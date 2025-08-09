"""
Configuration for 07_FRACTAL_FM_ENGINE
"""
import torch

# Base settings
CSV_PATH = '01_DATALAKE/eurusd_h1_ohlc.csv'
WEIGHTS_PATH = '07_FRACTAL_FM_ENGINE/pesos_fm_siren.json'
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

# We use 8 layers of EMA detrending, but each layer is modeled by a SIREN network.
# 
# Layer   EMA Span   ATR Per
# ---------------------------
# L1      20000      ---       (Special macro baseline, maybe just EMA)
# Wait, let's keep it similar to the previous project:
# L1      8000       2000      Multi-Year
# L2      2000       500       Annual
# L3      500        125       Quarterly
# L4      125        30        Monthly
# L5      30         8         Weekly
# L6      8          2         Daily
# L7      2          1         Intraday
# L8      1          1         Micro

LAYER_CONFIGS = [
    # L1: Multi-Year Macro
    {'span': 8000, 'atr_period': 2000, 'hidden_features': 16, 'hidden_layers': 1, 'omega_0': 10.0, 'lr': 0.005, 'epochs': 2000,  'alpha': 1.0, 'beta': 0.5},
    # L2: Annual
    {'span': 2000, 'atr_period': 500,  'hidden_features': 16, 'hidden_layers': 1, 'omega_0': 10.0, 'lr': 0.005, 'epochs': 2000,  'alpha': 1.0, 'beta': 0.5},
    # L3: Quarterly
    {'span': 500,  'atr_period': 125,  'hidden_features': 16, 'hidden_layers': 1, 'omega_0': 30.0, 'lr': 0.005, 'epochs': 1500,  'alpha': 1.0, 'beta': 1.0},
    # L4: Monthly
    {'span': 125,  'atr_period': 30,   'hidden_features': 32, 'hidden_layers': 2, 'omega_0': 30.0, 'lr': 0.002, 'epochs': 1500,  'alpha': 1.0, 'beta': 1.0},
    # L5: Weekly
    {'span': 30,   'atr_period': 8,    'hidden_features': 32, 'hidden_layers': 2, 'omega_0': 50.0, 'lr': 0.002, 'epochs': 1500,  'alpha': 1.0, 'beta': 1.5},
    # L6: Daily
    {'span': 8,    'atr_period': 3,    'hidden_features': 64, 'hidden_layers': 2, 'omega_0': 50.0, 'lr': 0.001, 'epochs': 1000,  'alpha': 1.0, 'beta': 2.0},
    # L7: Intraday
    {'span': 2,    'atr_period': 1,    'hidden_features': 64, 'hidden_layers': 2, 'omega_0': 50.0, 'lr': 0.001, 'epochs': 1000,  'alpha': 1.0, 'beta': 2.0},
    # L8: Micro
    {'span': 1,    'atr_period': 1,    'hidden_features': 128,'hidden_layers': 2, 'omega_0': 100.0,'lr': 0.0005,'epochs': 1000,  'alpha': 1.0, 'beta': 2.0},
]
