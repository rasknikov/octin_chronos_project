"""
Hermetic Backtest v2 — Walk-Forward with Committee Oracle
==========================================================
Bar-by-bar OOS backtest with:
    1. Committee Voting Oracle (L4+L5 compass, L6+L7 trigger, L8 muted)
    2. Walk-Forward Micro-Retrain every 24h (freeze L1-L4, retrain L5-L7)
    3. Phase Seeding (training-time ATR normalisation)

BLINDAGEM RULES:
    - Oracle receives ONLY past data at each bar.
    - No access to full dataframe.
    - Spread + slippage on every trade.
    - Walk-forward retrain uses only past data window.

Usage:
    cd d:\\OCTIN\\octin_labs\\lab_axis_00
    venv\\Scripts\\python.exe 06_WEIERSTRASS_ENGINE\\hermetic_backtest.py
"""

import sys
import os
import math
import json
import time
import random
import numpy as np
import pandas as pd
import torch

def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

set_seed(42)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from config import LAYER_CONFIGS
from bot_execution import WeierstrassOracle


# ============================================================================
# HAND-CODED INCREMENTAL ATR (no lookahead)
# ============================================================================

class IncrementalATR:
    """Maintains running ATR. No lookahead."""
    def __init__(self, period: int):
        self.period = period
        self.alpha = 2.0 / (period + 1.0)
        self.atr = 0.0
        self.prev_close = None
        self.cumulative_atr = 0.0
        self.n_bars = 0

    def update(self, high: float, low: float, close: float) -> float:
        if self.prev_close is None:
            tr = high - low
        else:
            tr = max(high - low,
                     abs(high - self.prev_close),
                     abs(low - self.prev_close))

        if self.n_bars == 0:
            self.atr = tr
        else:
            self.atr = self.alpha * tr + (1.0 - self.alpha) * self.atr

        self.cumulative_atr += self.atr
        self.prev_close = close
        self.n_bars += 1
        return self.atr

    def get_cumulative(self) -> float:
        return self.cumulative_atr


# ============================================================================
# WALK-FORWARD MICRO-RETRAINER
# ============================================================================

