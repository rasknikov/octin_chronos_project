"""
Weierstrass Decomposition Engine  v3
=====================================
Volatility-Modulated Sinusoidal Decomposition with Greedy Layer-Wise Training.

Mathematics
-----------
Each layer k models a BANK of N_h harmonics (a mini-Weierstrass sum):

    y_k(t) = Σ_{h=1}^{N_h}  A_{k,h} · sin(2π · f_{k,h} · Φ_ATR_k(t) + φ_{k,h})  + b_k

where Φ_ATR_k(t) = normalised cumulative integral of ATR_k up to time t.

CRITICAL FIX (v3): The detrending is SUBTRACTIVE via the low-pass filter itself.
    - The EMA(residual) IS the macro signal at that scale.
    - We train the layer against EMA(residual) so it learns the shape.
    - We subtract EMA(residual) from the raw residual to produce the next residual.
    - The trained layer is STORED for reconstruction, not used for subtraction.

This guarantees perfect detrending: each layer peels off exactly the frequency
band that the EMA reveals, with zero phase-lag contamination in the residual chain.

No LSTMs, no Transformers, no FFT, no scipy, no pandas.ewm, no ta-lib.
Everything is hand-coded from first principles.
"""

import math
import json
from datetime import datetime
import torch
import torch.nn as nn
import numpy as np
import numpy as np


# ============================================================================
# 1. HAND-CODED EMA LOW-PASS FILTER ("The Sandpaper")
# ============================================================================

def ema_lowpass(signal: np.ndarray, span: int) -> np.ndarray:
    """
    Forward-only Exponential Moving Average.

    Parameters
    ----------
    signal : 1-D numpy array of floats.
    span   : int, EMA span (larger = smoother).

    Returns
    -------
    smoothed : 1-D numpy array, same length as input.
    """
    n = len(signal)
    alpha = 2.0 / (span + 1.0)
    smoothed = np.empty(n, dtype=np.float64)
    smoothed[0] = signal[0]
    for i in range(1, n):
        smoothed[i] = alpha * signal[i] + (1.0 - alpha) * smoothed[i - 1]
    return smoothed


def ema_zero_phase(signal: np.ndarray, span: int) -> np.ndarray:
    """
    Zero-phase EMA: forward pass followed by backward pass.

    This eliminates the phase lag of a standard EMA while preserving
    its amplitude attenuation characteristics. The result is a symmetric,
    zero-lag low-pass filter.

    Parameters
    ----------
    signal : 1-D numpy array.
    span   : int, EMA span.

    Returns
    -------
    smoothed : 1-D numpy array, same length as input.
    """
    # Forward pass
    fwd = ema_lowpass(signal, span)
    # Backward pass on reversed forward result
    bwd = ema_lowpass(fwd[::-1], span)
    return bwd[::-1].copy()


# ============================================================================
# 2. HAND-CODED ATR (True Range → EMA → Cumulative Integral)
# ============================================================================

def compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                period: int) -> np.ndarray:
    """
    Compute the Average True Range and return its cumulative integral.

    Steps:
        1. True Range = max(H-L, |H-C_prev|, |L-C_prev|)
        2. ATR = EMA(True Range, span=period)
        3. Φ_ATR = cumsum(ATR), then normalised to [0, 1].

    Returns
    -------
    phi_atr : 1-D numpy array, the normalised cumulative ATR integral.
    """
    n = len(high)
    tr = np.empty(n, dtype=np.float64)

    tr[0] = high[0] - low[0]
    for i in range(1, n):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i - 1])
        lc = abs(low[i] - close[i - 1])
        tr[i] = max(hl, hc, lc)

    atr = ema_lowpass(tr, span=period)
    phi_atr = np.cumsum(atr)

    phi_min = phi_atr[0]
    phi_max = phi_atr[-1]
    if phi_max - phi_min > 1e-12:
        phi_atr = (phi_atr - phi_min) / (phi_max - phi_min)
    else:
        phi_atr = np.linspace(0.0, 1.0, n)

    return phi_atr


# ============================================================================
# 3. DATE/TIME CYCLE EXTRACTION (PINN Features)
# ============================================================================

