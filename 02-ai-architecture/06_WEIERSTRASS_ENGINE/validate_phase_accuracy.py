"""
Weierstrass Phase Accuracy Validator
=====================================
Proves that the Weierstrass layers capture DIRECTION (Phase) correctly,
even when R² is negative (because R² punishes amplitude mismatch, not timing).

Metrics
-------
1. Directional Accuracy (DA): % of bars where wave derivative sign matches
   actual signal derivative sign.
2. Directional Accuracy at Phase Crossings: DA measured only at the bars
   where the wave crosses zero (the most informative moments — inflection points).
3. Expected DA of a random predictor: 50% (coin flip).

If DA > 50% consistently, the wave has captured real phase structure
from the market, even if the amplitude is wrong.

Usage:
    cd d:\\OCTIN\\octin_labs\\lab_axis_00
    venv\\Scripts\\python.exe 06_WEIERSTRASS_ENGINE\\validate_phase_accuracy.py
"""

import sys
import os
import time
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from config import LAYER_CONFIGS
from weierstrass_engine import GreedyWeierstrassDecomposer


# ============================================================================
# DATA LOADING (copied from run_decomposition.py for standalone use)
# ============================================================================

def load_eurusd_from_1999(csv_path: str) -> dict:
    """Load EURUSD H1 OHLC from CSV, filtering for rows >= 1999-01-01."""
    print(f"Loading data from: {csv_path}")
    timestamps, opens, highs, lows, closes = [], [], [], [], []
    with open(csv_path, 'r') as f:
        f.readline()  # skip header
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
    print(f"  Loaded {len(timestamps)} rows ({timestamps[0]} to {timestamps[-1]})")
    return data


# ============================================================================
# DIRECTIONAL ACCURACY COMPUTATION
# ============================================================================

def compute_directional_accuracy(wave: np.ndarray, signal: np.ndarray,
                                 lookahead: int = 1) -> dict:
    """
    Compute Directional Accuracy between a wave prediction and the actual signal.

    The wave's derivative at time t predicts the direction.
    The signal's movement from t to t+lookahead is the reality.

    Parameters
    ----------
    wave   : 1-D array — the trained Weierstrass wave prediction.
    signal : 1-D array — the actual low-pass signal at that scale.
    lookahead : int — how many bars forward to measure direction (default 1).

    Returns
    -------
    dict with:
        'total_bars'     : number of bars evaluated
        'directional_acc': fraction of bars where wave and signal agree on direction
        'hits'           : count of directional matches
        'misses'         : count of directional mismatches
        'neutral'        : count of bars where one or both have zero derivative
    """
    n = min(len(wave), len(signal)) - lookahead

    # Wave derivative: sign(wave[t] - wave[t-1])
    wave_dir = np.sign(np.diff(wave[:n+1]))  # length = n

    # Signal future direction: sign(signal[t+lookahead] - signal[t])
    signal_dir = np.sign(signal[lookahead:n+lookahead] - signal[:n])  # length = n

    # Mask: only count bars where both have a non-zero direction
    active = (wave_dir != 0) & (signal_dir != 0)
    n_active = np.sum(active)

    if n_active == 0:
        return {
            'total_bars': n,
            'active_bars': 0,
            'directional_acc': 0.5,
            'hits': 0,
            'misses': 0,
            'neutral': n,
        }

    hits = np.sum((wave_dir[active] == signal_dir[active]))
    misses = n_active - hits

    return {
        'total_bars': int(n),
        'active_bars': int(n_active),
        'directional_acc': float(hits / n_active),
        'hits': int(hits),
        'misses': int(misses),
        'neutral': int(n - n_active),
    }


def compute_crossing_accuracy(wave: np.ndarray, signal: np.ndarray,
                              lookahead: int = 1) -> dict:
    """
    Compute Directional Accuracy ONLY at wave phase crossings (zero-crossings).

    These are the moments where the wave reverses its derivative — the inflection
    points where a trader would enter/exit. If the wave's direction at these
    moments matches reality, the Phase is correct.

    Parameters
    ----------
    wave   : 1-D array — the trained Weierstrass wave prediction.
    signal : 1-D array — the actual low-pass signal at that scale.
    lookahead : int — bars forward to measure direction.

    Returns
    -------
    dict with crossing accuracy metrics.
    """
    n = min(len(wave), len(signal)) - lookahead

    # Wave derivative
    wave_diff = np.diff(wave[:n+1])  # length = n

    # Find zero-crossings of the wave (sign changes in derivative)
    wave_sign = np.sign(wave_diff)
    crossings = np.where(np.abs(np.diff(wave_sign)) > 0)[0]  # indices where sign flips

    if len(crossings) == 0:
        return {
            'n_crossings': 0,
            'crossing_acc': 0.5,
            'hits': 0,
            'misses': 0,
        }

    # At each crossing, check if the NEW wave direction matches reality
    # crossing[i]+1 is the bar AFTER the sign flip
    crossing_bars = crossings + 1
    crossing_bars = crossing_bars[crossing_bars < n]  # bounds check

    wave_dir_at_cross = np.sign(wave_diff[crossing_bars])
    signal_move = np.sign(signal[crossing_bars + lookahead] - signal[crossing_bars])

    # Only count active
    active = (wave_dir_at_cross != 0) & (signal_move != 0)
    n_active = np.sum(active)

    if n_active == 0:
        return {
            'n_crossings': len(crossings),
            'active_crossings': 0,
            'crossing_acc': 0.5,
            'hits': 0,
            'misses': 0,
        }

    hits = np.sum(wave_dir_at_cross[active] == signal_move[active])

    return {
        'n_crossings': int(len(crossings)),
        'active_crossings': int(n_active),
        'crossing_acc': float(hits / n_active),
        'hits': int(hits),
        'misses': int(n_active - hits),
    }


