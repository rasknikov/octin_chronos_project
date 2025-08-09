import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import math

class SineLayer(nn.Module):
    """
    Sine activation layer with omega_0.
    y = sin(omega_0 * (Wx + b))
    Initialization according to SIREN paper.
    """
    def __init__(self, in_features, out_features, bias=True,
                 is_first=False, omega_0=30.0):
        super().__init__()
        self.omega_0 = omega_0
        self.is_first = is_first
        
        self.in_features = in_features
        self.linear = nn.Linear(in_features, out_features, bias=bias)
        
        self.init_weights()
    
    def init_weights(self):
        with torch.no_grad():
            if self.is_first:
                # W ~ U(-1 / in_features, 1 / in_features)
                self.linear.weight.uniform_(-1 / self.in_features, 
                                             1 / self.in_features)      
            else:
                # W ~ U(-sqrt(6 / in_features) / omega_0, sqrt(6 / in_features) / omega_0)
                bound = math.sqrt(6 / self.in_features) / self.omega_0
                self.linear.weight.uniform_(-bound, bound)
                
    def forward(self, input):
        return torch.sin(self.omega_0 * self.linear(input))


class FMSiren(nn.Module):
    """
    Fractal FM SIREN Network.
    Takes 1 input feature (phi_atr) and passes it through SIREN blocks.
    The final output is a linear combination of the last SineLayer.
    """
    def __init__(self, in_features=1, hidden_features=32, hidden_layers=2, out_features=1, omega_0=30.0):
        super().__init__()
        
        self.net = []
        
        # First SIREN layer
        self.net.append(SineLayer(in_features, hidden_features, 
                                  is_first=True, omega_0=omega_0))

        # Hidden SIREN layers (Frequency Modulation synthesis)
        for _ in range(hidden_layers):
            self.net.append(SineLayer(hidden_features, hidden_features, 
                                      is_first=False, omega_0=omega_0))

        # Final Linear Combiner (Amplitude A_k and final Bias b_out)
        final_linear = nn.Linear(hidden_features, out_features)
        
        # Initialize final layer weights
        with torch.no_grad():
            final_linear.weight.uniform_(-math.sqrt(6 / hidden_features) / omega_0, 
                                          math.sqrt(6 / hidden_features) / omega_0)
            
        self.net.append(final_linear)
        self.net = nn.Sequential(*self.net)
        
    def forward(self, x):
        return self.net(x)


# =====================================================================
# DATA PROCESSING & MATHEMATICAL PRE-REQUISITES (GREEDY DETRENDING)
# =====================================================================

def compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """Calculate ATR efficiently using numpy."""
    n = len(close)
    tr = np.zeros(n, dtype=np.float64)
    tr[0] = high[0] - low[0]
    
    for i in range(1, n):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i - 1])
        lc = abs(low[i] - close[i - 1])
        tr[i] = max(hl, hc, lc)

    atr = np.zeros(n, dtype=np.float64)
    if n > period:
        atr[period-1] = np.mean(tr[:period])
        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    else:
        atr[:] = np.mean(tr)

    # Fill start with first valid ATR
    for i in range(period - 1):
        atr[i] = atr[period - 1]

    return atr

def ema_zero_phase(series: np.ndarray, span: int) -> np.ndarray:
    """Zero-phase EMA (forward and backward) to prevent lag."""
    if span <= 1:
        return series.copy()
        
    alpha = 2.0 / (span + 1.0)
    
    # Forward pass
    fwd = np.zeros_like(series)
    fwd[0] = series[0]
    for i in range(1, len(series)):
        fwd[i] = (series[i] - fwd[i - 1]) * alpha + fwd[i - 1]
        
    # Backward pass
    bwd = np.zeros_like(series)
    bwd[-1] = fwd[-1]
    for i in range(len(series) - 2, -1, -1):
        bwd[i] = (fwd[i] - bwd[i + 1]) * alpha + bwd[i + 1]
        
    return bwd

def siren_loss_fn(y_pred, y_true, alpha=1.0, beta=1.0):
    """
    Custom Loss Function: MSE - beta * PearsonCorrelation(Delta_y_pred, Delta_y_true)
    Maximizes directionality while maintaining amplitude scale.
    """
    mse = torch.nn.functional.mse_loss(y_pred, y_true)
    
    if beta <= 0.0 or len(y_pred) <= 1:
        return mse
        
    dy_pred = y_pred[1:] - y_pred[:-1]
    dy_true = y_true[1:] - y_true[:-1]
    
    pred_mean = dy_pred.mean()
    true_mean = dy_true.mean()
    
    pred_centered = dy_pred - pred_mean
    true_centered = dy_true - true_mean
    
    cov = (pred_centered * true_centered).sum()
    var_pred = (pred_centered**2).sum()
    var_true = (true_centered**2).sum()
    
    denominator = torch.sqrt(var_pred * var_true) + 1e-8
    pearson_corr = cov / denominator
    
    # We want to maximize positive correlation, so we subtract from the loss
    loss = (alpha * mse) - (beta * pearson_corr)
    return loss, mse.item(), pearson_corr.item()
