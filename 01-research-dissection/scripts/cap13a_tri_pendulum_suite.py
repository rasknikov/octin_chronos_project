import argparse
import json
from pathlib import Path
from typing import Optional, List, Dict

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


def fit_tri_pendulum(t: np.ndarray, y: np.ndarray, periods_years: List[float], anchor: Optional[float]):
    cols = []
    if anchor is None:
        cols.append(np.ones_like(t))

    for p in periods_years:
        w = 2.0 * np.pi / p
        cols.append(np.sin(w * t))
        cols.append(np.cos(w * t))

    X = np.column_stack(cols)
    if anchor is None:
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        D = beta[0]
        coeffs = beta[1:]
        y_hat = X @ beta
    else:
        y_adj = y - anchor
        beta, *_ = np.linalg.lstsq(X, y_adj, rcond=None)
        D = anchor
        coeffs = beta
        y_hat = anchor + X @ beta

    amps = []
    phases = []
    for i in range(0, len(coeffs), 2):
        a = coeffs[i]
        b = coeffs[i + 1]
        A = float(np.sqrt(a * a + b * b))
        phi = float(np.arctan2(b, a))
        amps.append(A)
        phases.append(phi)

    r2 = r2_score(y, y_hat)
    return {
        "fit": y_hat,
        "D": D,
        "amps": amps,
        "phases": phases,
        "r2": r2,
    }


