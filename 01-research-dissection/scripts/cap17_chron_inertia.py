import argparse
import json
from pathlib import Path
from typing import Optional, List

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


def build_time_years(ts: pd.Series) -> np.ndarray:
    t0 = ts.iloc[0]
    hours = (ts - t0).dt.total_seconds() / 3600.0
    years = hours / (24.0 * 365.25)
    return years.to_numpy()


def fit_sine_period(t: np.ndarray, y: np.ndarray, period_years: float):
    w = 2.0 * np.pi / period_years
    X = np.column_stack([np.sin(w * t), np.cos(w * t), np.ones_like(t)])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    y_hat = X @ beta
    A = float(np.sqrt(beta[0]**2 + beta[1]**2))
    phase = float(np.arctan2(beta[1], beta[0]))
    r2 = r2_score(y, y_hat)
    return {
        "period_years": period_years,
        "amplitude": A,
        "phase": phase,
        "r2": r2,
    }


def fit_sine_period_hours(t_hours: np.ndarray, y: np.ndarray, period_hours: float):
    w = 2.0 * np.pi / period_hours
    X = np.column_stack([np.sin(w * t_hours), np.cos(w * t_hours), np.ones_like(t_hours)])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    y_hat = X @ beta
    A = float(np.sqrt(beta[0]**2 + beta[1]**2))
    phase = float(np.arctan2(beta[1], beta[0]))
    r2 = r2_score(y, y_hat)
    return {
        "period_hours": period_hours,
        "amplitude": A,
        "phase": phase,
        "r2": r2,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Capitulo XVII - Inercia Cronologica")
    ap.add_argument("--data", default=None)
    ap.add_argument("--outdir", default="outputs/out_cap17")
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    args = ap.parse_args()

    data_path = find_data_path(args.data)
    df = load_data(data_path)
    if args.start:
        df = df[df["timestamp"] >= pd.Timestamp(args.start)]
    if args.end:
        df = df[df["timestamp"] <= pd.Timestamp(args.end)]
    df = df.reset_index(drop=True)

    # Base series (price in pips)
    price = df["Close"].to_numpy(dtype=float) * 10000.0

    # Time axes
    t_years = build_time_years(df["timestamp"])
    t_hours = np.arange(len(df), dtype=float)

    # Macro periods in years
    macro_periods = [33.8, 14.5, 3.6]
    macro_fits = [fit_sine_period(t_years, price, p) for p in macro_periods]

    # Micro periods in hours (as in chapter)
    micro_periods_hours = [8760, 520, 120, 24]  # yearly, monthly, weekly, daily
    micro_fits = [fit_sine_period_hours(t_hours, price, p) for p in micro_periods_hours]

    # Mass = amplitude * period (converted to hours for uniformity)
    mass_table = []
    for f in macro_fits:
        period_hours = f["period_years"] * 365.25 * 24.0
        mass = f["amplitude"] * period_hours
        mass_table.append({
            "label": f"macro_{f['period_years']:.1f}y",
            "period_hours": period_hours,
            "amplitude": f["amplitude"],
            "r2": f["r2"],
            "mass": mass,
        })
    for f in micro_fits:
        period_hours = f["period_hours"]
        mass = f["amplitude"] * period_hours
        mass_table.append({
            "label": f"micro_{int(period_hours)}h",
            "period_hours": period_hours,
            "amplitude": f["amplitude"],
            "r2": f["r2"],
            "mass": mass,
        })

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
        "macro_fits": macro_fits,
        "micro_fits": micro_fits,
        "mass_table": mass_table,
    }

    with (outdir / "cap17_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    pd.DataFrame(mass_table).to_csv(outdir / "cap17_mass_table.csv", index=False)

    # Plots
    plot_dir = outdir.parent / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    df_mass = pd.DataFrame(mass_table)
    if len(df_mass):
        plt.figure(figsize=(7, 4))
        plt.scatter(df_mass["period_hours"], df_mass["mass"], color="#e15759")
        for _, row in df_mass.iterrows():
            plt.annotate(row["label"], (row["period_hours"], row["mass"]), fontsize=7, xytext=(3, 3),
                         textcoords="offset points")
        plt.xscale("log")
        plt.yscale("log")
        plt.xlabel("period_hours (log)")
        plt.ylabel("mass = amplitude * period (log)")
        plt.title("Capitulo XVII - Massa Cronologica (log-log)")
        plt.tight_layout()
        plt.savefig(plot_dir / "cap17_mass_loglog.png", dpi=140)
        plt.close()

    print("[OK] Capitulo XVII outputs:")
    print(f"- {outdir / 'cap17_summary.json'}")
    print(f"- {outdir / 'cap17_mass_table.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