class MicroRetrainer:
    """
    Re-optimises L5, L6, L7 on a rolling window of recent data.
    L1-L4 weights are FROZEN (macro = inert over weeks).

    This is the "breathing" mechanism that keeps the intraday layers
    aligned with current market volatility regime.
    """

    def __init__(self, base_weights_path: str, layer_configs: list,
                 retrain_window_bars: int = 720,  # ~30 days of H1
                 retrain_epochs: int = 500,
                 retrain_layers: list = None):
        """
        Parameters
        ----------
        base_weights_path : path to the initial weights JSON.
        layer_configs     : LAYER_CONFIGS list.
        retrain_window_bars: how many past bars to use for retrain.
        retrain_epochs    : epochs for micro-retrain (fast, ~500).
        retrain_layers    : which layers to retrain (default [4,5,6] = L5-L7).
        """
        self.base_weights_path = base_weights_path
        self.layer_configs = layer_configs
        self.retrain_window = retrain_window_bars
        self.retrain_epochs = retrain_epochs
        self.retrain_layers = retrain_layers or [4, 5, 6]  # L5, L6, L7

    def retrain(self, high: np.ndarray, low: np.ndarray,
                close: np.ndarray, timestamps: list, window_phi: np.ndarray, window_atr: np.ndarray, current_weights: dict) -> dict:
        """
        Micro-retrain the specified layers on the given data window.

        Returns updated weights dict (with L5-L7 re-optimised, L1-L4 frozen).
        """
        import torch
        import torch.nn as nn
        from weierstrass_engine import (PINNWeierstrassWaveLayer, ema_zero_phase,
                                         ema_lowpass, compute_atr, extract_pinn_features)

        n = len(close)
        residual = close.astype(np.float64).copy()

        from weierstrass_engine import evaluate_wave_pinn
        
        # Subtract the FROZEN layers' low-pass contributions
        # to get the residual that the retrain layers need to fit
        for k in range(len(self.layer_configs)):
            if k in self.retrain_layers:
                continue  # skip layers we're going to retrain
            if k >= len(self.layer_configs):
                break

            cfg = self.layer_configs[k]
            
            pinn_features_2d = extract_pinn_features(timestamps, window_atr[k], window_phi[k])
            
            # Use PyTorch directly for the exact full-dataset extraction (much faster than a Python loop of 168k evaluate_wave_pinn calls)
            layer = PINNWeierstrassWaveLayer(
                n_harmonics=current_weights['layers'][k].get('n_harmonics', 1),
                init_amp_hint=1.0,  # Placeholder, overwritten instantly
                init_freq_hint=1.0  # Placeholder, overwritten instantly
            )
            # Load exact weights
            with torch.no_grad():
                amps = current_weights['layers'][k].get('base_amplitudes', current_weights['layers'][k].get('amplitudes', [0.1]))
                freqs = current_weights['layers'][k].get('base_frequencies', current_weights['layers'][k].get('frequencies', [1.0]))
                layer.base_log_A.copy_(torch.tensor([math.log(max(a, 1e-8)) for a in amps]))
                layer.base_log_f.copy_(torch.tensor([math.log(max(f, 1e-8)) for f in freqs]))
                layer.base_phi.copy_(torch.tensor(current_weights['layers'][k].get('base_phi', current_weights['layers'][k].get('phase_shifts', [0.0]*len(amps)))))
                layer.b.copy_(torch.tensor(current_weights['layers'][k].get('dc_bias', 0.0)))
                
                if 'mlp_w1' in current_weights['layers'][k]:
                    layer.mlp[0].weight.copy_(torch.tensor(current_weights['layers'][k]['mlp_w1']))
                    layer.mlp[0].bias.copy_(torch.tensor(current_weights['layers'][k]['mlp_b1']))
                    layer.mlp[2].weight.copy_(torch.tensor(current_weights['layers'][k]['mlp_w2']))
                    layer.mlp[2].bias.copy_(torch.tensor(current_weights['layers'][k]['mlp_b2']))
                    layer.mlp[4].weight.copy_(torch.tensor(current_weights['layers'][k]['mlp_w3']))
                    layer.mlp[4].bias.copy_(torch.tensor(current_weights['layers'][k]['mlp_b3']))
            
            with torch.no_grad():
                pred = layer.forward(pinn_features_2d).squeeze().numpy()
                
            lowpass = ema_zero_phase(residual, span=cfg['ema_span'])
            residual = residual - lowpass

        # Now residual contains only the frequency content for L5-L7+L8
        # Re-train each retrain layer greedily
        updated_weights = json.loads(json.dumps(current_weights))  # deep copy

        for k in self.retrain_layers:
            cfg = self.layer_configs[k]

            pinn_features = extract_pinn_features(timestamps, window_atr[k], window_phi[k])

            # Low-pass of current residual
            lowpass = ema_zero_phase(residual, span=cfg['ema_span'])

            # Init hints
            init_amp = (np.max(lowpass) - np.min(lowpass)) / 2.0
            n_harmonics = cfg.get('n_harmonics', 8)

            # Create layer
            layer = PINNWeierstrassWaveLayer(
                n_harmonics=n_harmonics,
                init_freq_hint=1.0,
                init_amp_hint=1.0,
            )

            # LOAD EXISTING WEIGHTS BEFORE FINE-TUNING
            with torch.no_grad():
                amps = current_weights['layers'][k].get('base_amplitudes', [0.1])
                freqs = current_weights['layers'][k].get('base_frequencies', [1.0])
                layer.base_log_A.copy_(torch.tensor([math.log(max(a, 1e-8)) for a in amps]))
                layer.base_log_f.copy_(torch.tensor([math.log(max(f, 1e-8)) for f in freqs]))
                layer.base_phi.copy_(torch.tensor(current_weights['layers'][k].get('base_phi', [0.0]*len(amps))))
                layer.b.copy_(torch.tensor(current_weights['layers'][k].get('dc_bias', 0.0)))
                
                if 'mlp_w1' in current_weights['layers'][k]:
                    layer.mlp[0].weight.copy_(torch.tensor(current_weights['layers'][k]['mlp_w1']))
                    layer.mlp[0].bias.copy_(torch.tensor(current_weights['layers'][k]['mlp_b1']))
                    layer.mlp[2].weight.copy_(torch.tensor(current_weights['layers'][k]['mlp_w2']))
                    layer.mlp[2].bias.copy_(torch.tensor(current_weights['layers'][k]['mlp_b2']))
                    layer.mlp[4].weight.copy_(torch.tensor(current_weights['layers'][k]['mlp_w3']))
                    layer.mlp[4].bias.copy_(torch.tensor(current_weights['layers'][k]['mlp_b3']))

            # Train
            target = torch.tensor(lowpass, dtype=torch.float64)
            optimizer = torch.optim.Adam(layer.parameters(), lr=cfg['lr'])
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                optimizer, T_max=self.retrain_epochs, eta_min=cfg['lr'] * 0.01)
            criterion = nn.MSELoss()

            for epoch in range(self.retrain_epochs):
                optimizer.zero_grad()
                pred = layer.forward(pinn_features)
                loss = criterion(pred, target)
                loss.backward()
                optimizer.step()
                scheduler.step()

            # Freeze and extract params
            with torch.no_grad():
                params = layer.get_params_dict()

            # Update weights dict
            updated_weights['layers'][k]['base_amplitudes'] = params['base_amplitudes']
            updated_weights['layers'][k]['base_frequencies'] = params['base_frequencies']
            updated_weights['layers'][k]['base_phases'] = params['base_phases']
            updated_weights['layers'][k]['dc_bias'] = params['dc_bias']
            
            # MLP Weights
            updated_weights['layers'][k]['mlp_w1'] = params['mlp_w1']
            updated_weights['layers'][k]['mlp_b1'] = params['mlp_b1']
            updated_weights['layers'][k]['mlp_w2'] = params['mlp_w2']
            updated_weights['layers'][k]['mlp_b2'] = params['mlp_b2']
            updated_weights['layers'][k]['mlp_w3'] = params['mlp_w3']
            updated_weights['layers'][k]['mlp_b3'] = params['mlp_b3']

            # Detrend for next layer
            residual = residual - lowpass

        return updated_weights


