"""
Phase 6b theta sweep: test carry-gate at multiple thresholds.

Runs the 10-instrument portfolio with carry-gate at different theta
values to find whether any threshold produces a viable system.

Usage:
    python tools/run_phase6b_theta.py
    python tools/run_phase6b_theta.py --save-only
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if "--save-only" in sys.argv:
    import matplotlib
    matplotlib.use("Agg")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from core.forecast import (
    ewmac_forecast,
    combine_forecasts,
    EWMAC_SPEEDS,
    price_volatility,
)
from core.portfolio import run_portfolio_backtest
from core.costs import build_reference_rates, carry_gate_penalty, get_swap_scale
from config.instruments import INSTRUMENTS, INSTRUMENT_COSTS
from backtest.metrics import calculate_metrics, SHOW_INTERACTIVE
import backtest.metrics as metrics_module


ALL_INSTRUMENTS = [
    "SP500", "NASDAQ100", "DAX40", "NIKKEI225",
    "GOLD", "SILVER",
    "EURUSD", "USDJPY", "AUDUSD", "GBPUSD",
]

THETAS = [None, 0.20, 0.15, 0.10, 0.05, 0.03]


def load_data(name):
    path = ROOT / "data" / f"{name}_daily.csv"
    return pd.read_csv(path, index_col="Date", parse_dates=True)


def calculate_ewmac_combined(close):
    individual = []
    for fast, slow in EWMAC_SPEEDS:
        fc = ewmac_forecast(close, fast, slow)
        individual.append(fc)
    df_fc = pd.concat(individual, axis=1).dropna()
    n = len(individual)
    weights = np.array([1.0 / n] * n)
    corr = df_fc.corr().values
    w_corr_w = weights @ corr @ weights
    fdm = 1.0 / np.sqrt(w_corr_w)
    return combine_forecasts(individual, weights=None, fdm=fdm)


def prepare_instruments():
    instrument_data = []
    for name in ALL_INSTRUMENTS:
        try:
            df = load_data(name)
        except FileNotFoundError:
            continue
        close = df["Close"]
        cfg = INSTRUMENTS[name]
        forecast = calculate_ewmac_combined(close)
        instrument_data.append({
            "name": name,
            "close": close,
            "forecast": forecast,
            "point_value": cfg.get("point_value", 1.0),
        })
        print(f"  {name:<12s} {len(close)} bars")
    return instrument_data


def build_costs_dict():
    costs = {}
    for name in ALL_INSTRUMENTS:
        if name in INSTRUMENT_COSTS:
            costs[name] = dict(INSTRUMENT_COSTS[name])
    return costs


def compute_gate_diagnostics(instrument_data, costs, rates_daily, ref_rates,
                             theta):
    """Quick diagnostic: avg penalty and block rate per instrument."""
    diagnostics = {}
    for inst in instrument_data:
        name = inst["name"]
        close = inst["close"]
        forecast = inst["forecast"]
        vol = price_volatility(close)
        if name not in costs:
            continue

        penalties = []
        for date in forecast.index[::5]:  # sample every 5 days for speed
            fc = forecast.get(date, 0)
            v = vol.get(date, np.nan)
            if pd.isna(v) or v == 0 or pd.isna(fc) or fc == 0:
                continue
            ss = 1.0
            if rates_daily is not None and ref_rates is not None:
                if name in INSTRUMENTS:
                    ss = get_swap_scale(name, INSTRUMENTS[name], date,
                                        rates_daily, ref_rates)
            fc_sign = 1 if fc > 0 else -1
            p = carry_gate_penalty(fc_sign, costs[name], v, ss, theta)
            penalties.append(p)

        if penalties:
            arr = np.array(penalties)
            diagnostics[name] = {
                "avg_penalty": arr.mean(),
                "pct_blocked": (arr == 0).mean() * 100,
                "pct_pass": (arr >= 1.0).mean() * 100,
            }
    return diagnostics


def yearly_pnl(returns):
    """Returns dict of {year: pnl}."""
    result = {}
    for yr in sorted(returns.index.year.unique()):
        mask = returns.index.year == yr
        result[yr] = returns[mask].sum()
    return result


def main():
    save_only = "--save-only" in sys.argv
    if save_only:
        metrics_module.SHOW_INTERACTIVE = False

    vol_target = 0.12
    capital = 100000
    buffer_fraction = 0.10
    analysis_dir = ROOT / "analysis"
    analysis_dir.mkdir(exist_ok=True)

    print(f"{'='*80}")
    print(f" PHASE 6b THETA SWEEP: CARRY-GATE THRESHOLD ANALYSIS")
    print(f"{'='*80}")
    print(f" 10 instruments, EWMAC, hist swap")
    print(f" Thetas: {THETAS}")
    print(f"{'='*80}")

    # Load rates
    from core.carry import load_rates, _rates_to_daily
    rates_monthly = load_rates(ROOT / "data")
    daily_idx = pd.date_range("1999-01-01", "2027-12-31", freq="B")
    rates_daily = _rates_to_daily(rates_monthly, daily_idx)
    ref_rates = build_reference_rates(rates_daily)

    # Prepare data
    print(f"\nPreparing instruments...")
    instrument_data = prepare_instruments()
    costs = build_costs_dict()

    # Run scenarios
    all_results = []
    for theta in THETAS:
        label = "No gate" if theta is None else f"θ={theta:.0%}"
        print(f"\n  Running {label}...")
        results = run_portfolio_backtest(
            instrument_data,
            vol_target_annual=vol_target,
            capital=capital,
            buffer_fraction=buffer_fraction,
            idm=None,
            costs=costs,
            rates_daily=rates_daily,
            ref_rates=ref_rates,
            carry_gate=theta,
        )
        metrics = calculate_metrics(
            results["equity"], results["returns"], capital
        )
        all_results.append({
            "theta": theta,
            "label": label,
            "results": results,
            "metrics": metrics,
        })
        print(f"    Sharpe: {metrics['sharpe']:.3f}  "
              f"PF: {metrics['profit_factor']:.3f}  "
              f"PnL: ${metrics['total_pnl']:,.0f}")

    # === COMPARISON TABLE ===
    print(f"\n{'='*100}")
    print(f" THETA SWEEP COMPARISON (10 instruments, net hist swap)")
    print(f"{'='*100}")

    header = f"  {'Metric':<16s}"
    for r in all_results:
        header += f" {r['label']:>12s}"
    print(header)
    print(f"  {'-'*(18 + 13*len(all_results))}")

    rows = [
        ("Sharpe", "sharpe", ".3f"),
        ("Sortino", "sortino", ".3f"),
        ("CAGR %", "cagr_pct", ".2f"),
        ("Annual Vol %", "annual_vol_pct", ".1f"),
        ("Max DD %", "max_dd_pct", ".1f"),
        ("Profit Factor", "profit_factor", ".3f"),
        ("Calmar", "calmar", ".3f"),
        ("Win Rate %", "win_rate_pct", ".1f"),
        ("Total PnL $", "total_pnl", ",.0f"),
        ("% Pos Months", "pct_positive_months", ".1f"),
    ]
    for label_m, key, fmt in rows:
        line = f"  {label_m:<16s}"
        for r in all_results:
            val = r["metrics"].get(key, 0)
            line += f" {val:>12{fmt}}"
        print(line)

    # IDM
    line = f"  {'IDM':<16s}"
    for r in all_results:
        line += f" {r['results']['idm']:>12.4f}"
    print(line)

    # === PER-INSTRUMENT PnL TABLE ===
    print(f"\n{'='*100}")
    print(f" PER-INSTRUMENT NET PnL BY THETA")
    print(f"{'='*100}")

    header = f"  {'Instrument':<12s}"
    for r in all_results:
        header += f" {r['label']:>12s}"
    print(header)
    print(f"  {'-'*(14 + 13*len(all_results))}")

    for name in ALL_INSTRUMENTS:
        line = f"  {name:<12s}"
        for r in all_results:
            inst_ret = r["results"]["instrument_returns"]
            if name in inst_ret:
                pnl = inst_ret[name].sum()
                line += f" ${pnl:>10,.0f}"
            else:
                line += f" {'---':>12s}"
        print(line)

    line = f"  {'TOTAL':<12s}"
    for r in all_results:
        total = sum(v.sum() for v in r["results"]["instrument_returns"].values())
        line += f" ${total:>10,.0f}"
    print(line)

    # === GATE DIAGNOSTICS for θ=0.05 ===
    print(f"\n{'='*80}")
    print(f" CARRY-GATE DIAGNOSTICS: θ=5% vs θ=10%")
    print(f"{'='*80}")
    print(f"  {'Instrument':<12s} {'Avg P (10%)':>12s} {'Block (10%)':>12s} "
          f"{'Avg P (5%)':>12s} {'Block (5%)':>12s}")
    print(f"  {'-'*62}")

    diag_10 = compute_gate_diagnostics(
        instrument_data, costs, rates_daily, ref_rates, 0.10)
    diag_05 = compute_gate_diagnostics(
        instrument_data, costs, rates_daily, ref_rates, 0.05)

    for name in ALL_INSTRUMENTS:
        d10 = diag_10.get(name, {"avg_penalty": 1, "pct_blocked": 0})
        d05 = diag_05.get(name, {"avg_penalty": 1, "pct_blocked": 0})
        print(f"  {name:<12s} {d10['avg_penalty']:>11.2f}x "
              f"{d10['pct_blocked']:>10.1f}% "
              f"{d05['avg_penalty']:>11.2f}x "
              f"{d05['pct_blocked']:>10.1f}%")

    # === YEARLY PnL for key scenarios ===
    print(f"\n{'='*80}")
    print(f" YEAR-BY-YEAR PnL: No Gate vs θ=10% vs θ=5% vs θ=3%")
    print(f"{'='*80}")

    key_indices = [0, 3, 4, 5]  # No gate, θ=10%, θ=5%, θ=3%
    key_results = [all_results[i] for i in key_indices if i < len(all_results)]

    header = f"  {'Year':>4s}"
    for r in key_results:
        header += f" {r['label']:>12s}"
    print(header)
    print(f"  {'-'*(6 + 13*len(key_results))}")

    all_years = set()
    for r in key_results:
        all_years.update(r["results"]["returns"].index.year.unique())
    for yr in sorted(all_years):
        line = f"  {yr:>4d}"
        for r in key_results:
            ret = r["results"]["returns"]
            mask = ret.index.year == yr
            if mask.any():
                pnl = ret[mask].sum()
                sign = "+" if pnl >= 0 else ""
                line += f" {sign}${abs(pnl):>10,.0f}"
            else:
                line += f" {'---':>12s}"
        print(line)

    # === EQUITY PLOT ===
    fig, ax = plt.subplots(figsize=(14, 7))
    colors = ["#F44336", "#FF9800", "#FFC107", "#4CAF50", "#2196F3", "#9C27B0"]
    for i, r in enumerate(all_results):
        eq = r["results"]["equity"]
        ax.plot(eq.index, eq.values, label=r["label"],
                color=colors[i % len(colors)], linewidth=1.2)

    ax.axhline(y=capital, color="gray", linestyle="--", alpha=0.5)
    ax.set_title("Carry-Gate Theta Sweep (10 instruments, net hist swap)")
    ax.set_ylabel("Equity ($)")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    plt.tight_layout()
    plt.savefig(analysis_dir / "phase6b_theta_sweep.png", dpi=150,
                bbox_inches="tight")
    print(f"\n  Chart saved: {analysis_dir / 'phase6b_theta_sweep.png'}")
    if metrics_module.SHOW_INTERACTIVE:
        plt.show()
    plt.close()

    # === FINAL VERDICT ===
    print(f"\n{'='*80}")
    print(f" VERDICT")
    print(f"{'='*80}")

    best = max(all_results, key=lambda r: r["metrics"]["sharpe"])
    print(f"  Best theta: {best['label']} (Sharpe {best['metrics']['sharpe']:.3f})")
    print(f"  Profit Factor: {best['metrics']['profit_factor']:.3f}")
    print(f"  Max Drawdown: {best['metrics']['max_dd_pct']:.1f}%")

    pf = best["metrics"]["profit_factor"]
    if pf >= 1.10:
        print(f"\n  PF >= 1.10: System has VIABLE edge after costs.")
    elif pf > 1.0:
        print(f"\n  1.0 < PF < 1.10: MARGINAL edge, insufficient for live.")
    else:
        print(f"\n  PF <= 1.0: NO EDGE. CFDs are inoperable for EWMAC trend following.")
        print(f"  Conclusion: seek other instruments (micro futures) or")
        print(f"  accept EWMAC as non-standalone component.")

    print(f"\n{'='*80}")


if __name__ == "__main__":
    main()