def auto_search_periods(
    t: np.ndarray,
    y: np.ndarray,
    period_min: float,
    period_max: float,
    candidates: int,
    sample_step: int,
    anchor: Optional[float],
    max_combos: int,
    seed: int,
):
    # Downsample for speed
    idx = np.arange(0, len(t), max(1, sample_step))
    t_s = t[idx]
    y_s = y[idx]

    # Log-spaced candidates
    periods = np.exp(np.linspace(np.log(period_min), np.log(period_max), candidates))

    # Precompute sin/cos
    sincos = {}
    for p in periods:
        w = 2.0 * np.pi / p
        sincos[p] = (np.sin(w * t_s), np.cos(w * t_s))

    # Build combos
    from itertools import combinations
    combos = list(combinations(periods, 3))
    if max_combos and max_combos < len(combos):
        rng = np.random.default_rng(seed)
        combos = rng.choice(combos, size=max_combos, replace=False)

    best = (-1e9, None)
    for combo in combos:
        p1, p2, p3 = sorted(combo, reverse=True)
        cols = []
        if anchor is None:
            cols.append(np.ones_like(t_s))
        for p in (p1, p2, p3):
            s, c = sincos[p]
            cols.append(s)
            cols.append(c)
        X = np.column_stack(cols)
        if anchor is None:
            beta, *_ = np.linalg.lstsq(X, y_s, rcond=None)
            y_hat = X @ beta
        else:
            y_adj = y_s - anchor
            beta, *_ = np.linalg.lstsq(X, y_adj, rcond=None)
            y_hat = anchor + X @ beta
        y_mean = y_s.mean()
        ss_res = float(np.sum((y_s - y_hat) ** 2))
        ss_tot = float(np.sum((y_s - y_mean) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
        if r2 > best[0]:
            best = (r2, [p1, p2, p3])

    return best


def hp_filter(y: np.ndarray, lamb: float) -> np.ndarray:
    # Hodrick-Prescott filter using sparse solver
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


def fit_mass_deformed_sine(price: np.ndarray, high: np.ndarray, low: np.ndarray, orbit_window: int = 520):
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


def five_sines(M, a1, w1, p1, a2, w2, p2, a3, w3, p3, a4, w4, p4, a5, w5, p5):
    return (
        a1 * np.sin(w1 * M + p1) +
        a2 * np.sin(w2 * M + p2) +
        a3 * np.sin(w3 * M + p3) +
        a4 * np.sin(w4 * M + p4) +
        a5 * np.sin(w5 * M + p5)
    )


def fit_mass_domain(price_pips: np.ndarray, high_pips: np.ndarray, low_pips: np.ndarray, open_pips: np.ndarray,
                    sample_step: int = 4, hp_lambda: Optional[float] = None, anchor_pips: Optional[float] = None):
    try:
        from scipy.optimize import curve_fit
    except Exception as e:
        raise SystemExit(f"scipy required for curve_fit: {e}")

    # intrinsic mass axis
    direction = np.where(price_pips > open_pips, 1, np.where(price_pips < open_pips, -1, 0))
    mass = (high_pips - low_pips) * direction
    M_t = np.cumsum(mass)

    # sample for speed
    idx = np.arange(0, len(M_t), max(1, sample_step))
    M_s = M_t[idx]
    y_s = price_pips[idx]

    # moving intercept
    if hp_lambda is not None:
        C = hp_filter(y_s, lamb=hp_lambda)
    elif anchor_pips is not None:
        C = np.full_like(y_s, float(anchor_pips))
    else:
        C = np.zeros_like(y_s)

    resid = y_s - C

    bound_M = float(np.max(M_s) - np.min(M_s))
    # initial guess for w_i based on bound
    p0 = [
        1000.0, (2 * np.pi) / (bound_M * 0.8), 0.0,
        500.0,  (2 * np.pi) / (bound_M * 0.4), 0.0,
        200.0,  (2 * np.pi) / (bound_M * 0.1), 0.0,
        100.0,  (2 * np.pi) / (bound_M * 0.02), 0.0,
        50.0,   (2 * np.pi) / (bound_M * 0.005), 0.0,
    ]

    params, _ = curve_fit(five_sines, M_s, resid, p0=p0, maxfev=50000)
    fit_resid = five_sines(M_s, *params)
    y_hat = C + fit_resid

    r2 = r2_score(y_s, y_hat)

    return {
        "r2": r2,
        "params": params.tolist(),
        "sample_step": sample_step,
        "n": len(y_s),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Capitulo XIII-A - Tri-Pendulo suite")
    ap.add_argument("--data", default=None, help="Path to EURUSD H1 OHLC CSV")
    ap.add_argument("--outdir", default="outputs/out_cap13a", help="Output directory")
    ap.add_argument("--start", default=None, help="Filter start timestamp (YYYY-MM-DD or ISO)")
    ap.add_argument("--end", default=None, help="Filter end timestamp (YYYY-MM-DD or ISO)")
    ap.add_argument("--period-years", default="23.6,14.5,3.6")
    ap.add_argument("--auto-periods", action="store_true", help="Search periods automatically (3 sines).")
    ap.add_argument("--auto-periods-hp", action="store_true", help="Search periods on HP residual (3 sines).")
    ap.add_argument("--period-range", default="2,30", help="Min,Max years for auto search (default 2,30).")
    ap.add_argument("--candidates", type=int, default=24, help="Number of candidate periods in search grid.")
    ap.add_argument("--search-sample-step", type=int, default=10, help="Downsample step for auto search.")
    ap.add_argument("--max-combos", type=int, default=0, help="If >0, randomly sample combos instead of all.")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--hp-lambda", type=float, default=1e10)
    ap.add_argument("--mass-sample-step", type=int, default=4)
    ap.add_argument("--anchor", type=float, default=1.13677)
    args = ap.parse_args()

    data_path = find_data_path(args.data)
    df = load_data(data_path)
    if args.start:
        df = df[df["timestamp"] >= pd.Timestamp(args.start)]
    if args.end:
        df = df[df["timestamp"] <= pd.Timestamp(args.end)]
    df = df.reset_index(drop=True)

    price = df["Close"].to_numpy(dtype=float)
    ohlc4 = (df["Open"].to_numpy(dtype=float) + df["High"].to_numpy(dtype=float) +
             df["Low"].to_numpy(dtype=float) + df["Close"].to_numpy(dtype=float)) / 4.0

    t_years = build_time_years(df["timestamp"])
    if args.auto_periods:
        rng_min, rng_max = [float(x.strip()) for x in args.period_range.split(",")]
        best_r2, best_periods = auto_search_periods(
            t_years, price,
            period_min=rng_min,
            period_max=rng_max,
            candidates=args.candidates,
            sample_step=args.search_sample_step,
            anchor=None,
            max_combos=args.max_combos,
            seed=args.seed,
        )
        periods = best_periods
        auto_search_r2 = best_r2
    else:
        periods = [float(x.strip()) for x in args.period_years.split(",") if x.strip()]
        auto_search_r2 = None

    # Tri-pendulum (chronological) on Close
    tri_close = fit_tri_pendulum(t_years, price, periods, anchor=None)

    # Tri-pendulum + HP (fit residual around HP trend)
    hp_trend = hp_filter(price, lamb=args.hp_lambda)
    resid = price - hp_trend
    tri_hp = fit_tri_pendulum(t_years, resid, periods, anchor=0.0)
    hp_plus_tri = hp_trend + tri_hp["fit"]
    r2_hp_plus = r2_score(price, hp_plus_tri)
    r2_hp_only = r2_score(price, hp_trend)

    # Optional: auto-search periods on HP residual
    if args.auto_periods_hp:
        rng_min, rng_max = [float(x.strip()) for x in args.period_range.split(",")]
        best_r2_hp, best_periods_hp = auto_search_periods(
            t_years, resid,
            period_min=rng_min,
            period_max=rng_max,
            candidates=args.candidates,
            sample_step=args.search_sample_step,
            anchor=0.0,
            max_combos=args.max_combos,
            seed=args.seed,
        )
        tri_hp_auto = fit_tri_pendulum(t_years, resid, best_periods_hp, anchor=0.0)
        hp_plus_tri_auto = hp_trend + tri_hp_auto["fit"]
        r2_hp_plus_auto = r2_score(price, hp_plus_tri_auto)
    else:
        best_r2_hp = None
        best_periods_hp = None
        r2_hp_plus_auto = None

    # Mass-deformed sine (orbit + rigid vs mass)
    mass_def = fit_mass_deformed_sine(price, df["High"].to_numpy(dtype=float), df["Low"].to_numpy(dtype=float))

    # Theory of Everything (XXVII) - mass domain with fixed intercept
    price_pips = price * 10000.0
    open_pips = df["Open"].to_numpy(dtype=float) * 10000.0
    high_pips = df["High"].to_numpy(dtype=float) * 10000.0
    low_pips = df["Low"].to_numpy(dtype=float) * 10000.0
    anchor_pips = args.anchor * 10000.0

    xxvii = fit_mass_domain(price_pips, high_pips, low_pips, open_pips,
                            sample_step=args.mass_sample_step, hp_lambda=None, anchor_pips=anchor_pips)

    # XXVIII - mass domain with HP moving intercept
    xxviii = fit_mass_domain(price_pips, high_pips, low_pips, open_pips,
                             sample_step=args.mass_sample_step, hp_lambda=args.hp_lambda, anchor_pips=None)

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
        "tri_pendulum": {
            "auto_periods": bool(args.auto_periods),
            "auto_search_r2_sample": auto_search_r2,
            "periods_years": periods,
            "r2_close": tri_close["r2"],
            "amps": tri_close["amps"],
            "phases": tri_close["phases"],
        },
        "tri_pendulum_hp": {
            "hp_lambda": args.hp_lambda,
            "r2_hp_only": r2_hp_only,
            "r2_hp_plus_tri": r2_hp_plus,
            "auto_periods_hp": bool(args.auto_periods_hp),
            "auto_search_r2_sample_hp": best_r2_hp,
            "periods_years_hp": best_periods_hp,
            "r2_hp_plus_tri_auto": r2_hp_plus_auto,
        },
        "mass_deformed_sine": mass_def,
        "xxvii_theory_of_everything": {
            "anchor": args.anchor,
            "r2": xxvii["r2"],
            "sample_step": xxvii["sample_step"],
            "n": xxvii["n"],
        },
        "xxviii_relativistic_fiduciary": {
            "hp_lambda": args.hp_lambda,
            "r2": xxviii["r2"],
            "sample_step": xxviii["sample_step"],
            "n": xxviii["n"],
        },
    }

    with (outdir / "cap13a_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Plots
    plot_dir = outdir.parent / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    r2_items = [
        ("Tri-Pendulo", tri_close["r2"]),
        ("HP", r2_hp_only),
        ("HP+Tri", r2_hp_plus),
        ("HP+Tri auto", r2_hp_plus_auto),
        ("SMA-520", mass_def["r2_orbit"]),
        ("SMA+rigid", mass_def["r2_rigid"]),
        ("SMA+mass", mass_def["r2_mass"]),
        ("XXVII", xxvii["r2"]),
        ("XXVIII", xxviii["r2"]),
    ]
    r2_items = [(k, v) for k, v in r2_items if v is not None and np.isfinite(v)]
    if r2_items:
        labels = [k for k, _ in r2_items]
        values = [v for _, v in r2_items]
        plt.figure(figsize=(9, 4))
        plt.bar(labels, values, color="#4c78a8")
        plt.ylabel("R2")
        plt.title("Capitulo XIII-A - Comparativo de R2")
        plt.xticks(rotation=25, ha="right")
        plt.tight_layout()
        plt.savefig(plot_dir / "cap13a_r2.png", dpi=140)
        plt.close()

    print("[OK] Capitulo XIII-A summary:")
    print(f"- {outdir / 'cap13a_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
