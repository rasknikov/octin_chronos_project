"""
Weierstrass Decomposition — Runner Script (v3)
===============================================
Loads EURUSD H1 data (≥1999), runs the greedy decomposition, prints results,
and saves diagnostic plots.

Usage:
    cd d:\\OCTIN\\octin_labs\\lab_axis_00
    venv\\Scripts\\python.exe 06_WEIERSTRASS_ENGINE\\run_decomposition.py
"""

import sys
import os
import time
import numpy as np

# ---- Ensure this module's directory is importable ----
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from config import LAYER_CONFIGS
from weierstrass_engine import GreedyWeierstrassDecomposer


# ============================================================================
# DATA LOADING
# ============================================================================

def load_eurusd_from_1999(csv_path: str) -> dict:
    """Load EURUSD H1 OHLC from CSV, filtering for rows ≥ 1999-01-01."""
    print(f"Loading data from: {csv_path}")

    timestamps = []
    opens, highs, lows, closes = [], [], [], []

    with open(csv_path, 'r') as f:
        header = f.readline()
        for line in f:
            parts = line.strip().split(',')
            if len(parts) < 7:
                continue
            ts = parts[0]
            if ts < '1999':
                continue
            timestamps.append(ts)
            opens.append(float(parts[3]))
            highs.append(float(parts[4]))
            lows.append(float(parts[5]))
            closes.append(float(parts[6]))

    data = {
        'timestamp': timestamps,
        'open': np.array(opens, dtype=np.float64),
        'high': np.array(highs, dtype=np.float64),
        'low': np.array(lows, dtype=np.float64),
        'close': np.array(closes, dtype=np.float64),
    }
    print(f"  Loaded {len(timestamps)} rows (from {timestamps[0]} to {timestamps[-1]})")
    return data


# ============================================================================
# PLOTTING
# ============================================================================

def save_reconstruction_plot(data: dict, result: dict, output_path: str):
    """Save a plot of original price vs reconstruction (trained + exact)."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    n = len(data['close'])
    x = np.arange(n)

    fig, axes = plt.subplots(3, 1, figsize=(22, 14), sharex=True,
                             gridspec_kw={'height_ratios': [3, 1, 1]})

    # Top: Original vs Trained Reconstruction
    axes[0].plot(x, data['close'], color='#555555', linewidth=0.4,
                 alpha=0.7, label='Original EURUSD Close')
    axes[0].plot(x, result['reconstruction'], color='#FF4444', linewidth=0.5,
                 alpha=0.9, label='Trained Weierstrass Reconstruction')
    axes[0].plot(x, result['exact_recon'], color='#22AA44', linewidth=0.5,
                 alpha=0.8, label='Exact Low-Pass Reconstruction', linestyle='--')
    axes[0].set_title('EURUSD H1 — Weierstrass Decomposition v3',
                      fontsize=14, fontweight='bold')
    axes[0].set_ylabel('Price')
    axes[0].legend(loc='upper left', fontsize=9)
    axes[0].grid(True, alpha=0.3)

    # Middle: Trained reconstruction error
    train_err = data['close'] - result['reconstruction']
    axes[1].plot(x, train_err, color='#E63946', linewidth=0.3, alpha=0.8)
    axes[1].axhline(0, color='black', linewidth=0.5, linestyle='--')
    axes[1].set_title('Trained Reconstruction Error', fontsize=11)
    axes[1].set_ylabel('Error')
    axes[1].grid(True, alpha=0.3)

    # Bottom: Final Residual (from exact detrending chain)
    axes[2].plot(x, result['final_residual'], color='#2266AA', linewidth=0.3,
                 alpha=0.8)
    axes[2].axhline(0, color='black', linewidth=0.5, linestyle='--')
    axes[2].set_title('Final Residual (exact detrending chain)',
                      fontsize=11)
    axes[2].set_ylabel('Residual')
    axes[2].set_xlabel('Bar Index (H1)')
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n  Reconstruction plot saved: {output_path}")


def save_layer_waveforms_plot(result: dict, configs: list, output_path: str):
    """Save a stacked plot showing each layer's individual waveform."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    k = len(result['predictions'])
    fig, axes = plt.subplots(k, 1, figsize=(22, 3 * k), sharex=True)
    if k == 1:
        axes = [axes]

    colors = ['#E63946', '#457B9D', '#2A9D8F', '#E9C46A',
              '#F4A261', '#264653', '#A855F7', '#6B7280']

    for i in range(k):
        pred = result['predictions'][i]
        lp = result['lowpass_signals'][i]
        n = len(pred)
        x = np.arange(n)
        c = colors[i % len(colors)]

        # Plot both the exact low-pass and the trained approximation
        axes[i].plot(x, lp, color='#AAAAAA', linewidth=0.3, alpha=0.7,
                     label='Exact low-pass')
        axes[i].plot(x, pred, color=c, linewidth=0.5, alpha=0.9,
                     label='Trained')
        axes[i].axhline(0, color='black', linewidth=0.3, linestyle='--')

        label = configs[i]['label']
        params = result['params'][i]
        n_h = params.get('n_harmonics', 1)
        dom_amp = max(params['amplitudes'])
        f_min = min(params['frequencies'])
        f_max = max(params['frequencies'])
        title_str = (f"h={n_h}, A_max={dom_amp:.5f}, "
                     f"f=[{f_min:.1f}–{f_max:.1f}], "
                     f"b={params['dc_bias']:.5f}")
        axes[i].set_ylabel(f'{label}', fontsize=9)
        axes[i].set_title(title_str, fontsize=8, loc='right')
        axes[i].grid(True, alpha=0.2)
        if i == 0:
            axes[i].legend(fontsize=7, loc='upper right')

    axes[-1].set_xlabel('Bar Index (H1)')
    fig.suptitle('Weierstrass Layer Waveforms — Trained vs Exact (Macro → Micro)',
                 fontsize=14, fontweight='bold', y=1.01)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Layer waveforms plot saved: {output_path}")