# ============================================================================
# TRADE RECORD
# ============================================================================

class Trade:
    def __init__(self, entry_bar, entry_price, direction, exit_bar, exit_price, pnl_pips, expected_pips=0.0):
        self.entry_bar = entry_bar
        self.entry_price = entry_price
        self.direction = direction
        self.exit_bar = exit_bar
        self.exit_price = exit_price
        self.pnl_pips = pnl_pips
        self.expected_pips = expected_pips


# ============================================================================
# HERMETIC BACKTEST ENGINE v2
# ============================================================================

class HermeticBacktest:
    """Walk-forward hermetic backtest with committee Oracle."""

    def __init__(self, weights_path: str, layer_configs: list,
                 spread_pips: float = 2.0,
                 slippage_pips: float = 0.5,
                 projection_bars: int = 3,
                 hold_bars: int = 3,
                 warmup_bars: int = 500,
                 retrain_interval: int = 24,
                 retrain_window: int = 720,
                 retrain_epochs: int = 500,
                 retrain_layers: list = None):

        self.weights_path = weights_path
        self.layer_configs = layer_configs
        self.spread = spread_pips
        self.slippage = slippage_pips
        self.projection_bars = projection_bars
        self.hold_bars = hold_bars
        self.warmup_bars = warmup_bars
        self.retrain_interval = retrain_interval  # bars between retrains
        self.retrain_window = retrain_window
        self.retrain_epochs = retrain_epochs
        self.n_layers = len(layer_configs)

        # Load initial weights
        with open(weights_path, 'r') as f:
            self.current_weights = json.load(f)

        # Create Oracle with initial weights
        self.oracle = WeierstrassOracle(weights_path, spread_pips=spread_pips)

        # Phase seeding bounds
        self.phi_atr_mins = []
        self.phi_atr_maxs = []
        self.phi_atr_ranges = []
        for layer_w in self.current_weights['layers']:
            phi_min = layer_w.get('phi_atr_min', 0.0)
            phi_max = layer_w.get('phi_atr_max', 1.0)
            self.phi_atr_mins.append(phi_min)
            self.phi_atr_maxs.append(phi_max)
            self.phi_atr_ranges.append(phi_max - phi_min)

        # Create retrainer
        self.retrainer = MicroRetrainer(
            weights_path, layer_configs,
            retrain_window_bars=retrain_window,
            retrain_epochs=retrain_epochs,
            retrain_layers=retrain_layers
        )

    def _rebuild_oracle(self):
        """Rebuild Oracle from updated in-memory weights (no file I/O)."""
        # Write temp weights and reload
        tmp_path = self.weights_path + '.tmp'
        with open(tmp_path, 'w') as f:
            json.dump(self.current_weights, f)
        self.oracle = WeierstrassOracle(tmp_path, spread_pips=self.spread)
        os.remove(tmp_path)

    def run(self, high: np.ndarray, low: np.ndarray,
            close: np.ndarray, timestamps: list) -> dict:
        n = len(close)
        print(f"\n  Starting hermetic backtest v2: {n} bars, "
              f"warmup={self.warmup_bars}, hold={self.hold_bars}, "
              f"retrain every {self.retrain_interval}h")

        atrs = [IncrementalATR(cfg['atr_period']) for cfg in self.layer_configs]

        trades = []
        equity_curve = np.zeros(n, dtype=np.float64)
        cumulative_pnl = 0.0

        in_position = False
        position_dir = 0
        entry_bar = 0
        entry_price = 0.0
        entry_expected_pips = 0.0

        signals = np.zeros(n, dtype=np.int32)
        bars_since_retrain = 0
        n_retrains = 0

        import pandas as pd
        dt_series = pd.to_datetime(timestamps)
        hours_arr = dt_series.hour.values
        dows_arr = dt_series.weekday.values

        phi_history = np.zeros((self.n_layers, n), dtype=np.float64)
        atr_history = np.zeros((self.n_layers, n), dtype=np.float64)

        for bar in range(n):
            h, l, c = float(high[bar]), float(low[bar]), float(close[bar])
            bar_hour = int(hours_arr[bar])
            bar_dow = int(dows_arr[bar])

            # Update ATRs
            current_atr_values = []
            current_phi_atrs = []
            for k in range(self.n_layers):
                atr_val = atrs[k].update(h, l, c)
                current_atr_values.append(atr_val)
                raw_cum = atrs[k].get_cumulative()
                atr_range = self.phi_atr_ranges[k]
                if atr_range > 1e-12:
                    phi_norm = (raw_cum - self.phi_atr_mins[k]) / atr_range
                else:
                    phi_norm = bar / max(n - 1, 1)
                current_phi_atrs.append(phi_norm)

            phi_history[:, bar] = current_phi_atrs
            atr_history[:, bar] = current_atr_values

            # Skip warmup
            if bar < self.warmup_bars:
                equity_curve[bar] = cumulative_pnl
                continue

            # ----- WALK-FORWARD MICRO-RETRAIN -----
            bars_since_retrain += 1
            if bars_since_retrain >= self.retrain_interval and bar >= self.retrain_window:
                # Retrain on past window (ONLY past data!)
                start_idx = bar - self.retrain_window
                window_high = high[start_idx:bar]
                window_low = low[start_idx:bar]
                window_close = close[start_idx:bar]
                window_timestamps = timestamps[start_idx:bar]
                window_phi = phi_history[:, start_idx:bar]
                window_atr = atr_history[:, start_idx:bar]

                self.current_weights = self.retrainer.retrain(
                    window_high, window_low, window_close, window_timestamps,
                    window_phi, window_atr,
                    self.current_weights,
                )
                self._rebuild_oracle()
                bars_since_retrain = 0
                n_retrains += 1

                if n_retrains % 10 == 0:
                    print(f"    Retrain #{n_retrains} at bar {bar} "
                          f"({timestamps[bar]}) — PnL: {cumulative_pnl:+.1f} pips")

            # ----- Ask the Committee Oracle -----
            signal_result = self.oracle.generate_signal(
                current_hour=bar_hour,
                current_dow=bar_dow,
                current_phi_atrs=current_phi_atrs,
                current_atr_values=current_atr_values,
                phi_atr_ranges=self.phi_atr_ranges,
                projection_bars=self.projection_bars,
            )
            sig = signal_result['signal']
            signals[bar] = sig

            # ----- Position Management -----
            if in_position:
                bars_held = bar - entry_bar
                should_exit = (bars_held >= self.hold_bars or
                               (sig != 0 and sig != position_dir))

                if should_exit:
                    exit_price = c
                    raw_pnl = (exit_price - entry_price) * position_dir
                    pnl_pips = raw_pnl / 0.0001 - self.slippage
                    trades.append(Trade(entry_bar, entry_price, position_dir,
                                       bar, exit_price, pnl_pips, entry_expected_pips))
                    cumulative_pnl += pnl_pips
                    in_position = False
                    position_dir = 0

            if not in_position and sig != 0:
                entry_bar = bar
                entry_price = c + (self.spread + self.slippage) * 0.0001 * sig
                position_dir = sig
                entry_expected_pips = signal_result['delta_pips']
                in_position = True

            equity_curve[bar] = cumulative_pnl

        # Close open position
        if in_position:
            exit_price = float(close[-1])
            raw_pnl = (exit_price - entry_price) * position_dir
            pnl_pips = raw_pnl / 0.0001 - self.slippage
            trades.append(Trade(entry_bar, entry_price, position_dir,
                               n-1, exit_price, pnl_pips, entry_expected_pips))
            cumulative_pnl += pnl_pips
            equity_curve[-1] = cumulative_pnl

        print(f"  Total retrains: {n_retrains}")
        return self._compute_report(trades, equity_curve, signals, n, timestamps)

    def _compute_report(self, trades, equity_curve, signals, n_bars, timestamps):
        if len(trades) == 0:
            return {'n_trades': 0, 'message': 'NO TRADES',
                    'equity_curve': equity_curve, 'signals': signals}

        pnls = np.array([t.pnl_pips for t in trades])
        wins = pnls[pnls > 0]
        losses = pnls[pnls < 0]

        n_trades = len(trades)
        win_rate = len(wins) / n_trades if n_trades > 0 else 0.0
        gross_profit = float(np.sum(wins)) if len(wins) > 0 else 0.0
        gross_loss = float(np.sum(np.abs(losses))) if len(losses) > 0 else 0.0
        pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        peak = np.maximum.accumulate(equity_curve)
        dd = equity_curve - peak
        
        # --- ML / AI Metrics ---
        # Did the direction of the trade match the actual return direction?
        # A positive PnL (ignoring spread/slippage for pure direction) means we got it right.
        # But we will just use pnl_pips > - (spread + slippage) as a proxy, or better:
        actual_returns = np.array([t.exit_price - t.entry_price for t in trades])
        actual_pips_raw = (actual_returns / 0.0001) * np.array([t.direction for t in trades])
        
        directional_accuracy = np.mean(actual_pips_raw > 0) * 100.0 if n_trades > 0 else 0.0
        
        # Precision by direction
        long_trades = [t for t in trades if t.direction == 1]
        short_trades = [t for t in trades if t.direction == -1]
        
        long_wins = sum(1 for t in long_trades if (t.exit_price - t.entry_price) > 0)
        short_wins = sum(1 for t in short_trades if (t.entry_price - t.exit_price) > 0)
        
        long_precision = (long_wins / len(long_trades) * 100.0) if long_trades else 0.0
        short_precision = (short_wins / len(short_trades) * 100.0) if short_trades else 0.0
        
        # Regression metrics (Expected vs Actual)
        # Assuming we added `expected_pips` to the Trade object during execution
        has_expected = hasattr(trades[0], 'expected_pips')
        mae, rmse, ic = 0.0, 0.0, 0.0
        if has_expected:
            preds = np.array([t.expected_pips for t in trades])
            # actual target is the raw pip movement in the direction of the trade, without crossing spread
            targets = np.array([(t.exit_price - t.entry_price) / 0.0001 * t.direction for t in trades])
            
            mae = np.mean(np.abs(preds - targets))
            rmse = np.sqrt(np.mean((preds - targets)**2))
            
            # Information Coefficient (Pearson Correlation between prediction and actual return)
            if np.std(preds) > 0 and np.std(targets) > 0:
                ic = np.corrcoef(preds, targets)[0, 1]

        return {
            'n_trades': n_trades,
            'n_wins': len(wins),
            'n_losses': len(losses),
            'win_rate': win_rate,
            'total_pnl_pips': float(np.sum(pnls)),
            'avg_win_pips': float(np.mean(wins)) if len(wins) > 0 else 0.0,
            'avg_loss_pips': float(np.mean(losses)) if len(losses) > 0 else 0.0,
            'profit_factor': pf,
            'max_drawdown_pips': float(np.min(dd)),
            'avg_duration_bars': float(np.mean([t.exit_bar - t.entry_bar for t in trades])),
            'n_long': len(long_trades),
            'n_short': len(short_trades),
            'directional_accuracy': directional_accuracy,
            'long_precision': long_precision,
            'short_precision': short_precision,
            'mae_pips': mae,
            'rmse_pips': rmse,
            'ic': ic,
            'equity_curve': equity_curve,
            'signals': signals,
            'trades': trades,
        }