def extract_pinn_features(timestamps_str: list[str], atr: np.ndarray,
                          phi_atr: np.ndarray) -> torch.Tensor:
    """
    Convert raw strings + ATR into the PINN feature matrix.
    
    Features (5 cols):
    1. phi_atr (normalised cumulative phase)
    2. atr_val (current volatility depth)
    3. sin(hour), cos(hour) (circadian cycle, 24h)
    4. sin(dow), cos(dow)   (weekly cycle, 5d)
    
    Returns
    -------
    features : torch.Tensor of shape (N, 6)
    """
    import pandas as pd
    from datetime import datetime
    import math
    
    n = len(timestamps_str)
    feats = np.zeros((n, 6), dtype=np.float64)
    
    if n == 1:
        # Fast path for single inference loops (Oracle)
        dt = datetime.strptime(timestamps_str[0], "%Y-%m-%d %H:%M:%S")
        h = dt.hour
        dow = dt.weekday()
        feats[0, 2] = math.sin(2.0 * math.pi * h / 24.0)
        feats[0, 3] = math.cos(2.0 * math.pi * h / 24.0)
        feats[0, 4] = math.sin(2.0 * math.pi * dow / 5.0)
        feats[0, 5] = math.cos(2.0 * math.pi * dow / 5.0)
    else:
        # Fast vectorized path for large arrays (Backtester init)
        dt_series = pd.to_datetime(timestamps_str)
        h = dt_series.hour.values
        dow = dt_series.weekday.values
        feats[:, 2] = np.sin(2.0 * np.pi * h / 24.0)
        feats[:, 3] = np.cos(2.0 * np.pi * h / 24.0)
        feats[:, 4] = np.sin(2.0 * np.pi * dow / 5.0)
        feats[:, 5] = np.cos(2.0 * np.pi * dow / 5.0)
    
    feats[:, 0] = phi_atr
    feats[:, 1] = atr / (np.max(atr) + 1e-12)  # normalize ATR safely
    
    return torch.tensor(feats, dtype=torch.float64)


# ============================================================================
# 4. THE PINN WEIERSTRASS WAVE LAYER (nn.Module)
# ============================================================================

