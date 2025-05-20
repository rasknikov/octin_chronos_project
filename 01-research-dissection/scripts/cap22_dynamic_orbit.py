import argparse
import json
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def find_data_path(custom: Optional[str]) -> Path:
    candidates = [
        "01_DATALAKE/eurusd_h1_ohlc.csv",
        "01_DATALAKE/EURUSD_H1_ohlc.csv",
        "01_DATALAKE/EURUSD_H1.csv",
        "EURUSD_H1.csv",
    ]
    if custom:
        p = Path(custom)
        if p.exists():
            return p
        raise FileNotFoundError(f"Data file not found: {custom}")
    for cand in candidates:
        p = Path(cand)
        if p.exists():
            return p
    raise FileNotFoundError("No EURUSD H1 dataset found in default locations.")


def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    for col in ["Open", "High", "Low", "Close"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["timestamp", "Close", "High", "Low"])
    return df


def r2_score(y: np.ndarray, y_hat: np.ndarray) -> float:
    y_mean = y.mean()
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - y_mean) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan


def hp_filter(y: np.ndarray, lamb: float) -> np.ndarray:
    try:
        import scipy.sparse as sparse
        from scipy.sparse.linalg import spsolve
    except Exception as e:
        raise SystemExit(f"scipy required for HP filter: {e}")

    n = len(y)
    D = sparse.diags([1, -2, 1], [0, 1, 2], shape=(n - 2, n))
    I = sparse.eye(n)
    B = I + lamb * D.T.dot(D)
    return spsolve(B, y)


def fit_orbit_sine(price: np.ndarray, high: np.ndarray, low: np.ndarray, orbit_window: int = 520):
    # Orbit base
    s = pd.Series(price)
    orbit = s.rolling(orbit_window).mean().to_numpy()
    valid = ~np.isnan(orbit)
    price = price[valid]
    high = high[valid]
    low = low[valid]
    orbit = orbit[valid]

    osc = price - orbit
    n = len(osc)

    # Time axes
    t_chron = np.arange(n)
    mass = np.clip((high - low), 0.0001, np.inf)
    mass_med = np.median(mass)
    phi_m = np.cumsum(mass / mass_med)

    # Fit sin/cos with monthly period (520 hours)
    T = 520.0
    w = 2.0 * np.pi / T

    X_rigid = np.column_stack([np.sin(w * t_chron), np.cos(w * t_chron), np.ones(n)])
    beta_rigid, *_ = np.linalg.lstsq(X_rigid, osc, rcond=None)
    osc_hat_rigid = X_rigid @ beta_rigid
    price_hat_rigid = orbit + osc_hat_rigid

    X_mass = np.column_stack([np.sin(w * phi_m), np.cos(w * phi_m), np.ones(n)])
    beta_mass, *_ = np.linalg.lstsq(X_mass, osc, rcond=None)
    osc_hat_mass = X_mass @ beta_mass
    price_hat_mass = orbit + osc_hat_mass

    r2_orbit = r2_score(price, orbit)
    r2_rigid = r2_score(price, price_hat_rigid)
    r2_mass = r2_score(price, price_hat_mass)

    return {
        "r2_orbit": r2_orbit,
        "r2_rigid": r2_rigid,
        "r2_mass": r2_mass,
        "n": n,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Capitulo XXII - Orbita Dinamica")
    ap.add_argument("--data", default=None)
    ap.add_argument("--outdir", default="outputs/out_cap22")
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--orbit_window", type=int, default=520)
    ap.add_argument("--hp_lambda", type=float, default=1e10)
    args = ap.parse_args()

    data_path = find_data_path(args.data)
    df = load_data(data_path)
    if args.start:
        df = df[df["timestamp"] >= pd.Timestamp(args.start)]
    if args.end:
        df = df[df["timestamp"] <= pd.Timestamp(args.end)]
    df = df.reset_index(drop=True)

    price = df["Close"].to_numpy(dtype=float) * 10000.0
    high = df["High"].to_numpy(dtype=float) * 10000.0
    low = df["Low"].to_numpy(dtype=float) * 10000.0

    # HP trend as alternative orbit
    hp_trend = hp_filter(price, lamb=args.hp_lambda)
    r2_hp = r2_score(price, hp_trend)

    # Orbit + sine fits (SMA-520)
    orbit_res = fit_orbit_sine(price, high, low, orbit_window=args.orbit_window)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    summary = {
        "dataset": {
            "path": str(data_path),
            "rows": int(len(df)),
            "start": str(df["timestamp"].iloc[0]),
            "end": str(df["timestamp"].iloc[-1]),
            "filter_start": args.start,
            "filter_end": args.end,
        },
        "orbit_window": args.orbit_window,
        "hp_lambda": args.hp_lambda,
        "r2_hp": r2_hp,
        "orbit_sma": orbit_res,
    }

    with (outdir / "cap22_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Plots
    plot_dir = outdir.parent / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    r2_items = [
        ("HP", r2_hp),
        ("SMA-520", orbit_res["r2_orbit"]),
        ("SMA+rigid", orbit_res["r2_rigid"]),
        ("SMA+mass", orbit_res["r2_mass"]),
    ]
    r2_items = [(k, v) for k, v in r2_items if v is not None and np.isfinite(v)]
    if r2_items:
        labels = [k for k, _ in r2_items]
        values = [v for _, v in r2_items]
        plt.figure(figsize=(7, 4))
        plt.bar(labels, values, color="#4e79a7")
        plt.ylabel("R2")
        plt.title("Capitulo XXII - R2 por Modelo")
        plt.xticks(rotation=20, ha="right")
        plt.tight_layout()
        plt.savefig(plot_dir / "cap22_r2.png", dpi=140)
        plt.close()

    print("[OK] Capitulo XXII outputs:")
    print(f"- {outdir / 'cap22_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
