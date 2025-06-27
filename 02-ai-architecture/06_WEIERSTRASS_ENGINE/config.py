"""
Weierstrass Decomposition Engine — Layer Configuration v2
==========================================================
Each dict defines one greedy layer, from Macro (layer 0) to Micro (layer 7).

Keys
----
ema_span    : int — EMA smoothing window ("sandpaper grade") for the target.
atr_period  : int — ATR lookback for the volatility integral at this scale.
n_harmonics : int — number of sinusoidal harmonics per layer (mini-Weierstrass bank).
lr          : float — Adam learning rate.
epochs      : int — training iterations for this layer.
label       : str — human-readable label for logs / plots.
"""

LAYER_CONFIGS = [
    # ----- Macro (multi-year trend) -----
    {
        "ema_span": 20_000,
        "atr_period": 5_000,
        "n_harmonics": 6,
        "lr": 0.01,
        "epochs": 4_000,
        "label": "L1 — Multi-Year Macro",
    },
    # ----- Annual cycle -----
    {
        "ema_span": 5_000,
        "atr_period": 2_000,
        "n_harmonics": 6,
        "lr": 0.01,
        "epochs": 4_000,
        "label": "L2 — Annual",
    },
    # ----- Quarterly swing -----
    {
        "ema_span": 1_500,
        "atr_period": 500,
        "n_harmonics": 6,
        "lr": 0.005,
        "epochs": 3_000,
        "label": "L3 — Quarterly",
    },
    # ----- Monthly -----
    {
        "ema_span": 400,
        "atr_period": 200,
        "n_harmonics": 6,
        "lr": 0.005,
        "epochs": 3_000,
        "label": "L4 — Monthly",
    },
    # ----- Weekly -----
    {
        "ema_span": 100,
        "atr_period": 50,
        "n_harmonics": 8,
        "lr": 0.003,
        "epochs": 2_000,
        "label": "L5 — Weekly",
    },
    # ----- Daily -----
    {
        "ema_span": 30,
        "atr_period": 14,
        "n_harmonics": 8,
        "lr": 0.003,
        "epochs": 2_000,
        "label": "L6 — Daily",
    },
    # ----- Intraday -----
    {
        "ema_span": 10,
        "atr_period": 5,
        "n_harmonics": 8,
        "lr": 0.001,
        "epochs": 1_500,
        "label": "L7 — Intraday",
    },
    # ----- Micro-pip -----
    {
        "ema_span": 3,
        "atr_period": 3,
        "n_harmonics": 8,
        "lr": 0.001,
        "epochs": 1_500,
        "label": "L8 — Micro-Pip",
    },
]
