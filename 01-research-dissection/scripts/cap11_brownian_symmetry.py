import argparse
import json
from pathlib import Path
from typing import Optional, List, Dict

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
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["timestamp", "Close"])
    return df


def compute_hourly_symmetry(close: np.ndarray) -> Dict[str, float]:
    # Hour-to-hour deltas in pips
    d = np.diff(close, prepend=close[0])
    up = d[d > 0]
    dn = d[d < 0]
    flat = np.sum(d == 0)
    hours_up = int(len(up))
    hours_dn = int(len(dn))
    pips_up = float(np.sum(up))
    pips_dn = float(np.abs(np.sum(dn)))
    ratio_time = hours_up / hours_dn if hours_dn > 0 else np.nan
    ratio_space = pips_up / pips_dn if pips_dn > 0 else np.nan
    return {
        "hours_up": hours_up,
        "hours_down": hours_dn,
        "hours_flat": int(flat),
        "pips_up": pips_up,
        "pips_down": pips_dn,
        "edge_time": ratio_time,
        "edge_space": ratio_space,
    }


def zigzag_legs(close: np.ndarray, threshold_pips: float) -> pd.DataFrame:
    # close is in pips (price*10000)
    legs = []
    direction = 0  # 1 up, -1 down, 0 unknown
    last_pivot = close[0]
    last_pivot_idx = 0
    last_extreme = close[0]
    last_extreme_idx = 0

    for i in range(1, len(close)):
        val = close[i]
        diff_from_extreme = val - last_extreme

        if direction == 0:
            if diff_from_extreme >= threshold_pips:
                direction = 1
                last_extreme = val
                last_extreme_idx = i
            elif diff_from_extreme <= -threshold_pips:
                direction = -1
                last_extreme = val
                last_extreme_idx = i
            continue

        if direction == 1:
            if diff_from_extreme <= -threshold_pips:
                # close up leg
                legs.append({
                    "dir": 1,
                    "start_idx": last_pivot_idx,
                    "end_idx": last_extreme_idx,
                    "pips": float(last_extreme - last_pivot),
                    "hours": int(max(1, last_extreme_idx - last_pivot_idx)),
                })
                direction = -1
                last_pivot = last_extreme
                last_pivot_idx = last_extreme_idx
                last_extreme = val
                last_extreme_idx = i
            elif diff_from_extreme > 0:
                last_extreme = val
                last_extreme_idx = i
            continue

        # direction == -1
        if diff_from_extreme >= threshold_pips:
            # close down leg
            legs.append({
                "dir": -1,
                "start_idx": last_pivot_idx,
                "end_idx": last_extreme_idx,
                "pips": float(last_pivot - last_extreme),
                "hours": int(max(1, last_extreme_idx - last_pivot_idx)),
            })
            direction = 1
            last_pivot = last_extreme
            last_pivot_idx = last_extreme_idx
            last_extreme = val
            last_extreme_idx = i
        elif diff_from_extreme < 0:
            last_extreme = val
            last_extreme_idx = i

    # The last running leg is intentionally ignored to avoid bias.
    if not legs:
        return pd.DataFrame(columns=["dir", "start_idx", "end_idx", "pips", "hours"])
    return pd.DataFrame(legs)


def summarize_legs(legs: pd.DataFrame) -> Dict[str, float]:
    up = legs[legs["dir"] == 1]
    dn = legs[legs["dir"] == -1]
    legs_up = int(len(up))
    legs_dn = int(len(dn))
    pips_up = float(up["pips"].sum())
    pips_dn = float(dn["pips"].sum())
    hrs_up = int(up["hours"].sum())
    hrs_dn = int(dn["hours"].sum())
    return {
        "count_legs": int(len(legs)),
        "legs_up": legs_up,
        "legs_down": legs_dn,
        "pips_up": pips_up,
        "pips_down": pips_dn,
        "hours_up": hrs_up,
        "hours_down": hrs_dn,
        "edge_legs": (legs_up / legs_dn) if legs_dn > 0 else np.nan,
        "edge_pips": (pips_up / pips_dn) if pips_dn > 0 else np.nan,
        "edge_hours": (hrs_up / hrs_dn) if hrs_dn > 0 else np.nan,
    }


