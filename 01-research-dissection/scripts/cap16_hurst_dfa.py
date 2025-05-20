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
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["timestamp", "Close"])
    return df


def build_time_years(ts: pd.Series) -> np.ndarray:
    t0 = ts.iloc[0]
    hours = (ts - t0).dt.total_seconds() / 3600.0
    years = hours / (24.0 * 365.25)
    return years.to_numpy()


def r2_score(y: np.ndarray, y_hat: np.ndarray) -> float:
    y_mean = y.mean()
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - y_mean) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan


def fit_tri_pendulum(t: np.ndarray, y: np.ndarray, periods_years: List[float]):
    cols = [np.ones_like(t)]
    for p in periods_years:
        w = 2.0 * np.pi / p
        cols.append(np.sin(w * t))
        cols.append(np.cos(w * t))
    X = np.column_stack(cols)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    y_hat = X @ beta
    return y_hat


def auto_search_periods(
    t: np.ndarray,
    y: np.ndarray,
    period_min: float,
    period_max: float,
    candidates: int,
    sample_step: int,
    max_combos: int,
    seed: int,
):
    idx = np.arange(0, len(t), max(1, sample_step))
    t_s = t[idx]
    y_s = y[idx]

    periods = np.exp(np.linspace(np.log(period_min), np.log(period_max), candidates))

    sincos = {}
    for p in periods:
        w = 2.0 * np.pi / p
        sincos[p] = (np.sin(w * t_s), np.cos(w * t_s))

    from itertools import combinations
    combos = list(combinations(periods, 3))
    if max_combos and max_combos < len(combos):
        rng = np.random.default_rng(seed)
        combos = rng.choice(combos, size=max_combos, replace=False)

    best = (-1e9, None)
    for combo in combos:
        p1, p2, p3 = sorted(combo, reverse=True)
        cols = [np.ones_like(t_s)]
        for p in (p1, p2, p3):
            s, c = sincos[p]
            cols.append(s)
            cols.append(c)
        X = np.column_stack(cols)
        beta, *_ = np.linalg.lstsq(X, y_s, rcond=None)
        y_hat = X @ beta
        y_mean = y_s.mean()
        ss_res = float(np.sum((y_s - y_hat) ** 2))
        ss_tot = float(np.sum((y_s - y_mean) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
        if r2 > best[0]:
            best = (r2, [p1, p2, p3])

    return best


def dfa_hurst(series: np.ndarray, min_scale: int, max_scale: int, n_scales: int = 12, order: int = 1) -> float:
    # Detrended Fluctuation Analysis (DFA)
    if max_scale <= min_scale:
        return np.nan

    # profile
    x = series - np.mean(series)
    y = np.cumsum(x)

    # log-spaced scales
    scales = np.unique(np.floor(np.logspace(np.log10(min_scale), np.log10(max_scale), n_scales)).astype(int))
    # avoid degenerate fits on very small scales
    min_valid = max(4, order + 2)
    scales = scales[scales >= min_valid]
    if len(scales) < 2:
        return np.nan

    Fs = []
    S = []
    for s in scales:
        n_segments = len(y) // s
        if n_segments < 2:
            continue
        rms = []
        for v in range(n_segments):
            seg = y[v * s:(v + 1) * s]
            t = np.arange(s)
            # polynomial fit
            coeffs = np.polyfit(t, seg, order)
            trend = np.polyval(coeffs, t)
            rms.append(np.mean((seg - trend) ** 2))
        if len(rms) == 0:
            continue
        fval = np.sqrt(np.mean(rms))
        # guard against near-zero fluctuations (degenerate)
        if fval <= 0.0 or not np.isfinite(fval):
            continue
        Fs.append(fval)
        S.append(s)

    if len(S) < 2:
        return np.nan

    # slope of log-log
    m, _ = np.polyfit(np.log(S), np.log(Fs), 1)
    return float(m)


def classify_hurst(h: float) -> str:
    if np.isnan(h):
        return "nan"
    if h < 0.49:
        return "mean_reverting"
    if h > 0.51:
        return "trending"
    return "random_walk"


def main() -> int:
    ap = argparse.ArgumentParser(description="Capitulo XVI - Elasticidade do Tempo (Hurst via DFA)")
    ap.add_argument("--data", default=None)
    ap.add_argument("--outdir", default="outputs/out_cap16_dfa")
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--period-range", default="2,30")
    ap.add_argument("--candidates", type=int, default=24)
    ap.add_argument("--search-sample-step", type=int, default=10)
    ap.add_argument("--max-combos", type=int, default=0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dfa-scales", type=int, default=12)
    ap.add_argument("--dfa-order", type=int, default=1)
    args = ap.parse_args()

    data_path = find_data_path(args.data)
    df = load_data(data_path)
    if args.start:
        df = df[df["timestamp"] >= pd.Timestamp(args.start)]
    if args.end:
        df = df[df["timestamp"] <= pd.Timestamp(args.end)]
    df = df.reset_index(drop=True)

    t_years = build_time_years(df["timestamp"])
    price = df["Close"].to_numpy(dtype=float)

    # auto-search periods for macro removal
    rng_min, rng_max = [float(x.strip()) for x in args.period_range.split(",")]
    best_r2, best_periods = auto_search_periods(
        t_years, price,
        period_min=rng_min,
        period_max=rng_max,
        candidates=args.candidates,
        sample_step=args.search_sample_step,
        max_combos=args.max_combos,
        seed=args.seed,
    )

    macro_fit = fit_tri_pendulum(t_years, price, best_periods)
    r2_macro = r2_score(price, macro_fit)

    # residual in pips
    residual = (price - macro_fit) * 10000.0
    # use increments to avoid inflated DFA exponents on non-stationary levels
    residual_inc = np.diff(residual, prepend=residual[0])

    scopes = [
        ("micro_intraday", 2, 24),
        ("swing_semanal", 24, 120),
        ("fissura_mensal", 120, 520),
        ("macro_orbita", 520, 6240),
    ]

    hurst_results = []
    for name, lo, hi in scopes:
        h = dfa_hurst(residual_inc, lo, hi, n_scales=args.dfa_scales, order=args.dfa_order)
        hurst_results.append({
            "scope": name,
            "min_scale": lo,
            "max_scale": hi,
            "hurst": h,
            "class": classify_hurst(h),
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
        "macro_removal": {
            "periods_years": best_periods,
            "auto_search_r2_sample": best_r2,
            "r2_macro_fit": r2_macro,
        },
        "dfa": {
            "scales": args.dfa_scales,
            "order": args.dfa_order,
        },
        "hurst": hurst_results,
    }

    with (outdir / "cap16_dfa_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    pd.DataFrame(hurst_results).to_csv(outdir / "cap16_dfa_hurst.csv", index=False)

    # Plots
    plot_dir = outdir.parent / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    df_h = pd.DataFrame(hurst_results)
    if len(df_h):
        plt.figure(figsize=(7, 4))
        plt.bar(df_h["scope"], df_h["hurst"], color="#59a14f")
        plt.axhline(0.5, color="black", linewidth=1, alpha=0.6)
        plt.ylabel("H (DFA)")
        plt.title("Capitulo XVI - Hurst por Escopo")
        plt.xticks(rotation=20, ha="right")
        plt.tight_layout()
        plt.savefig(plot_dir / "cap16_hurst_scopes.png", dpi=140)
        plt.close()

    print("[OK] Capitulo XVI (DFA) outputs:")
    print(f"- {outdir / 'cap16_dfa_summary.json'}")
    print(f"- {outdir / 'cap16_dfa_hurst.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
