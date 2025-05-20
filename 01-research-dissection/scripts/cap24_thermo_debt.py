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
    if "TickVolume" in df.columns:
        df["TickVolume"] = pd.to_numeric(df["TickVolume"], errors="coerce")
    df = df.dropna(subset=["timestamp", "Close", "High", "Low"])
    return df


def extract_swings(high: np.ndarray, low: np.ndarray, threshold_pips: float):
    swings = []
    direction = 0  # 1 up, -1 down
    last_high_val = high[0]
    last_high_idx = 0
    last_low_val = low[0]
    last_low_idx = 0

    for i in range(1, len(high)):
        h = high[i]
        l = low[i]

        if direction == 0:
            if h - last_low_val >= threshold_pips:
                direction = 1
                last_high_val = h
                last_high_idx = i
                swings.append({
                    "dir": 1,
                    "start_idx": last_low_idx,
                    "start_price": last_low_val,
                    "end_idx": i,
                    "end_price": h,
                })
            elif last_high_val - l >= threshold_pips:
                direction = -1
                last_low_val = l
                last_low_idx = i
                swings.append({
                    "dir": -1,
                    "start_idx": last_high_idx,
                    "start_price": last_high_val,
                    "end_idx": i,
                    "end_price": l,
                })
            continue

        if direction == 1:
            if h > last_high_val:
                last_high_val = h
                last_high_idx = i
                swings[-1]["end_idx"] = i
                swings[-1]["end_price"] = h
            elif last_high_val - l >= threshold_pips:
                direction = -1
                last_low_val = l
                last_low_idx = i
                swings.append({
                    "dir": -1,
                    "start_idx": last_high_idx,
                    "start_price": last_high_val,
                    "end_idx": i,
                    "end_price": l,
                })
            continue

        if direction == -1:
            if l < last_low_val:
                last_low_val = l
                last_low_idx = i
                swings[-1]["end_idx"] = i
                swings[-1]["end_price"] = l
            elif h - last_low_val >= threshold_pips:
                direction = 1
                last_high_val = h
                last_high_idx = i
                swings.append({
                    "dir": 1,
                    "start_idx": last_low_idx,
                    "start_price": last_low_val,
                    "end_idx": i,
                    "end_price": h,
                })

    return swings


def summarize_swings(swings, tick_volume: Optional[np.ndarray]):
    up_pips = 0.0
    down_pips = 0.0
    up_hours = 0.0
    down_hours = 0.0
    up_joules_time = 0.0
    down_joules_time = 0.0
    up_joules_tick = 0.0
    down_joules_tick = 0.0

    for s in swings:
        amp = abs(s["end_price"] - s["start_price"])
        hours = max(1.0, float(s["end_idx"] - s["start_idx"]))
        joules_time = amp * hours

        if tick_volume is not None:
            vol = float(np.sum(tick_volume[s["start_idx"]: s["end_idx"] + 1]))
            joules_tick = amp * vol
        else:
            vol = None
            joules_tick = 0.0

        if s["dir"] == 1:
            up_pips += amp
            up_hours += hours
            up_joules_time += joules_time
            up_joules_tick += joules_tick
        else:
            down_pips += amp
            down_hours += hours
            down_joules_time += joules_time
            down_joules_tick += joules_tick

    total_pips = up_pips + down_pips
    total_hours = up_hours + down_hours
    total_jt = up_joules_time + down_joules_time
    total_jv = up_joules_tick + down_joules_tick

    return {
        "count": len(swings),
        "pips_up_pct": (up_pips / total_pips * 100.0) if total_pips else 0.0,
        "pips_down_pct": (down_pips / total_pips * 100.0) if total_pips else 0.0,
        "hours_up_pct": (up_hours / total_hours * 100.0) if total_hours else 0.0,
        "hours_down_pct": (down_hours / total_hours * 100.0) if total_hours else 0.0,
        "joules_time_up_pct": (up_joules_time / total_jt * 100.0) if total_jt else 0.0,
        "joules_time_down_pct": (down_joules_time / total_jt * 100.0) if total_jt else 0.0,
        "joules_tick_up_pct": (up_joules_tick / total_jv * 100.0) if total_jv else 0.0,
        "joules_tick_down_pct": (down_joules_tick / total_jv * 100.0) if total_jv else 0.0,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Capitulo XXIV - Divida Termodinamica")
    ap.add_argument("--data", default=None)
    ap.add_argument("--outdir", default="outputs/out_cap24")
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--thresholds", default="15,100,500")
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
    tick = df["TickVolume"].to_numpy(dtype=float) if "TickVolume" in df.columns else None

    thresholds = [float(x.strip()) for x in args.thresholds.split(",") if x.strip()]
    rows = []
    for thr in thresholds:
        swings = extract_swings(high, low, thr)
        stats = summarize_swings(swings, tick)
        rows.append({
            "threshold_pips": thr,
            "count": stats["count"],
            "pips_up_pct": stats["pips_up_pct"],
            "pips_down_pct": stats["pips_down_pct"],
            "hours_up_pct": stats["hours_up_pct"],
            "hours_down_pct": stats["hours_down_pct"],
            "joules_time_up_pct": stats["joules_time_up_pct"],
            "joules_time_down_pct": stats["joules_time_down_pct"],
            "joules_tick_up_pct": stats["joules_tick_up_pct"],
            "joules_tick_down_pct": stats["joules_tick_down_pct"],
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
        "thresholds": thresholds,
        "rows": rows,
    }

    with (outdir / "cap24_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    pd.DataFrame(rows).to_csv(outdir / "cap24_table.csv", index=False)

    # Plots
    plot_dir = outdir.parent / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    df_rows = pd.DataFrame(rows)
    if len(df_rows):
        labels = [str(int(x)) for x in df_rows["threshold_pips"]]
        x = np.arange(len(labels))
        width = 0.2
        plt.figure(figsize=(8, 4))
        plt.bar(x - 1.5 * width, df_rows["pips_up_pct"], width, label="pips_up")
        plt.bar(x - 0.5 * width, df_rows["hours_up_pct"], width, label="hours_up")
        plt.bar(x + 0.5 * width, df_rows["joules_time_up_pct"], width, label="joules_time_up")
        plt.bar(x + 1.5 * width, df_rows["joules_tick_up_pct"], width, label="joules_tick_up")
        plt.axhline(50.0, color="black", linewidth=1, alpha=0.6)
        plt.xticks(x, labels)
        plt.ylabel("up (%)")
        plt.xlabel("threshold_pips")
        plt.title("Capitulo XXIV - Conservacao Direcional (Up %)")
        plt.legend(fontsize=8)
        plt.tight_layout()
        plt.savefig(plot_dir / "cap24_up_pct.png", dpi=140)
        plt.close()

    print("[OK] Capitulo XXIV outputs:")
    print(f"- {outdir / 'cap24_summary.json'}")
    print(f"- {outdir / 'cap24_table.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