def save_loss_curves_plot(result: dict, configs: list, output_path: str):
    """Save a grid of training loss curves, one per layer."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    k = len(result['losses'])
    cols = min(k, 4)
    rows = (k + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(5 * cols, 4 * rows))
    if rows == 1 and cols == 1:
        axes = np.array([axes])
    axes = np.array(axes).flatten()

    for i in range(k):
        axes[i].plot(result['losses'][i], color='#E63946', linewidth=0.5)
        axes[i].set_title(configs[i]['label'], fontsize=10)
        axes[i].set_xlabel('Epoch')
        axes[i].set_ylabel('MSE Loss')
        axes[i].set_yscale('log')
        axes[i].grid(True, alpha=0.3)

    for j in range(k, len(axes)):
        axes[j].set_visible(False)

    fig.suptitle('Training Loss Curves (per Layer)', fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Loss curves plot saved: {output_path}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
    CSV_PATH = os.path.join(PROJECT_ROOT, '01_DATALAKE', 'eurusd_h1_ohlc.csv')
    OUTPUT_DIR = SCRIPT_DIR

    data = load_eurusd_from_1999(CSV_PATH)

    print(f"\nStarting Greedy Weierstrass Decomposition v3 ({len(LAYER_CONFIGS)} layers)")
    print(f"Total bars: {len(data['close'])}")
    t_start = time.time()

    decomposer = GreedyWeierstrassDecomposer(
        layer_configs=LAYER_CONFIGS,
        verbose=True,
    )
    result = decomposer.decompose(
        close=data['close'],
        high=data['high'],
        low=data['low'],
        timestamps_str=data['timestamp']
    )

    elapsed = time.time() - t_start
    print(f"\n{'='*70}")
    print(f"  DECOMPOSITION COMPLETE in {elapsed:.1f} seconds")
    print(f"{'='*70}")

    # ---- Save Weights (Module 1 output) ----
    from weierstrass_engine import compute_atr
    phi_atr_bounds = []
    for cfg in LAYER_CONFIGS:
        phi_raw = compute_atr(data['high'], data['low'], data['close'],
                              period=cfg['atr_period'])
        # compute_atr returns normalised [0,1], so we need the raw cumsum bounds
        # Re-compute raw cumsum for bounds
        from weierstrass_engine import ema_lowpass as _ema
        n_bars = len(data['high'])
        tr = np.empty(n_bars, dtype=np.float64)
        tr[0] = data['high'][0] - data['low'][0]
        for i in range(1, n_bars):
            hl = data['high'][i] - data['low'][i]
            hc = abs(data['high'][i] - data['close'][i-1])
            lc = abs(data['low'][i] - data['close'][i-1])
            tr[i] = max(hl, hc, lc)
        atr_raw = _ema(tr, span=cfg['atr_period'])
        cumsum_raw = np.cumsum(atr_raw)
        phi_atr_bounds.append({
            'phi_min': float(cumsum_raw[0]),
            'phi_max': float(cumsum_raw[-1]),
        })

    weights_path = os.path.join(OUTPUT_DIR, 'pesos_weierstrass.json')
    decomposer.save_weights(weights_path, LAYER_CONFIGS, phi_atr_bounds)
    print(f"  Weights saved: {weights_path}")

    # ---- Metrics ----
    original = data['close']

    # Trained reconstruction
    recon = result['reconstruction']
    mse_train = np.mean((original - recon) ** 2)
    ss_res_train = np.sum((original - recon) ** 2)
    ss_tot = np.sum((original - np.mean(original)) ** 2)
    r2_train = 1.0 - (ss_res_train / ss_tot) if ss_tot > 0 else 0.0

    # Exact reconstruction (sum of low-pass signals)
    exact = result['exact_recon']
    mse_exact = np.mean((original - exact) ** 2)
    ss_res_exact = np.sum((original - exact) ** 2)
    r2_exact = 1.0 - (ss_res_exact / ss_tot) if ss_tot > 0 else 0.0

    residual = result['final_residual']

    print(f"\n  TRAINED RECONSTRUCTION:")
    print(f"    MSE:  {mse_train:.10f}")
    print(f"    R²:   {r2_train:.8f}")

    print(f"\n  EXACT RECONSTRUCTION (sum of low-pass signals):")
    print(f"    MSE:  {mse_exact:.10f}")
    print(f"    R²:   {r2_exact:.8f}")

    print(f"\n  FINAL RESIDUAL:")
    print(f"    Std Dev:    {np.std(residual):.8f}")
    print(f"    Max Abs:    {np.max(np.abs(residual)):.8f}")
    print(f"    Mean:       {np.mean(residual):.8f}")

    print(f"\n  Per-Layer Parameters:")
    for i, p in enumerate(result['params']):
        cfg = LAYER_CONFIGS[i]
        n_h = p.get('n_harmonics', 1)
        amps = p.get('base_amplitudes', p.get('amplitudes', [0]))
        freqs = p.get('base_frequencies', p.get('frequencies', [0]))
        # Fit quality: how well the trained layer matches the low-pass
        lp = result['lowpass_signals'][i]
        pred = result['predictions'][i]
        fit_r2 = 1.0 - (np.sum((lp - pred)**2) / (np.sum((lp - np.mean(lp))**2) + 1e-30))
        
        a_max = max(amps) if isinstance(amps, (list, tuple, np.ndarray)) and len(amps) > 0 else 0.0
        f_min = min(freqs) if isinstance(freqs, (list, tuple, np.ndarray)) and len(freqs) > 0 else 0.0
        f_max = max(freqs) if isinstance(freqs, (list, tuple, np.ndarray)) and len(freqs) > 0 else 0.0
        
        print(f"    {cfg['label']:25s}  |  h={n_h}  "
              f"A_max={a_max:.6f}  f=[{f_min:.1f}–{f_max:.1f}]  "
              f"b={p.get('dc_bias', 0.0):.6f}  fit_R²={fit_r2:.6f}")

    # ---- Plots ----
    print(f"\nGenerating plots...")
    save_reconstruction_plot(
        data, result,
        os.path.join(OUTPUT_DIR, 'reconstruction_plot.png')
    )
    save_layer_waveforms_plot(
        result, LAYER_CONFIGS,
        os.path.join(OUTPUT_DIR, 'layer_waveforms.png')
    )
    save_loss_curves_plot(
        result, LAYER_CONFIGS,
        os.path.join(OUTPUT_DIR, 'loss_curves.png')
    )

    print(f"\n  ALL DONE. Total time: {elapsed:.1f}s")


if __name__ == '__main__':
    main()
