import time
import math
import random
import torch
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from config import CSV_PATH, WEIGHTS_PATH, DEVICE, LAYER_CONFIGS
from siren_engine import FMSiren, compute_atr, ema_zero_phase, siren_loss_fn
from siren_bot_execution import SirenOracle


def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

def load_eurusd_from_1999(csv_path: str) -> dict:
    df = pd.read_csv(csv_path, sep=',')
    df = df[df['timestamp'] >= '1999-01-01']
    return {
        'timestamp': df['timestamp'].values,
        'open': df['Open'].values.astype(np.float64),
        'high': df['High'].values.astype(np.float64),
        'low': df['Low'].values.astype(np.float64),
        'close': df['Close'].values.astype(np.float64),
        'spread': df['Spread'].values.astype(np.float64) / 10.0 # Standardize to pips
    }


class Trade:
    def __init__(self, entry_idx: int, entry_price: float, direction: int, expected_pips: float):
        self.entry_idx = entry_idx
        self.entry_price = entry_price
        self.direction = direction   # 1 for Long, -1 for Short
        self.expected_pips = expected_pips
        self.exit_idx = None
        self.exit_price = None
        self.pnl_pips = 0.0

    def close(self, exit_idx: int, exit_price: float):
        self.exit_idx = exit_idx
        self.exit_price = exit_price
        diff = self.exit_price - self.entry_price
        self.pnl_pips = (diff * 10000.0) * self.direction


class SirenMicroRetrainer:
    """
    Retrains the TRIGGER layers exactly like the V2 MicroRetrainer but for SIREN models.
    """
    def __init__(self, initial_weights_path: str, 
                 retrain_epochs: int = 150, 
                 retrain_layers: list = None):
                 
        with open(initial_weights_path, 'r') as f:
            self.base_weights = json.load(f)
            
        self.layer_configs = LAYER_CONFIGS
        self.retrain_epochs = retrain_epochs
        
        # Matches the triggered layers
        self.retrain_layers = retrain_layers or [3, 4] # L4 and L5

    def retrain(self, close_prices: np.ndarray, window_phi: list) -> dict:
        """
        Retrain Walk-Forward window logic.
        Extracts residual from L1 -> Ln, training only the retrained_layers using FMSiren
        with the Pearson Loss function to bend correctly.
        """
        # Start matching current base exactly
        updated_weights = json.loads(json.dumps(self.base_weights))
        
        residual = close_prices.copy()
        
        # Sequentially subtract frozen layers
        for k in range(len(self.layer_configs)):
            cfg = self.layer_configs[k]
            
            # If frozen layer (Macro), just subtract its lowpass target
            lowpass = ema_zero_phase(residual, span=cfg['span'])
            residual = residual - lowpass
            
            if k in self.retrain_layers:
                # We need to retrain this SIREN
                target_smoothed = lowpass
                
                phi_1d = window_phi[k]
                
                # Normalize inside limits of the exact bounds from extraction
                phi_min = updated_weights['layers'][k]['phi_atr_min']
                phi_max = updated_weights['layers'][k]['phi_atr_max']
                range_phi = phi_max - phi_min
                norm_phi = (phi_1d - phi_min) / range_phi if range_phi != 0 else np.zeros_like(phi_1d)
                
                X_t = torch.tensor(norm_phi, dtype=torch.float32, device=DEVICE).unsqueeze(1)
                Y_t = torch.tensor(target_smoothed, dtype=torch.float32, device=DEVICE).unsqueeze(1)

                model = FMSiren(
                    in_features=1, 
                    hidden_features=cfg['hidden_features'], 
                    hidden_layers=cfg['hidden_layers'], 
                    out_features=1, 
                    omega_0=cfg['omega_0']
                ).to(DEVICE)
                
                # Load pre-trained weights to avoid amnesia
                raw_state = updated_weights['layers'][k]['state_dict']
                tensor_state = {key: torch.tensor(v, dtype=torch.float32, device=DEVICE) for key, v in raw_state.items()}
                model.load_state_dict(tensor_state)
                
                optimizer = torch.optim.Adam(model.parameters(), lr=cfg['lr'])
                scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=self.retrain_epochs)
                
                best_loss = float('inf')
                best_state = None
                
                for epoch in range(self.retrain_epochs):
                    optimizer.zero_grad()
                    preds = model(X_t)
                    
                    # Pearson FMSIREN Custom Loss
                    loss_val, mse_val, pearson_val = siren_loss_fn(preds, Y_t, alpha=cfg['alpha'], beta=cfg['beta'])
                    
                    loss_val.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optimizer.step()
                    scheduler.step()
                    
                    if loss_val.item() < best_loss:
                        best_loss = loss_val.item()
                        best_state = {key: val.cpu().clone() for key, val in model.state_dict().items()}
                
                if best_state is not None:
                    state_dict_serializable = {key: val.numpy().tolist() for key, val in best_state.items()}
                    updated_weights['layers'][k]['state_dict'] = state_dict_serializable
                
        return updated_weights