# ============================================================================
# DATA LOADING + PLOTTING + MAIN
# ============================================================================

def load_eurusd_from_1999(csv_path):
    timestamps, opens, highs, lows, closes = [], [], [], [], []
    with open(csv_path, 'r') as f:
        f.readline()
        for line in f:
            parts = line.strip().split(',')
            if len(parts) < 7 or parts[0] < '1999':
                continue
            timestamps.append(parts[0])
            opens.append(float(parts[3]))
            highs.append(float(parts[4]))
            lows.append(float(parts[5]))
            closes.append(float(parts[6]))
    return {
        'timestamp': timestamps,
        'open': np.array(opens, dtype=np.float64),
        'high': np.array(highs, dtype=np.float64),
        'low': np.array(lows, dtype=np.float64),
        'close': np.array(closes, dtype=np.float64),
    }


def save_backtest_plot(report, output_path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    equity = report['equity_curve']
    n = len(equity)
    x = np.arange(n)

    fig, axes = plt.subplots(2, 1, figsize=(20, 10), sharex=True,
                             gridspec_kw={'height_ratios': [3, 1]})

    axes[0].plot(x, equity, color='#2A9D8F', linewidth=0.8)
    axes[0].axhline(0, color='black', linewidth=0.5, linestyle='--')
    axes[0].set_title(f"Hermetic Backtest v2 (Committee + Walk-Forward)  |  "
                      f"PF={report['profit_factor']:.2f}  "
                      f"WR={report['win_rate']*100:.1f}%  "
                      f"Trades={report['n_trades']}",
                      fontsize=13, fontweight='bold')
    axes[0].set_ylabel('Cumulative PnL (pips)')
    axes[0].grid(True, alpha=0.3)
    axes[0].fill_between(x, equity, 0, where=equity >= 0,
                         color='#2A9D8F', alpha=0.1)
    axes[0].fill_between(x, equity, 0, where=equity < 0,
                         color='#E63946', alpha=0.1)

    peak = np.maximum.accumulate(equity)
    dd = equity - peak
    axes[1].fill_between(x, dd, 0, color='#E63946', alpha=0.5)
    axes[1].plot(x, dd, color='#E63946', linewidth=0.5)
    axes[1].set_title(f"Drawdown  |  Max DD = {report['max_drawdown_pips']:.1f} pips",
                      fontsize=11)
    axes[1].set_ylabel('Drawdown (pips)')
    axes[1].set_xlabel('Bar Index (H1)')
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Equity curve plot saved: {output_path}")


def main():
    PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
    CSV_PATH = os.path.join(PROJECT_ROOT, '01_DATALAKE', 'eurusd_h1_ohlc.csv')
    WEIGHTS_PATH = os.path.join(SCRIPT_DIR, 'pesos_weierstrass.json')

    if not os.path.exists(WEIGHTS_PATH):
        print(f"ERROR: Weights not found: {WEIGHTS_PATH}")
        sys.exit(1)

    print(f"Loading EURUSD H1 data...")
    data = load_eurusd_from_1999(CSV_PATH)
    # TRUNCATE FOR MACRO EXPERIMENT (5 Years)
    limit = 30000
    for k in data:
        data[k] = data[k][:limit]
    print(f"  Loaded {len(data['close'])} bars")

    t_start = time.time()

    backtest = HermeticBacktest(
        weights_path=WEIGHTS_PATH,
        layer_configs=LAYER_CONFIGS,
        spread_pips=2.0,
        slippage_pips=0.5,
        projection_bars=168,   # Predict 1 week ahead
        hold_bars=168,         # Hold 1 week
        warmup_bars=500,
        retrain_interval=168,  # retrain every week
        retrain_window=4320,   # lookback 6 months
        retrain_epochs=150,    # slightly faster retrain
        retrain_layers=[3, 4]  # Retrain Monthly and Weekly
    )

    report = backtest.run(
        high=data['high'],
        low=data['low'],
        close=data['close'],
        timestamps=data['timestamp'],
    )

    elapsed = time.time() - t_start

    print(f"\n{'='*70}")
    print(f"  HERMETIC BACKTEST v2 REPORT")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"{'='*70}")

    if report['n_trades'] == 0:
        print("  NO TRADES GENERATED.")
        return

    print(f"\n  Total Trades:     {report['n_trades']}")
    print(f"  Long / Short:     {report['n_long']} / {report['n_short']}")
    print(f"  Win Rate:         {report['win_rate']*100:.2f}%")
    print(f"  Profit Factor:    {report['profit_factor']:.4f}")
    print(f"  Total PnL:        {report['total_pnl_pips']:+.1f} pips")
    print(f"  Avg Win:          {report['avg_win_pips']:+.1f} pips")
    print(f"  Avg Loss:         {report['avg_loss_pips']:.1f} pips")
    print(f"  Max Drawdown:     {report['max_drawdown_pips']:.1f} pips")
    print(f"  Avg Duration:     {report['avg_duration_bars']:.1f} bars")
    
    print(f"\n  --- ML Performance Metrics ---")
    print(f"  Dir. Accuracy:    {report['directional_accuracy']:.2f}%")
    print(f"  Long Precision:   {report['long_precision']:.2f}%")
    print(f"  Short Precision:  {report['short_precision']:.2f}%")
    print(f"  Predictive MAE:   {report['mae_pips']:.2f} pips")
    print(f"  Predictive RMSE:  {report['rmse_pips']:.2f} pips")
    print(f"  Info Coeff (IC):  {report['ic']:.4f}")

    save_backtest_plot(report, os.path.join(SCRIPT_DIR, 'backtest_equity.png'))
    print(f"\n  BACKTEST COMPLETE.")


if __name__ == '__main__':
    main()
