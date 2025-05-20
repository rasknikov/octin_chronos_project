import argparse
import json
from pathlib import Path
from typing import Optional, Dict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DATA_CANDIDATES = [
    "01_DATALAKE/eurusd_h1_ohlc.csv",
    "01_DATALAKE/EURUSD_H1_ohlc.csv",
    "01_DATALAKE/EURUSD_H1.csv",
    "EURUSD_H1.csv",
]


def find_data_path(custom: Optional[str]) -> Path:
    if custom:
        p = Path(custom)
        if p.exists():
            return p
        raise FileNotFoundError(f"Data file not found: {custom}")
    for cand in DATA_CANDIDATES:
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
    df = df.dropna(subset=["timestamp", "Close"])
    return df


def compute_time_asymmetry(
    close: np.ndarray,
    equator_window: int = 520,
    rolling_window: int = 6240,
) -> Dict[str, object]:
    s_c = pd.Series(close)
    eq = ((s_c.rolling(equator_window).max() + s_c.rolling(equator_window).min()) / 2.0)

    state = np.where(close > eq.to_numpy(), 1.0, 0.0)
    # mask equator warmup
    state[:equator_window] = np.nan

    s_state = pd.Series(state)
    distribution = s_state.rolling(window=rolling_window).mean().dropna()

    # binning by magnitude from 0.5
    bins = {
        "50/50 (Total Equilibrio)": 0,
        "60/40 (Tendencia Leve)": 0,
        "70/30 (Tendencia Forte)": 0,
        "80/20 (Tendencia Extrema)": 0,
        "90/10 (Supernova)": 0,
    }

    mags = []
    labels = []
    for pct in distribution.values:
        mag = pct if pct >= 0.5 else (1.0 - pct)
        if mag < 0.55:
            label = "50/50 (Total Equilibrio)"
        elif mag < 0.65:
            label = "60/40 (Tendencia Leve)"
        elif mag < 0.75:
            label = "70/30 (Tendencia Forte)"
        elif mag < 0.85:
            label = "80/20 (Tendencia Extrema)"
        else:
            label = "90/10 (Supernova)"
        bins[label] += 1
        mags.append(mag)
        labels.append(label)

    total = int(len(distribution))
    pct_bins = {k: (v / total * 100.0 if total else 0.0) for k, v in bins.items()}

    # distribution table
    dist_df = pd.DataFrame({
        "timestamp": distribution.index,
        "pct_above_equator": distribution.values,
        "magnitude": mags,
        "bin": labels,
    })

    return {
        "bins": bins,
        "pct_bins": pct_bins,
        "total_samples": total,
        "dist_df": dist_df,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Capitulo XII - Matriz de Inanicao Temporaria")
    ap.add_argument("--data", default=None, help="Path to EURUSD H1 OHLC CSV")
    ap.add_argument("--outdir", default="outputs/out_cap12", help="Output directory")
    ap.add_argument("--start", default=None, help="Filter start timestamp (YYYY-MM-DD or ISO)")
    ap.add_argument("--end", default=None, help="Filter end timestamp (YYYY-MM-DD or ISO)")
    ap.add_argument("--equator_window", type=int, default=520, help="Equator rolling window (hours)")
    ap.add_argument("--rolling_window", type=int, default=6240, help="Distribution rolling window (hours)")
    args = ap.parse_args()

    data_path = find_data_path(args.data)
    df = load_data(data_path)
    if args.start:
        df = df[df["timestamp"] >= pd.Timestamp(args.start)]
    if args.end:
        df = df[df["timestamp"] <= pd.Timestamp(args.end)]
    df = df.reset_index(drop=True)

    close = df["Close"].to_numpy(dtype=float)
    res = compute_time_asymmetry(close, args.equator_window, args.rolling_window)

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
        "equator_window": args.equator_window,
        "rolling_window": args.rolling_window,
        "total_samples": res["total_samples"],
        "bins": res["bins"],
        "pct_bins": res["pct_bins"],
    }

    with (outdir / "cap12_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    res["dist_df"].to_csv(outdir / "cap12_distribution.csv", index=False)

    # also save bin table
    bin_df = pd.DataFrame({
        "bin": list(res["bins"].keys()),
        "count": list(res["bins"].values()),
        "percent": [res["pct_bins"][k] for k in res["bins"].keys()],
    })
    bin_df.to_csv(outdir / "cap12_bins.csv", index=False)

    # Plots
    plot_dir = outdir.parent / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    if len(bin_df):
        plt.figure(figsize=(8, 4))
        plt.bar(bin_df["bin"], bin_df["percent"], color="#2f4b7c")
        plt.ylabel("percent (%)")
        plt.title("Capitulo XII - Distribuicao por Bin")
        plt.xticks(rotation=25, ha="right")
        plt.tight_layout()
        plt.savefig(plot_dir / "cap12_bins.png", dpi=140)
        plt.close()

    print("[OK] Capitulo XII outputs:")
    print(f"- {outdir / 'cap12_summary.json'}")
    print(f"- {outdir / 'cap12_bins.csv'}")
    print(f"- {outdir / 'cap12_distribution.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