class SirenHermeticBacktest:
    """
    Step-by-step out-of-sample execution.
    """
    def __init__(self,
                 warmup_bars: int = 500,
                 projection_bars: int = 168,
                 hold_bars: int = 168,
                 retrain_window: int = 4320,
                 retrain_interval: int = 168,
                 retrain_epochs: int = 150,
                 retrain_layers: list = None):
                 
        self.warmup_bars = warmup_bars
        self.projection_bars = projection_bars
        self.hold_bars = hold_bars
        
        self.retrain_window = retrain_window
        self.retrain_interval = retrain_interval
        
        self.retrainer = SirenMicroRetrainer(
            '07_FRACTAL_FM_ENGINE/pesos_fm_siren_init.json', 
            retrain_epochs=retrain_epochs,
            retrain_layers=retrain_layers
        )
        self.current_weights = self.retrainer.base_weights

    def run(self, data: dict) -> dict:
        total_bars = len(data['close'])
        
        trades = []
        active_trade = None
        
        equity = 0.0
        equity_curve = []
        trade_bars = []
        drawdown_history = []
        max_equity = 0.0
        
        phi_history = [np.zeros(total_bars) for _ in LAYER_CONFIGS]
        atr_history = [np.zeros(total_bars) for _ in LAYER_CONFIGS]
        
        n_retrains = 0
        
        # Build oracle with base weights out of the box
        oracle = SirenOracle('07_FRACTAL_FM_ENGINE/pesos_fm_siren_init.json')
        
        for i in range(self.warmup_bars, total_bars - self.hold_bars):
            
            # --- Extract global phase hermetically ---
            window_slice_close = data['close'][i - self.warmup_bars:i]
            window_slice_high = data['high'][i - self.warmup_bars:i]
            window_slice_low = data['low'][i - self.warmup_bars:i]
            
            current_atr_values = []
            current_phi_atrs = []
            
            for k, cfg in enumerate(LAYER_CONFIGS):
                atrs = compute_atr(window_slice_high, window_slice_low, window_slice_close, cfg['atr_period'])
                
                target_atr = float(atrs[-1])
                current_atr_values.append(target_atr)
                
                # Retrieve last computed step and sum locally
                if i > self.warmup_bars:
                    phi_history[k][i] = phi_history[k][i-1] + target_atr
                else: # at 500
                    phi_history[k][i] = np.sum(atrs) 
                
                atr_history[k][i] = target_atr
                current_phi_atrs.append(phi_history[k][i])

            # EXIT TRADE First
            if active_trade is not None:
                bars_held = i - active_trade.entry_idx
                if bars_held >= self.hold_bars:
                    exit_p = data['close'][i]
                    if active_trade.direction == 1:
                        # pay spread on exit if we bought (bid to sell)
                        exit_p -= (data['spread'][i] / 10000.0) 
                    else:
                        exit_p += (data['spread'][i] / 10000.0)

                    active_trade.close(i, exit_p)
                    equity += active_trade.pnl_pips
                    trades.append(active_trade)
                    active_trade = None

            # ORACLE EXECUTION 
            if active_trade is None:
                result = oracle.generate_signal(
                    current_phi_atrs,
                    current_atr_values,
                    self.projection_bars
                )
                
                sig = result['signal']
                if sig != 0:
                    entry_p = data['close'][i]
                    # slippage modeled as paying spread
                    if sig == 1:
                        entry_p += (data['spread'][i] / 10000.0)
                    else:
                        entry_p -= (data['spread'][i] / 10000.0)
                        
                    active_trade = Trade(i, entry_p, sig, result['expected_pips'])

            # RECORD METRICS
            current_eq = equity
            if active_trade is not None:
                unrealized = ((data['close'][i] - active_trade.entry_price) * 10000.0) * active_trade.direction
                current_eq += unrealized
                
            equity_curve.append(current_eq)
            trade_bars.append(i)
            
            if current_eq > max_equity:
                max_equity = current_eq
            drawdown_history.append(current_eq - max_equity)

            # RETRAIN LOGIC (Walk-Forward)
            if (i - self.warmup_bars) % self.retrain_interval == 0 and (i - self.warmup_bars) > 0:
                n_retrains += 1
                
                start_idx = max(0, i - self.retrain_window)
                
                w_close = data['close'][start_idx:i]
                w_phi = [phi_history[k][start_idx:i] for k in range(len(LAYER_CONFIGS))]
                
                self.current_weights = self.retrainer.retrain(w_close, w_phi)
                # Overwrite Oracle memory with new weights dict
                oracle.layers = self.current_weights['layers']
                
                if n_retrains % 10 == 0:
                    print(f"    Retrain #{n_retrains} at bar {i} — PnL: {current_eq:+.1f} pips")

        print(f"\n  Total retrains: {n_retrains}")
        return self._compute_report(trades, equity_curve, trade_bars, drawdown_history)

    def _compute_report(self, trades, equity_curve, trade_bars, max_drawdowns):
        if not trades:
            return {"Total Trades": 0}
            
        pnl = [t.pnl_pips for t in trades]
        wins = [p for p in pnl if p > 0]
        losses = [p for p in pnl if p <= 0]
        
        longs = [t for t in trades if t.direction == 1]
        shorts = [t for t in trades if t.direction == -1]

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.0
        
        # Machine Learning Metrics (Phase Directional matching)
        correct_directions = 0
        long_won = 0
        short_won = 0
        
        errors_pips = []
        actual_vs_expected = []
        
        for t in trades:
            if t.pnl_pips > 0:
                correct_directions += 1
                if t.direction == 1:
                    long_won += 1
                else:
                    short_won += 1
            
            # Predict Pips vs Actual Result Pips
            errors_pips.append(abs(t.expected_pips - t.pnl_pips))
            actual_vs_expected.append((t.pnl_pips, t.expected_pips))

        total_t = len(trades)
        dir_accuracy = (correct_directions / total_t) * 100.0
        long_precision = (long_won / len(longs) * 100.0) if len(longs) > 0 else 0.0
        short_precision = (short_won / len(shorts) * 100.0) if len(shorts) > 0 else 0.0
        
        mae = np.mean(errors_pips)
        rmse = np.sqrt(np.mean(np.array(errors_pips)**2))
        
        # IC (Information Coefficient) = Correlation between expected delta and actual PnL
        actuals = np.array([x[0] for x in actual_vs_expected])
        expecteds = np.array([x[1] for x in actual_vs_expected])
        
        if len(actuals) > 1 and np.std(actuals) > 0 and np.std(expecteds) > 0:
            ic = np.corrcoef(actuals, expecteds)[0, 1]
        else:
            ic = 0.0

        # Plot Equity
        plt.figure(figsize=(10,5))
        plt.plot(trade_bars, equity_curve, color='blue', label='Siren Oracle PnL')
        plt.fill_between(trade_bars, equity_curve, alpha=0.1, color='blue')
        plt.title(f"SIREN V3 Walk-Forward PnL: +{sum(pnl):.1f} pips")
        plt.legend()
        plt.grid(True)
        plt.savefig('07_FRACTAL_FM_ENGINE/siren_backtest_equity.png')
        plt.close()

        report = f"""
======================================================================
  FM SIREN BACKTEST v3 REPORT
======================================================================

  Total Trades:     {total_t}
  Long / Short:     {len(longs)} / {len(shorts)}
  Win Rate:         {len(wins) / total_t * 100:.2f}%
  Profit Factor:    {profit_factor:.4f}
  Total PnL:        {sum(pnl):+.1f} pips
  Avg Win:          {np.mean(wins) if wins else 0:+.1f} pips
  Avg Loss:         {np.mean(losses) if losses else 0:+.1f} pips
  Max Drawdown:     {min(max_drawdowns):+.1f} pips

  --- ML Performance Metrics ---
  Dir. Accuracy:    {dir_accuracy:.2f}%
  Long Precision:   {long_precision:.2f}%
  Short Precision:  {short_precision:.2f}%
  Predictive MAE:   {mae:.2f} pips
  Predictive RMSE:  {rmse:.2f} pips
  Info Coeff (IC):  {ic:+.4f}
"""
        return report

def main():
    set_seed(42)
    
    print(f"Loading EURUSD H1 data...")
    data = load_eurusd_from_1999(CSV_PATH)
    
    # TRUNCATE FOR MACRO EXPERIMENT COMPARISON
    limit = 30000 
    for k in data:
        data[k] = data[k][:limit]
    print(f"  Loaded {len(data['close'])} bars")

    t_start = time.time()
    
    # Exactly matches MACRO PINN parameters but WITHOUT leak
    backtest = SirenHermeticBacktest(
        warmup_bars=4320,
        projection_bars=168,
        hold_bars=168,
        retrain_window=4320,
        retrain_interval=168,
        retrain_epochs=150,
        retrain_layers=[1, 2, 3, 4]  # Compass and Triggers must be retrained to avoid future leak
    )
    
    print("\n  Starting FMSIREN Hermetic Walk-Forward: 30000 bars, Retrain L4/L5")
    report = backtest.run(data)
    
    print(report)
    print(f"\n  BACKTEST COMPLETE. Elapsed: {time.time() - t_start:.1f}s")


if __name__ == '__main__':
    main()
