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


def extract_swings(close: np.ndarray, min_swing_pips: float):
    legs = []
    last_pivot_idx = 0
    last_pivot_val = close[0]
    is_up = True

    for i in range(1, len(close)):
        current_val = close[i]
        if is_up:
            if current_val > last_pivot_val:
                last_pivot_val = current_val
                last_pivot_idx = i
            elif last_pivot_val - current_val >= min_swing_pips:
                legs.append({
                    "start_idx": last_pivot_idx,
                    "end_idx": last_pivot_idx,
                    "type": 1,
                })
                is_up = False
                last_pivot_val = current_val
                last_pivot_idx = i
        else:
            if current_val < last_pivot_val:
                last_pivot_val = current_val
                last_pivot_idx = i
            elif current_val - last_pivot_val >= min_swing_pips:
                legs.append({
                    "start_idx": last_pivot_idx,
                    "end_idx": last_pivot_idx,
                    "type": -1,
                })
                is_up = True
                last_pivot_val = current_val
                last_pivot_idx = i
    return legs


def main() -> int:
    ap = argparse.ArgumentParser(description="Capitulo XIX - Reatividade de Baixa Massa")
    ap.add_argument("--data", default=None)
    ap.add_argument("--outdir", default="outputs/out_cap19")
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--min_swing_pips", type=float, default=15.0)
    ap.add_argument("--reversion_target", type=float, default=0.90)
    ap.add_argument("--max_lookahead", type=int, default=2000)
    args = ap.parse_args()

    data_path = find_data_path(args.data)
    df = load_data(data_path)
    if args.start:
        df = df[df["timestamp"] >= pd.Timestamp(args.start)]
    if args.end:
        df = df[df["timestamp"] <= pd.Timestamp(args.end)]
    df = df.reset_index(drop=True)

    high = df["High"].to_numpy(dtype=float) * 10000.0
    low = df["Low"].to_numpy(dtype=float) * 10000.0
    close = df["Close"].to_numpy(dtype=float) * 10000.0

    legs = extract_swings(close, args.min_swing_pips)

    all_waves = []
    for k in range(1, len(legs) - 1):
        start_idx = legs[k - 1]["end_idx"]
        end_idx = legs[k]["end_idx"]
        amp = abs(close[end_idx] - close[start_idx])
        t_exp = end_idx - start_idx
        if t_exp <= 0:
            continue
        mass = amp * t_exp

        target = close[end_idx] - (args.reversion_target * amp * legs[k]["type"])
        t_rev = -1
        success = False

        for j in range(end_idx + 1, min(end_idx + args.max_lookahead, len(close))):
            if legs[k]["type"] == 1 and low[j] <= target:
                t_rev = j - end_idx
                success = True
                break
            if legs[k]["type"] == -1 and high[j] >= target:
                t_rev = j - end_idx
                success = True
                break

        all_waves.append({
            "mass": mass,
            "success": success,
            "t_exp": t_exp,
            "t_rev": t_rev,
        })

    df_waves = pd.DataFrame(all_waves)
    df_waves = df_waves.sort_values("mass").reset_index(drop=True)

    total = len(df_waves)
    q1 = int(total * 0.25)
    q3 = int(total * 0.75)

    groups = {
        "pena_quartil": df_waves.iloc[:q1],
        "pedra_medio": df_waves.iloc[q1:q3],
        "bigorna_quartil": df_waves.iloc[q3:],
    }

    summary_rows = []
    for name, subset in groups.items():
        total_g = len(subset)
        succ = subset[subset["success"] == True]
        win = float(len(succ) / total_g * 100.0) if total_g else 0.0
        t_exp_med = float(succ["t_exp"].median()) if len(succ) else None
        t_rev_med = float(succ["t_rev"].median()) if len(succ) else None
        ratio = float(t_rev_med / t_exp_med) if t_exp_med and t_rev_med else None
        summary_rows.append({
            "group": name,
            "count": int(total_g),
            "win_rate": win,
            "t_exp_med": t_exp_med,
            "t_rev_med": t_rev_med,
            "ratio": ratio,
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
        "params": {
            "min_swing_pips": args.min_swing_pips,
            "reversion_target": args.reversion_target,
            "max_lookahead": args.max_lookahead,
        },
        "summary": summary_rows,
    }

    with (outdir / "cap19_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    df_waves.to_csv(outdir / "cap19_waves.csv", index=False)
    pd.DataFrame(summary_rows).to_csv(outdir / "cap19_groups.csv", index=False)

    # Plots
    plot_dir = outdir.parent / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    df_groups = pd.DataFrame(summary_rows)
    if len(df_groups):
        plt.figure(figsize=(7, 4))
        plt.bar(df_groups["group"], df_groups["win_rate"], color="#f28e2b")
        plt.ylabel("win rate (%)")
        plt.title("Capitulo XIX - Win Rate por Grupo de Massa")
        plt.xticks(rotation=20, ha="right")
        plt.ylim(0, 100)
        plt.tight_layout()
        plt.savefig(plot_dir / "cap19_win_rate.png", dpi=140)
        plt.close()

    print("[OK] Capitulo XIX outputs:")
    print(f"- {outdir / 'cap19_summary.json'}")
    print(f"- {outdir / 'cap19_groups.csv'}")
    print(f"- {outdir / 'cap19_waves.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
