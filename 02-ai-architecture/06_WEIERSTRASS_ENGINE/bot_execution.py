"""
Weierstrass Oracle — Bot Execution Module (Module 2) v2
========================================================
Committee Voting Oracle with Layer Hierarchy:

    L4+L5 = COMPASS  (slow layers, determine BUY-only or SELL-only)
    L6+L7 = TRIGGER  (medium layers, must agree with compass to fire)
    L8    = MUTED    (too fast for t+3 projection — 2 radians rotation = noise)

The Oracle has AMNESIA. It retains NO state between calls.
"""

import math
import json
import numpy as np
from weierstrass_engine import evaluate_wave_pinn, extract_pinn_features


def load_weights(filepath: str) -> dict:
    """Load the frozen Weierstrass weights from JSON."""
    with open(filepath, 'r') as f:
        return json.load(f)


def project_layer(layer_params: dict, current_hour: int, current_dow: int,
                   phi_now: float, atr_now: float, atr_range: float,
                   projection_bars: int) -> float:
    """
    Project a single PINN layer forward and return ΔP in price units.
    
    This exact method:
    1. Extracts baseline PINN features for `t_now`
    2. Modifies ONLY the cumulative phase `phi_atr` + `projection_bars * atr_now / atr_range`
       meaning we assume the exact same time-of-day dynamics but shifted phase space.
    3. Calculates ΔP = wave(features_future) - wave(features_now)
    """
    if atr_range > 1e-12:
        phi_step = (projection_bars * atr_now) / atr_range
    else:
        phi_step = 0.0

    # Build features purely in Numpy for max speed (0 PyTorch overhead)
    # [phi_atr, atr_norm, sin_h, cos_h, sin_dow, cos_dow]
    features_now_1d = np.zeros(6, dtype=np.float64)
    features_now_1d[0] = phi_now
    features_now_1d[1] = atr_now / 0.005  # Approximate global ATR max for EURUSD to keep it 0~1
    features_now_1d[2] = math.sin(2.0 * math.pi * current_hour / 24.0)
    features_now_1d[3] = math.cos(2.0 * math.pi * current_hour / 24.0)
    features_now_1d[4] = math.sin(2.0 * math.pi * current_dow / 5.0)
    features_now_1d[5] = math.cos(2.0 * math.pi * current_dow / 5.0)
    
    # Calculate for FUTURE (only advancing time dimension by shifting phase)
    features_future_1d = features_now_1d.copy()
    features_future_1d[0] = phi_now + phi_step

    p_now = evaluate_wave_pinn(layer_params, features_now_1d)
    p_future = evaluate_wave_pinn(layer_params, features_future_1d)
    
    return p_future - p_now


class WeierstrassOracle:
    """
    Committee Voting Oracle.

    Instead of blindly summing all layers, this Oracle uses a hierarchy:
    - COMPASS layers (L4, L5): determine allowed direction
    - TRIGGER layers (L6, L7): must agree with compass to fire
    - MUTED layers (L8): excluded from signal generation

    A trade is generated ONLY when compass and trigger agree.
    """

    # Default layer roles (0-indexed)
    COMPASS_LAYERS = [1, 2]   # L2 (Annual) + L3 (Quarterly)
    TRIGGER_LAYERS = [3, 4]   # L4 (Monthly) + L5 (Weekly)
    MUTED_LAYERS   = [5, 6, 7]  # L6, L7, L8 — too fast for macro prediction

    def __init__(self, weights_path: str,
                 spread_pips: float = 2.0,
                 compass_layers: list = None,
                 trigger_layers: list = None):
        """
        Parameters
        ----------
        weights_path   : path to pesos_weierstrass.json.
        spread_pips    : broker spread in pips.
        compass_layers : indices of compass (direction filter) layers.
        trigger_layers : indices of trigger (execution) layers.
        """
        self.weights = load_weights(weights_path)
        self.n_layers = self.weights['n_layers']
        self.layers = self.weights['layers']
        self.spread = spread_pips
        self.compass_layers = compass_layers or self.COMPASS_LAYERS
        self.trigger_layers = trigger_layers or self.TRIGGER_LAYERS

    def generate_signal(self,
                        current_hour: int,
                        current_dow: int,
                        current_phi_atrs: list,
                        current_atr_values: list,
                        phi_atr_ranges: list,
                        projection_bars: int = 3) -> dict:
        """
        Committee Voting Signal Generation with PINN Features.

        1. Compute ΔP for compass layers → determines allowed direction
        2. Compute ΔP for trigger layers → must agree to fire
        3. If both agree → SIGNAL. Otherwise → NEUTRAL.

        Returns
        -------
        dict with signal, delta_pips, compass_delta, trigger_delta.
        """
        # ----- COMPASS: direction filter -----
        compass_delta = 0.0
        for k in self.compass_layers:
            compass_delta += project_layer(
                self.layers[k], current_hour, current_dow, current_phi_atrs[k],
                current_atr_values[k], phi_atr_ranges[k],
                projection_bars,
            )

        # ----- TRIGGER: execution confirmation -----
        trigger_delta = 0.0
        for k in self.trigger_layers:
            trigger_delta += project_layer(
                self.layers[k], current_hour, current_dow, current_phi_atrs[k],
                current_atr_values[k], phi_atr_ranges[k],
                projection_bars,
            )

        # Convert to pips
        compass_pips = compass_delta / 0.0001
        trigger_pips = trigger_delta / 0.0001
        total_pips = compass_pips + trigger_pips

        # ----- COMMITTEE VOTE -----
        # Compass determines allowed direction
        compass_dir = 1 if compass_pips > 0 else (-1 if compass_pips < 0 else 0)

        # Trigger must agree with compass direction
        trigger_dir = 1 if trigger_pips > 0 else (-1 if trigger_pips < 0 else 0)

        # Both must agree AND total must exceed spread
        if compass_dir != 0 and compass_dir == trigger_dir and abs(total_pips) > self.spread:
            signal = compass_dir
        else:
            signal = 0  # NEUTRAL: committee disagrees or below spread

        return {
            "signal": signal,
            "delta_pips": round(total_pips, 2),
            "compass_pips": round(compass_pips, 2),
            "trigger_pips": round(trigger_pips, 2),
            "compass_dir": compass_dir,
            "trigger_dir": trigger_dir,
        }