def compute_multi_horizon_da(wave: np.ndarray, signal: np.ndarray,
                             horizons: list[int]) -> dict:
    """
    Compute Directional Accuracy at multiple lookahead horizons.

    This reveals whether the wave captures direction that persists over time.
    """
    results = {}
    for h in horizons:
        da = compute_directional_accuracy(wave, signal, lookahead=h)
        results[h] = da['directional_acc']
    return results


# ============================================================================
# PLOTTING
# ============================================================================

def save_phase_accuracy_plot(layer_results: list, configs: list, output_path: str):
    """Save a comprehensive phase accuracy dashboard."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    k = len(layer_results)

    fig, axes = plt.subplots(1, 3, figsize=(22, 7))

    labels = [c['label'].replace('—', '-') for c in configs]
    short_labels = [f"L{i+1}" for i in range(k)]

    # ---- Panel 1: Directional Accuracy by Layer ----
    da_values = [r['da']['directional_acc'] * 100 for r in layer_results]
    colors = ['#22AA44' if v > 50 else '#E63946' for v in da_values]
    bars = axes[0].bar(short_labels, da_values, color=colors, alpha=0.85, edgecolor='black',
                       linewidth=0.5)
    axes[0].axhline(50, color='#888888', linewidth=1.5, linestyle='--', label='Random (50%)')
    axes[0].set_ylabel('Directional Accuracy (%)', fontsize=11)
    axes[0].set_title('Directional Accuracy — All Bars', fontsize=13, fontweight='bold')
    axes[0].set_ylim(40, max(max(da_values) + 5, 55))
    axes[0].legend(fontsize=9)
    axes[0].grid(True, alpha=0.3, axis='y')
    for bar, val in zip(bars, da_values):
        axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                     f'{val:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')

    # ---- Panel 2: Crossing Accuracy by Layer ----
    ca_values = [r['crossing']['crossing_acc'] * 100 for r in layer_results]
    n_cross = [r['crossing']['n_crossings'] for r in layer_results]
    colors2 = ['#22AA44' if v > 50 else '#E63946' for v in ca_values]
    bars2 = axes[1].bar(short_labels, ca_values, color=colors2, alpha=0.85,
                        edgecolor='black', linewidth=0.5)
    axes[1].axhline(50, color='#888888', linewidth=1.5, linestyle='--', label='Random (50%)')
    axes[1].set_ylabel('Directional Accuracy (%)', fontsize=11)
    axes[1].set_title('Directional Accuracy — At Phase Crossings Only', fontsize=13,
                      fontweight='bold')
    axes[1].set_ylim(40, max(max(ca_values) + 5, 55))
    axes[1].legend(fontsize=9)
    axes[1].grid(True, alpha=0.3, axis='y')
    for bar, val, nc in zip(bars2, ca_values, n_cross):
        axes[1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                     f'{val:.1f}%\n({nc} cross)', ha='center', va='bottom',
                     fontsize=8, fontweight='bold')

    # ---- Panel 3: Multi-Horizon DA (lines for each layer) ----
    horizon_colors = ['#E63946', '#457B9D', '#2A9D8F', '#E9C46A',
                      '#F4A261', '#264653', '#A855F7', '#6B7280']
    for i, r in enumerate(layer_results):
        horizons = sorted(r['multi_horizon'].keys())
        values = [r['multi_horizon'][h] * 100 for h in horizons]
        axes[2].plot(horizons, values, marker='o', markersize=4, linewidth=1.5,
                     color=horizon_colors[i % len(horizon_colors)],
                     alpha=0.85, label=short_labels[i])
    axes[2].axhline(50, color='#888888', linewidth=1.5, linestyle='--')
    axes[2].set_xlabel('Lookahead Horizon (bars)', fontsize=11)
    axes[2].set_ylabel('Directional Accuracy (%)', fontsize=11)
    axes[2].set_title('DA vs Lookahead Horizon', fontsize=13, fontweight='bold')
    axes[2].legend(fontsize=8, ncol=2, loc='upper right')
    axes[2].grid(True, alpha=0.3)
    axes[2].set_ylim(40, None)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n  Phase accuracy plot saved: {output_path}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
    CSV_PATH = os.path.join(PROJECT_ROOT, '01_DATALAKE', 'eurusd_h1_ohlc.csv')
    OUTPUT_DIR = SCRIPT_DIR

    data = load_eurusd_from_1999(CSV_PATH)

    # ---- Run decomposition ----
    print(f"\nRunning decomposition ({len(LAYER_CONFIGS)} layers)...")
    t_start = time.time()

    decomposer = GreedyWeierstrassDecomposer(
        layer_configs=LAYER_CONFIGS,
        verbose=False,  # quiet mode for validation
    )
    result = decomposer.decompose(
        close=data['close'],
        high=data['high'],
        low=data['low'],
    )

    elapsed = time.time() - t_start
    print(f"  Decomposition done in {elapsed:.1f}s")

    # ---- Phase Accuracy Validation ----
    print(f"\n{'='*70}")
    print(f"  PHASE ACCURACY VALIDATION (Directional Accuracy)")
    print(f"  Random baseline: 50.0%")
    print(f"{'='*70}")

    horizons = [1, 2, 3, 5, 8, 13, 21]  # Fibonacci-spaced lookaheads

    layer_results = []

    for i, cfg in enumerate(LAYER_CONFIGS):
        wave = result['predictions'][i]
        signal = result['lowpass_signals'][i]

        # Standard DA at 1-bar lookahead
        da = compute_directional_accuracy(wave, signal, lookahead=1)

        # Crossing-only DA
        crossing = compute_crossing_accuracy(wave, signal, lookahead=1)

        # Multi-horizon DA
        multi_da = compute_multi_horizon_da(wave, signal, horizons)

        layer_results.append({
            'da': da,
            'crossing': crossing,
            'multi_horizon': multi_da,
        })

        # Print results
        da_pct = da['directional_acc'] * 100
        ca_pct = crossing['crossing_acc'] * 100
        edge = da_pct - 50.0

        marker = "✅" if da_pct > 50.5 else ("⚠️ " if da_pct > 49.5 else "❌")

        print(f"\n  {cfg['label']}")
        print(f"    DA (all bars):       {da_pct:6.2f}%  ({da['hits']}/{da['active_bars']} hits)  "
              f"Edge: {edge:+.2f}pp  {marker}")
        print(f"    DA (at crossings):   {ca_pct:6.2f}%  ({crossing['hits']}/{crossing.get('active_crossings', 0)} hits, "
              f"{crossing['n_crossings']} crossings)")

        horizon_str = "    DA by horizon:       "
        for h in horizons:
            horizon_str += f"{h}h={multi_da[h]*100:.1f}%  "
        print(horizon_str)

    # ---- Summary Table ----
    print(f"\n{'='*70}")
    print(f"  SUMMARY")
    print(f"{'='*70}")
    print(f"  {'Layer':<26s} {'DA(1bar)':>10s} {'DA(cross)':>10s} {'DA(5bar)':>10s} {'DA(13bar)':>10s}  {'Edge(1h)':>10s}")
    print(f"  {'-'*26} {'-'*10} {'-'*10} {'-'*10} {'-'*10}  {'-'*10}")
    for i, cfg in enumerate(LAYER_CONFIGS):
        r = layer_results[i]
        da1 = r['da']['directional_acc'] * 100
        dac = r['crossing']['crossing_acc'] * 100
        da5 = r['multi_horizon'][5] * 100
        da13 = r['multi_horizon'][13] * 100
        edge = da1 - 50.0
        print(f"  {cfg['label']:<26s} {da1:>9.2f}% {dac:>9.2f}% {da5:>9.2f}% {da13:>9.2f}%  {edge:>+9.2f}pp")

    # ---- Statistical Significance ----
    print(f"\n  STATISTICAL SIGNIFICANCE (binomial test, H0: DA = 50%):")
    for i, cfg in enumerate(LAYER_CONFIGS):
        r = layer_results[i]
        n = r['da']['active_bars']
        k = r['da']['hits']
        # z-test for proportion
        p_hat = k / n if n > 0 else 0.5
        z = (p_hat - 0.5) / (0.5 / (n ** 0.5)) if n > 0 else 0.0
        # Two-tailed p-value approximation
        # Using normal CDF approximation
        if abs(z) > 6:
            p_val_str = "< 1e-9"
        elif abs(z) > 3.29:
            p_val_str = "< 0.001"
        elif abs(z) > 2.58:
            p_val_str = "< 0.01"
        elif abs(z) > 1.96:
            p_val_str = "< 0.05"
        else:
            p_val_str = "> 0.05 (NOT significant)"

        sig_marker = "***" if abs(z) > 3.29 else ("**" if abs(z) > 2.58 else ("*" if abs(z) > 1.96 else "ns"))
        print(f"    {cfg['label']:<26s}  z={z:+7.2f}  p {p_val_str}  {sig_marker}")

    # ---- Plot ----
    print(f"\nGenerating phase accuracy plots...")
    save_phase_accuracy_plot(
        layer_results, LAYER_CONFIGS,
        os.path.join(OUTPUT_DIR, 'phase_accuracy.png')
    )

    print(f"\n  VALIDATION COMPLETE.")


if __name__ == '__main__':
    main()
