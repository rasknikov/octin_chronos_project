import json
import torch
import numpy as np
from config import DEVICE
from siren_engine import FMSiren

def load_siren_weights(path: str) -> dict:
    with open(path, 'r') as f:
        data = json.load(f)
    return data

def build_siren_model_from_export(layer_export: dict) -> FMSiren:
    config = layer_export['config']
    
    model = FMSiren(
        in_features=1,
        hidden_features=config['hidden_features'],
        hidden_layers=config['hidden_layers'],
        out_features=1,
        omega_0=config['omega_0']
    ).to(DEVICE)
    
    # Reload weights
    # state_dict lists were exported, convert back to tensors
    raw_state = layer_export['state_dict']
    tensor_state = {k: torch.tensor(v, dtype=torch.float32, device=DEVICE) for k, v in raw_state.items()}
    model.load_state_dict(tensor_state)
    
    model.eval()
    return model

def project_siren_layer(layer_export: dict, 
                        current_phi_atr: float, 
                        current_atr: float, 
                        total_projection_bars: int) -> float:
    """
    Given the current phase (Phi), project the trend over 'projection_bars'
    using the accumulated ATR to unroll the phase into the future.
    """
    # Assuming ATR holds relatively constant for the projection size
    future_phi_atr = current_phi_atr + (current_atr * total_projection_bars)
    
    # Normalize bounds based on global historical min/max seen so far
    phi_min = layer_export['phi_atr_min']
    phi_max = layer_export['phi_atr_max']
    
    # Strictly bound to prevent exploding predictions if ATR jumps beyond historical
    range_phi = phi_max - phi_min
    if range_phi == 0:
        norm_current = 0.0
        norm_future = 0.0
    else:
        norm_current = (current_phi_atr - phi_min) / range_phi
        norm_future = (future_phi_atr - phi_min) / range_phi
        
    model = build_siren_model_from_export(layer_export)
    
    # Predict Y_current and Y_future
    with torch.no_grad():
        x_curr = torch.tensor([[norm_current]], dtype=torch.float32, device=DEVICE)
        x_fut = torch.tensor([[norm_future]], dtype=torch.float32, device=DEVICE)
        
        y_curr = model(x_curr).cpu().item()
        y_fut = model(x_fut).cpu().item()
        
    # Return expected delta (Pips)
    return (y_fut - y_curr) * 10000.0  # Convert to pips


class SirenOracle:
    """
    Committee Voting Oracle using FM SIREN Models.
    Matches identically the logic of V2 PINN Oracle.
    """
    
    # Default matching MACRO EXPERIMENT mapping
    COMPASS_LAYERS = [1, 2]   # L2 (Annual) + L3 (Quarterly)
    TRIGGER_LAYERS = [3, 4]   # L4 (Monthly) + L5 (Weekly)
    MUTED_LAYERS   = [5, 6, 7]  # L6, L7, L8 — too fast for macro prediction

    def __init__(self, weights_path: str,
                 spread_pips: float = 2.0,
                 compass_layers: list = None,
                 trigger_layers: list = None):
                 
        self.weights_data = load_siren_weights(weights_path)
        self.n_layers = self.weights_data['n_layers']
        self.layers = self.weights_data['layers']
        
        self.spread = spread_pips
        self.compass_layers = compass_layers or self.COMPASS_LAYERS
        self.trigger_layers = trigger_layers or self.TRIGGER_LAYERS

    def generate_signal(self,
                        current_phi_atrs: list,
                        current_atr_values: list,
                        projection_bars: int = 168) -> dict:
        """
        Committee Voting Signal Generation.
        """
        # ----- COMPASS: direction filter -----
        compass_delta = 0.0
        for k in self.compass_layers:
            compass_delta += project_siren_layer(
                self.layers[k], current_phi_atrs[k], current_atr_values[k], projection_bars
            )

        # ----- TRIGGER: execution confirmation -----
        trigger_delta = 0.0
        for k in self.trigger_layers:
            trigger_delta += project_siren_layer(
                self.layers[k], current_phi_atrs[k], current_atr_values[k], projection_bars
            )

        signal = 0
        if compass_delta > 0 and trigger_delta > 0:
            if trigger_delta > self.spread:
                signal = 1
        elif compass_delta < 0 and trigger_delta < 0:
            if trigger_delta < -self.spread:
                signal = -1

        return {
            'signal': signal,
            'expected_pips': float(trigger_delta),
            'compass_delta': float(compass_delta),
            'trigger_delta': float(trigger_delta)
        }
