import time
import json
import numpy as np
import pandas as pd
import torch
from config import CSV_PATH, DEVICE, LAYER_CONFIGS
from siren_engine import FMSiren, compute_atr, ema_zero_phase, siren_loss_fn

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
    phi_atr = np.zeros_like(atr_values)
    current_sum = 0.0
    for i in range(len(atr_values)):
        current_sum += atr_values[i]
        phi_atr[i] = current_sum
    
    phi_max = phi_atr[-1]
    phi_min = phi_atr[0]
    if phi_max > phi_min:
        phi_atr = (phi_atr - phi_min) / (phi_max - phi_min)
    
    return phi_atr, phi_min, phi_max

def train_siren_layer(layer_idx, config, residual, phi_atr_1d):
    span = config['span']
    atr_period = config['atr_period']
    hidden_features = config['hidden_features']
    hidden_layers = config['hidden_layers']
    omega_0 = config['omega_0']
    lr = config['lr']
    epochs = config['epochs']
    alpha = config['alpha']
    beta = config['beta']
    
    target_smoothed = ema_zero_phase(residual, span)
    
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
    
    torch.manual_seed(42)
    
    for epoch in range(epochs):
        optimizer.zero_grad()
        preds = model(X_t)
        loss_val, mse_val, pearson_val = siren_loss_fn(preds, Y_t, alpha=alpha, beta=beta)
        if torch.isnan(loss_val): break
        loss_val.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()
        
        if loss_val.item() < best_loss:
            best_loss = loss_val.item()
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            
    if best_state is not None:
        model.load_state_dict(best_state)
        
    state_dict_serializable = {k: v.numpy().tolist() for k, v in best_state.items()}
    layer_export = {
        'config': config,
        'state_dict': state_dict_serializable
    }
    return layer_export, target_smoothed

def main():
    print(f"Loading data for STRICT IN-SAMPLE INITIALIZATION (4320 bars)...")
    high, low, close = load_data(CSV_PATH, limit=4320)
    
    np.random.seed(42)
    torch.manual_seed(42)
    
    residual = close.copy()
    layers_exported = []
    
    for i, config in enumerate(LAYER_CONFIGS):
        atr_values = compute_atr(high, low, close, config['atr_period'])
        phi_atr, phi_min, phi_max = extract_phi_atr(atr_values)
        
        layer_export, target_smoothed = train_siren_layer(i, config, residual, phi_atr)
        
        layer_export['phi_atr_min'] = float(phi_min)
        layer_export['phi_atr_max'] = float(phi_max)
        
        layers_exported.append(layer_export)
        residual = residual - target_smoothed
        print(f"L{i+1} In-Sample base generated.")
        
    out_path = '07_FRACTAL_FM_ENGINE/pesos_fm_siren_init.json'
    with open(out_path, 'w') as f:
        json.dump({'n_layers': len(LAYER_CONFIGS), 'layers': layers_exported}, f, indent=2)
    print(f"Strict In-Sample weights saved to {out_path}")

if __name__ == '__main__':
    main()
