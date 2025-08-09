import time
import json
import numpy as np
import pandas as pd
import torch
from config import CSV_PATH, WEIGHTS_PATH, DEVICE, LAYER_CONFIGS
from siren_engine import FMSiren, compute_atr, ema_zero_phase, siren_loss_fn

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def load_data(path, limit=None):
    df = pd.read_csv(path, sep=',')
    df = df[df['timestamp'] >= '1999-01-01']
    if limit:
        df = df.head(limit)
    high = df['High'].values.astype(np.float64)
    low = df['Low'].values.astype(np.float64)
    close = df['Close'].values.astype(np.float64)
    return high, low, close

def extract_phi_atr(atr_values: np.ndarray) -> np.ndarray:
    """Calculates the cumulative phase coordinate Phi(t)"""
    phi_atr = np.zeros_like(atr_values)
    current_sum = 0.0
    for i in range(len(atr_values)):
        current_sum += atr_values[i]
        phi_atr[i] = current_sum
    
    # Normalize globally for the initial training
    phi_max = phi_atr[-1]
    phi_min = phi_atr[0]
    if phi_max > phi_min:
        phi_atr = (phi_atr - phi_min) / (phi_max - phi_min)
    
    return phi_atr, phi_min, phi_max

def train_siren_layer(layer_idx, config, residual, phi_atr_1d):
    """
    Trains a single SIREN layer to fit the smoothed residual (alvo careca).
    Returns the trained weights dict and the prediction array.
    """
    span = config['span']
    atr_period = config['atr_period']
    hidden_features = config['hidden_features']
    hidden_layers = config['hidden_layers']
    omega_0 = config['omega_0']
    lr = config['lr']
    epochs = config['epochs']
    alpha = config['alpha']
    beta = config['beta']
    
    print(f"\n[{time.strftime('%H:%M:%S')}] --- Training L{layer_idx+1} (Span {span}) ---")
    
    # 1. Detrending / Smoothing (passar o ferro)
    target_smoothed = ema_zero_phase(residual, span)
    
    # Move to tensors
    X_t = torch.tensor(phi_atr_1d, dtype=torch.float32, device=DEVICE).unsqueeze(1)
    Y_t = torch.tensor(target_smoothed, dtype=torch.float32, device=DEVICE).unsqueeze(1)
    
    model = FMSiren(
        in_features=1, 
        hidden_features=hidden_features, 
        hidden_layers=hidden_layers, 
        out_features=1, 
        omega_0=omega_0
    ).to(DEVICE)
    
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    
    best_loss = float('inf')
    best_state = None
    best_mse = 0.0
    best_pearson = 0.0
    
    # Fix seed for reproducibility inside layer
    torch.manual_seed(42)
    
    for epoch in range(epochs):
        optimizer.zero_grad()
        
        preds = model(X_t)
        
        loss_val, mse_val, pearson_val = siren_loss_fn(preds, Y_t, alpha=alpha, beta=beta)
        
        if torch.isnan(loss_val):
            print("NaN loss detected. Stopping training early.")
            break
            
        loss_val.backward()
        
        # Gradient clipping to prevent exploding gradients in FM Synthesis
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        
        optimizer.step()
        scheduler.step()
        
        # Track best model strictly by the custom loss
        if loss_val.item() < best_loss:
            best_loss = loss_val.item()
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            best_mse = mse_val
            best_pearson = pearson_val
            
        if epoch % 200 == 0 or epoch == epochs - 1:
            print(f"  Epoch {epoch:4d} | Loss: {loss_val.item():.7f} | MSE: {mse_val:.7f} | Pearson: {pearson_val:+.4f}")
            
    # Load best state
    if best_state is not None:
        model.load_state_dict(best_state)
        
    with torch.no_grad():
        final_preds = model(X_t).cpu().numpy().flatten()
        
    # Serialize weights for Oracle
    state_dict_serializable = {k: v.numpy().tolist() for k, v in best_state.items()}
    
    layer_export = {
        'config': config,
        'state_dict': state_dict_serializable,
        'final_mse': best_mse,
        'final_pearson': best_pearson
    }
    
    return layer_export, final_preds, target_smoothed

def main():
    print(f"Loading data from {CSV_PATH} ...")
    high, low, close = load_data(CSV_PATH, limit=30000) # Truncated to 5 years for testing FM architecture
    print(f"Loaded {len(close)} bars.")
    
    # Global state init
    np.random.seed(42)
    torch.manual_seed(42)
    
    residual = close.copy()
    
    # Store results
    layers_exported = []
    predictions_history = []
    smoothed_history = []
    
    global_start = time.time()
    
    for i, config in enumerate(LAYER_CONFIGS):
        # Calculate specific ATR for the layer's volatility span
        atr_values = compute_atr(high, low, close, config['atr_period'])
        phi_atr, phi_min, phi_max = extract_phi_atr(atr_values)
        
        layer_export, preds, target_smoothed = train_siren_layer(i, config, residual, phi_atr)
        
        # Store bounds for Walk-Forward
        layer_export['phi_atr_min'] = float(phi_min)
        layer_export['phi_atr_max'] = float(phi_max)
        
        layers_exported.append(layer_export)
        predictions_history.append(preds)
        smoothed_history.append(target_smoothed)
        
        # Subtractive Detrending (Greedy Layer-Wise)
        # We subtract the SMOOTHED TARGET, not the prediction.
        # This keeps the geometry 100% mathematically correct without NN artifacts.
        residual = residual - target_smoothed
        
    global_end = time.time()
    print(f"\n[{time.strftime('%H:%M:%S')}] --- Decomposition completed in {global_end - global_start:.2f} seconds ---")
    
    # Save weights
    with open(WEIGHTS_PATH, 'w') as f:
        json.dump({
            'n_layers': len(LAYER_CONFIGS),
            'layers': layers_exported
        }, f, indent=2)
    print(f"Weights saved to {WEIGHTS_PATH}")
    
    # Export plots to verify if SIREN is bending the curve without gradient vanishing
    plt.figure(figsize=(15, 10))
    for i in range(len(LAYER_CONFIGS)):
        plt.subplot(len(LAYER_CONFIGS), 1, i + 1)
        plt.plot(smoothed_history[i][-1000:], color='gray', alpha=0.5, label='EMA Target')
        plt.plot(predictions_history[i][-1000:], color='blue', alpha=0.8, label='SIREN FM Fit')
        plt.title(f"L{i+1}: Span {LAYER_CONFIGS[i]['span']} (Last 1000 Bars)")
        plt.legend(loc='upper right')
    plt.tight_layout()
    plt.savefig('siren_layer_fits.png')
    plt.close()
    print("Saved siren_layer_fits.png")

if __name__ == '__main__':
    main()