class PINNWeierstrassWaveLayer(nn.Module):
    """
    Physics-Informed Neural Network for Wave Decomposition.
    
    Instead of fixed parameters {A, f, phi}, this uses an MLP to predict 
    dynamically modulated parameters {A(t), f(t), phi(t)} based on the environment.
    
    y(t) = Σ_{h=1}^{N_h} (A_h + ΔA_h(t)) · sin(2π · (f_h + Δf_h(t)) · Φ_ATR(t) + (φ_h + Δφ_h(t))) + b
    """

    def __init__(self, n_harmonics: int = 4,
                 init_freq_hint: float = 1.0,
                 init_amp_hint: float = 0.1):
        super().__init__()
        self.n_harmonics = n_harmonics

        # --- Base Static Parameters (same as v1, provides stability) ---
        amp_per_h = init_amp_hint / np.arange(1, n_harmonics + 1).astype(np.float64)
        freq_spread = np.geomspace(
            max(init_freq_hint * 0.5, 0.5),
            max(init_freq_hint * 2.0, 2.0),
            n_harmonics,
        )

        self.base_log_A = nn.Parameter(torch.tensor(
            [math.log(max(a, 1e-8)) for a in amp_per_h], dtype=torch.float64))
        self.base_log_f = nn.Parameter(torch.tensor(
            [math.log(max(f, 1e-8)) for f in freq_spread], dtype=torch.float64))
        self.base_phi = nn.Parameter(torch.zeros(n_harmonics, dtype=torch.float64))
        self.b = nn.Parameter(torch.tensor(0.0, dtype=torch.float64))

        # --- The PINN (MLP Matrix) ---
        # Input: 6 features (phi_atr, atr_norm, sin_h, cos_h, sin_dow, cos_dow)
        # Output: 3 * N_harmonics deltas (ΔA, Δf, Δφ)
        hidden_dim = 16
        
        self.mlp = nn.Sequential(
            nn.Linear(6, hidden_dim, dtype=torch.float64),
            nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim, dtype=torch.float64),
            nn.Tanh(),
            nn.Linear(hidden_dim, 3 * n_harmonics, dtype=torch.float64)
        )
        
        # Initialize MLP weights to near-zero so it starts as a pure static wave
        with torch.no_grad():
            self.mlp[-1].weight.fill_(1e-5)
            self.mlp[-1].bias.fill_(0.0)

    def forward(self, pinn_features: torch.Tensor) -> torch.Tensor:
        """
        pinn_features: Tensor of shape (batch_size, 6)
        Returns y(t) of shape (batch_size,)
        """
        # Base parameters
        base_A = torch.exp(self.base_log_A)
        base_f = torch.exp(self.base_log_f)
        
        # MLP Deltas
        deltas = self.mlp(pinn_features)  # (batch_size, 3 * n_harmonics)
        
        delta_A   = deltas[:, 0 : self.n_harmonics]                 # (N, H)
        delta_f   = deltas[:, self.n_harmonics : 2*self.n_harmonics] # (N, H)
        delta_phi = deltas[:, 2*self.n_harmonics : 3*self.n_harmonics] # (N, H)
        
        # We use Tanh on deltas to bound the modulations (prevent unstable blowup)
        # A can vary by ±50%
        # f can vary by ±20%
        # phi can vary by ±pi/2
        A_dynamic = base_A.unsqueeze(0) * (1.0 + 0.5 * torch.tanh(delta_A))
        f_dynamic = base_f.unsqueeze(0) * (1.0 + 0.2 * torch.tanh(delta_f))
        phi_dynamic = self.base_phi.unsqueeze(0) + (math.pi/2.0) * torch.tanh(delta_phi)
        
        phi_atr = pinn_features[:, 0]  # The time axis
        
        # Evaluate wave
        phase_arg = (2.0 * math.pi * f_dynamic * phi_atr.unsqueeze(1) + phi_dynamic)
        waves = A_dynamic * torch.sin(phase_arg)  # (N, H)
        
        y = waves.sum(dim=1) + self.b
        return y

    def get_params_dict(self) -> dict:
        """Return all weights needed for Numpy forward pass in the Oracle."""
        with torch.no_grad():
            return {
                "n_harmonics": self.n_harmonics,
                "base_amplitudes": torch.exp(self.base_log_A).tolist(),
                "base_frequencies": torch.exp(self.base_log_f).tolist(),
                "base_phases": self.base_phi.tolist(),
                "dc_bias": self.b.item(),
                "mlp_w1": self.mlp[0].weight.tolist(),
                "mlp_b1": self.mlp[0].bias.tolist(),
                "mlp_w2": self.mlp[2].weight.tolist(),
                "mlp_b2": self.mlp[2].bias.tolist(),
                "mlp_w3": self.mlp[4].weight.tolist(),
                "mlp_b3": self.mlp[4].bias.tolist(),
            }


# ============================================================================
# 4. THE GREEDY WEIERSTRASS DECOMPOSER (v3 — correct detrending)
# ============================================================================