def parse_thresholds(text: str) -> List[float]:
    out = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(float(part))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Capitulo XI - Brownian symmetry audit")
    ap.add_argument("--data", default=None, help="Path to EURUSD H1 OHLC CSV")
    ap.add_argument("--thresholds", default="20,50,100,200", help="Comma-separated pips thresholds")
    ap.add_argument("--outdir", default="outputs/out_cap11", help="Output directory")
    ap.add_argument("--export_legs", type=float, default=None, help="Export legs CSV for one threshold (pips)")
    ap.add_argument("--start", default=None, help="Filter start timestamp (YYYY-MM-DD or ISO)")
    ap.add_argument("--end", default=None, help="Filter end timestamp (YYYY-MM-DD or ISO)")
    args = ap.parse_args()

    data_path = find_data_path(args.data)
    df = load_data(data_path)
    if args.start:
        start_ts = pd.Timestamp(args.start)
        df = df[df["timestamp"] >= start_ts]
    if args.end:
        end_ts = pd.Timestamp(args.end)
        df = df[df["timestamp"] <= end_ts]
    df = df.reset_index(drop=True)

    close_pips = (df["Close"].to_numpy(dtype=float) * 10000.0)

    hourly = compute_hourly_symmetry(close_pips)

    thresholds = parse_thresholds(args.thresholds)
    leg_rows = []
    legs_cache = {}

    for thr in thresholds:
        legs = zigzag_legs(close_pips, thr)
        legs_cache[thr] = legs
        stats = summarize_legs(legs)
        stats["threshold_pips"] = thr
        leg_rows.append(stats)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Save summary
    summary = {
        "dataset": {
            "path": str(data_path),
            "rows": int(len(df)),
            "start": str(df["timestamp"].iloc[0]),
            "end": str(df["timestamp"].iloc[-1]),
            "filter_start": args.start,
            "filter_end": args.end,
        },
        "hourly_symmetry": hourly,
        "zigzag_thresholds": leg_rows,
    }

    with (outdir / "cap11_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    pd.DataFrame(leg_rows).to_csv(outdir / "cap11_leg_summary.csv", index=False)

    # Plots
    plot_dir = outdir.parent / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    if len(leg_rows) >= 2:
        df_plot = pd.DataFrame(leg_rows).sort_values("threshold_pips")
        plt.figure(figsize=(7, 4))
        plt.plot(df_plot["threshold_pips"], df_plot["edge_legs"], label="edge_legs")
        plt.plot(df_plot["threshold_pips"], df_plot["edge_pips"], label="edge_pips")
        plt.plot(df_plot["threshold_pips"], df_plot["edge_hours"], label="edge_hours")
        plt.axhline(1.0, color="black", linewidth=1, alpha=0.6)
        plt.xlabel("threshold_pips")
        plt.ylabel("edge ratio")
        plt.title("Capitulo XI - Edge Ratios vs Threshold")
        plt.legend()
        plt.tight_layout()
        plt.savefig(plot_dir / "cap11_edge_ratios.png", dpi=140)
        plt.close()

    if args.export_legs is not None:
        thr = float(args.export_legs)
        if thr not in legs_cache:
            legs_cache[thr] = zigzag_legs(close_pips, thr)
        legs_cache[thr].to_csv(outdir / f"cap11_legs_{int(thr)}pips.csv", index=False)

    print("[OK] Capitulo XI summary saved:")
    print(f"- {outdir / 'cap11_summary.json'}")
    print(f"- {outdir / 'cap11_leg_summary.csv'}")
    if args.export_legs is not None:
        print(f"- {outdir / f'cap11_legs_{int(args.export_legs)}pips.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