class GreedyWeierstrassDecomposer:
    """
    Greedy Layer-Wise decomposition engine.

    KEY DESIGN (v3):
    ~~~~~~~~~~~~~~~~
    The detrending is done by the LOW-PASS FILTER, not by the trained layer.

    For each layer k:
        1. low_k = ZeroPhaseEMA(residual_k, span_k)     ← the "macro" at this scale
        2. Train WeierstrassWaveLayer_k to FIT low_k     ← learn the shape
        3. residual_{k+1} = residual_k − low_k           ← EXACT subtractive detrending
        4. Freeze the layer.

    Reconstruction:
        Price(t) ≈ Σ_k  layer_k(t, ATR_k)               ← sum of all trained layers

    Why this works:
        - low_k is the EXACT low-pass of the residual. Subtracting it is a perfect
          high-pass filter — no phase error, no amplitude distortion.
        - The trained layer approximates low_k. If it's imperfect, it doesn't matter
          for the residual chain — only for the final reconstruction quality.
        - The residual chain is PERFECT: each step removes exactly the frequency band
          that the EMA span allows through.
    """

    def __init__(self, layer_configs: list[dict], verbose: bool = True):
        self.layer_configs = layer_configs
        self.verbose = verbose
        self.layers: list[PINNWeierstrassWaveLayer] = []
        self.layer_phi_atrs: list[np.ndarray] = []
        self.layer_predictions: list[np.ndarray] = []
        self.lowpass_signals: list[np.ndarray] = []
        self.training_losses: list[list[float]] = []

    def decompose(self, close: np.ndarray, high: np.ndarray,
                  low: np.ndarray, timestamps_str: list[str]) -> dict:
        """
        Run the full greedy decomposition using PINNs.

        Parameters
        ----------
        close, high, low : np.ndarray price data.
        timestamps_str   : list of string timestamps "YYYY-MM-DD HH:MM:SS"
        -------
        result : dict with keys:
            'layers'         — list of WeierstrassWaveLayer (frozen)
            'predictions'    — list of np.ndarray (layer outputs for reconstruction)
            'lowpass_signals'— list of np.ndarray (exact low-pass used for detrending)
            'reconstruction' — np.ndarray, sum of all layer predictions
            'exact_recon'    — np.ndarray, sum of all low-pass signals (perfect reconstruction)
            'final_residual' — np.ndarray, what's left after all layers
            'losses'         — list of loss curves
            'params'         — list of dicts with learnt parameters
        """
        n = len(close)
        residual = close.astype(np.float64).copy()

        self.layers = []
        self.layer_phi_atrs = []
        self.layer_predictions = []
        self.lowpass_signals = []
        self.training_losses = []

        for k, cfg in enumerate(self.layer_configs):
            n_harmonics = cfg.get('n_harmonics', 4)

            if self.verbose:
                print(f"\n{'='*70}")
                print(f"  LAYER {k+1}/{len(self.layer_configs)}: {cfg['label']}")
                print(f"  EMA span={cfg['ema_span']}, ATR period={cfg['atr_period']}, "
                      f"LR={cfg['lr']}, Epochs={cfg['epochs']}, "
                      f"Harmonics={n_harmonics}")
                print(f"  Residual std={np.std(residual):.8f}, "
                      f"range=[{np.min(residual):.6f}, {np.max(residual):.6f}]")
                print(f"{'='*70}")

            # ----- Step 1: Compute ATR integral at this scale -----
            phi_atr_np = compute_atr(high, low, close, period=cfg['atr_period'])
            
            # --- [NOVO V2] Feature extraction for the PINN ---
            atr_val_np = ema_lowpass(
                np.maximum(high - low, np.maximum(np.abs(high - np.roll(close, 1)), 
                                                  np.abs(low - np.roll(close, 1)))), 
                span=cfg['atr_period']
            )
            # Roll fix for first element
            tr_first = high[0] - low[0]
            atr_val_np[0] = tr_first
            
            pinn_features = extract_pinn_features(timestamps_str, atr_val_np, phi_atr_np)

            # ----- Step 2: Zero-phase low-pass of the residual -----
            lowpass = ema_zero_phase(residual, span=cfg['ema_span'])

            # Estimate initial frequency and amplitude from the low-pass
            init_amp = (np.max(lowpass) - np.min(lowpass)) / 2.0
            mean_val = np.mean(lowpass)
            centered = lowpass - mean_val
            zero_crossings = np.sum(np.abs(np.diff(np.sign(centered))) > 0)
            init_freq = max(zero_crossings / 2.0, 1.0)

            if self.verbose:
                print(f"  Init hints: amp={init_amp:.6f}, freq={init_freq:.1f}, "
                      f"zero_crossings={zero_crossings}")
                print(f"  Low-pass range: [{np.min(lowpass):.6f}, {np.max(lowpass):.6f}]")

            # ----- Step 3: Create the PINN multi-harmonic layer -----
            layer = PINNWeierstrassWaveLayer(
                n_harmonics=n_harmonics,
                init_freq_hint=init_freq,
                init_amp_hint=init_amp,
            )

            # ----- Step 4: Train against the low-pass signal using PINN feats -----
            target_tensor = torch.tensor(lowpass, dtype=torch.float64)
            losses = self._train_layer(layer, pinn_features, target_tensor, cfg)

            # ----- Step 5: Freeze -----
            for param in layer.parameters():
                param.requires_grad = False

            # ----- Step 6: Get the trained prediction -----
            with torch.no_grad():
                prediction = layer.forward(pinn_features).numpy()

            # Measure fit quality of the TRAINED model vs the low-pass
            fit_mse = np.mean((lowpass - prediction) ** 2)

            if self.verbose:
                params = layer.get_params_dict()
                amps_str = ", ".join(f"{a:.5f}" for a in params['base_amplitudes'])
                freqs_str = ", ".join(f"{f:.2f}" for f in params['base_frequencies'])
                print(f"  Base amplitudes: [{amps_str}]")
                print(f"  Base frequencies: [{freqs_str}]")
                print(f"  DC bias: {params['dc_bias']:.6f}")
                print(f"  Fit MSE (layer vs lowpass): {fit_mse:.10f}")

            # Store results
            self.layers.append(layer)
            self.layer_phi_atrs.append(phi_atr_np)
            self.layer_predictions.append(prediction)
            self.lowpass_signals.append(lowpass)
            self.training_losses.append(losses)

            # ----- Step 7: EXACT detrending via low-pass subtraction -----
            # This is the key: subtract the LOW-PASS, not the trained prediction.
            # The residual chain is therefore mathematically perfect.
            residual = residual - lowpass

            if self.verbose:
                print(f"  Residual after detrending: std={np.std(residual):.8f}, "
                      f"max_abs={np.max(np.abs(residual)):.8f}")

        # Build reconstruction from trained layers
        reconstruction = np.sum(self.layer_predictions, axis=0)

        # Build exact reconstruction from low-pass signals
        exact_recon = np.sum(self.lowpass_signals, axis=0)

        # Collect parameters
        params = [l.get_params_dict() for l in self.layers]

        return {
            'layers': self.layers,
            'predictions': self.layer_predictions,
            'lowpass_signals': self.lowpass_signals,
            'reconstruction': reconstruction,
            'exact_recon': exact_recon,
            'final_residual': residual,
            'losses': self.training_losses,
            'params': params,
        }

    def _train_layer(self, layer: PINNWeierstrassWaveLayer,
                     pinn_features: torch.Tensor, target: torch.Tensor,
                     cfg: dict) -> list[float]:
        """Train a single PINNWeierstrassWaveLayer with Adam + cosine annealing."""
        optimizer = torch.optim.Adam(layer.parameters(), lr=cfg['lr'])
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=cfg['epochs'], eta_min=cfg['lr'] * 0.01)
        criterion = nn.MSELoss()

        losses = []
        log_interval = max(cfg['epochs'] // 10, 1)

        for epoch in range(cfg['epochs']):
            optimizer.zero_grad()
            pred = layer.forward(pinn_features)
            loss = criterion(pred, target)
            loss.backward()
            optimizer.step()
            scheduler.step()

            loss_val = loss.item()
            losses.append(loss_val)

            if self.verbose and (epoch % log_interval == 0 or epoch == cfg['epochs'] - 1):
                print(f"    Epoch {epoch:>5d}/{cfg['epochs']}  |  "
                      f"MSE = {loss_val:.10f}")

        return losses

    def save_weights(self, filepath: str, layer_configs: list,
                     phi_atr_bounds=None):
        """
        Serialize all learnt parameters + config to JSON.

        This is the ONLY output of the Laboratory (Module 1).
        The Oracle (Module 2) loads this file and projects the equation forward.

        Parameters
        ----------
        filepath      : str — path to save the JSON file.
        layer_configs : list — the original LAYER_CONFIGS used for training.
        phi_atr_bounds: optional list of dicts with {'phi_min', 'phi_max'}
                        per layer, for denormalising ATR projections.
        """
        payload = {
            "version": 3,
            "n_layers": len(self.layers),
            "layers": [],
        }

        for k, layer in enumerate(self.layers):
            params = layer.get_params_dict()
            cfg = layer_configs[k] if k < len(layer_configs) else {}

            layer_data = {
                "label": cfg.get('label', f'Layer_{k}'),
                "ema_span": cfg.get('ema_span', 0),
                "atr_period": cfg.get('atr_period', 0),
                "n_harmonics": params['n_harmonics'],
                "base_amplitudes": params['base_amplitudes'],
                "base_frequencies": params['base_frequencies'],
                "base_phases": params['base_phases'],
                "dc_bias": params['dc_bias'],
                "mlp_w1": params['mlp_w1'],
                "mlp_b1": params['mlp_b1'],
                "mlp_w2": params['mlp_w2'],
                "mlp_b2": params['mlp_b2'],
                "mlp_w3": params['mlp_w3'],
                "mlp_b3": params['mlp_b3'],
            }

            # Store ATR normalisation bounds if available
            if phi_atr_bounds and k < len(phi_atr_bounds):
                layer_data["phi_atr_min"] = phi_atr_bounds[k]['phi_min']
                layer_data["phi_atr_max"] = phi_atr_bounds[k]['phi_max']

            payload["layers"].append(layer_data)

        with open(filepath, 'w') as f:
            json.dump(payload, f, indent=2)

        if self.verbose:
            print(f"  Weights saved to: {filepath}")


def load_weights(filepath: str) -> dict:
    """
    Load serialised Weierstrass weights from JSON.

    Returns the raw dict. The Oracle uses this directly —
    no need to reconstruct nn.Module objects for inference.
    """
    with open(filepath, 'r') as f:
        return json.load(f)


def evaluate_wave_pinn(params: dict, pinn_features_1d: np.ndarray) -> float:
    """
    Evaluate a single PINN layer's wave equation using Numpy only.

    This performs the MLP forward pass manually:
      1. mlp_out = W3 * tanh(W2 * tanh(W1 * x + b1) + b2) + b3
      2. Extract delta_A, delta_f, delta_phi
      3. Compute dynamic A(t), f(t), phi(t)
      4. y = Σ A_h · sin(2π · f_h · φ + phase_h) + b

    This guarantees the Oracle operates purely in NumPy, with 0 PyTorch overhead.

    Parameters
    ----------
    params           : dict — one layer from the weights JSON.
    pinn_features_1d : np.ndarray — 1D array of length 6: 
                       [phi_atr, atr_norm, sin_h, cos_h, sin_dow, cos_dow]

    Returns
    -------
    y : float — the wave's modulated value at this current state.
    """
    x = pinn_features_1d
    
    # MLP Forward Pass (NumPy)
    w1 = np.array(params['mlp_w1'])
    b1 = np.array(params['mlp_b1'])
    h1 = np.tanh(np.dot(w1, x) + b1)
    
    w2 = np.array(params['mlp_w2'])
    b2 = np.array(params['mlp_b2'])
    h2 = np.tanh(np.dot(w2, h1) + b2)
    
    w3 = np.array(params['mlp_w3'])
    b3 = np.array(params['mlp_b3'])
    deltas = np.dot(w3, h2) + b3
    
    n_h = params['n_harmonics']
    delta_A   = deltas[0 : n_h]
    delta_f   = deltas[n_h : 2*n_h]
    delta_phi = deltas[2*n_h : 3*n_h]
    
    # Base params
    base_A = np.array(params['base_amplitudes'])
    base_f = np.array(params['base_frequencies'])
    base_phi = np.array(params['base_phases'])
    
    # Dynamic modulations exactly matching PyTorch code:
    A_dynamic = base_A * (1.0 + 0.5 * np.tanh(delta_A))
    f_dynamic = base_f * (1.0 + 0.2 * np.tanh(delta_f))
    phi_dynamic = base_phi + (math.pi/2.0) * np.tanh(delta_phi)
    
    phi_atr = x[0]
    
    y = params['dc_bias']
    for h in range(n_h):
        y += A_dynamic[h] * math.sin(2.0 * math.pi * f_dynamic[h] * phi_atr + phi_dynamic[h])
        
    return float(y)

