"""
Phase 6b: Universe filtering + carry-gate analysis.

Runs 4 scenarios to evaluate cost mitigation strategies:
  S1: Gross, 10 instruments (baseline)
  S2: Net (hist swap), 10 instruments (Phase 6 v2)
  S3: Net (hist swap), 3 survivors only (NI225/USDJPY/DAX40)
  S4: Net (hist swap), 10 instruments + carry-gate (theta=10% ATR)

Usage:
    python tools/run_phase6b_universe.py
    python tools/run_phase6b_universe.py --save-only
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
from core.costs import (
    carry_gate_penalty,
    get_swap_scale,
    build_reference_rates,
    SWAP_CALENDAR_MULTIPLIER,
)
from config.instruments import INSTRUMENTS, INSTRUMENT_COSTS
from backtest.metrics import (
    calculate_metrics,
    print_metrics,
    SHOW_INTERACTIVE,
)
import backtest.metrics as metrics_module


ALL_INSTRUMENTS = [
    "SP500", "NASDAQ100", "DAX40", "NIKKEI225",
    "GOLD", "SILVER",
    "EURUSD", "USDJPY", "AUDUSD", "GBPUSD",
]

SURVIVORS = ["NIKKEI225", "USDJPY", "DAX40"]

CARRY_GATE_THRESHOLD = 0.10  # 10% of ATR


def load_data(name):
    path = ROOT / "data" / f"{name}_daily.csv"
    df = pd.read_csv(path, index_col="Date", parse_dates=True)
    return df


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

    combined = combine_forecasts(individual, weights=None, fdm=fdm)
    return combined


def prepare_instruments(names=None):
    if names is None:
        names = ALL_INSTRUMENTS
    instrument_data = []
    for name in names:
        try:
            df = load_data(name)
        except FileNotFoundError:
            print(f"  [SKIP] {name}: data file not found")
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
        print(f"  {name:<12s} {len(close)} bars, "
              f"{close.index[0].date()} to {close.index[-1].date()}")
    return instrument_data


def build_costs_dict(names=None, include_swap=True):
    if names is None:
        names = ALL_INSTRUMENTS
    costs = {}
    for name in names:
        if name not in INSTRUMENT_COSTS:
            continue
        c = dict(INSTRUMENT_COSTS[name])
        if not include_swap:
            c["swap_long_per_unit"] = 0.0
            c["swap_short_per_unit"] = 0.0
        costs[name] = c
    return costs


def run_scenario(label, instrument_data, costs, vol_target, capital,
                 buffer_fraction, rates_daily=None, ref_rates=None,
                 carry_gate=None):
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
        carry_gate=carry_gate,
    )
    metrics = calculate_metrics(results["equity"], results["returns"], capital)
    return results, metrics


def print_comparison_table(scenarios):
    print(f"\n{'='*80}")
    print(f" SCENARIO COMPARISON")
    print(f"{'='*80}")

    labels = [s["label"] for s in scenarios]
    header = f"  {'Metric':<16s}"
    for lab in labels:
        header += f" {lab:>16s}"
    print(header)
    print(f"  {'-'*(18 + 17*len(labels))}")

    rows = [
        ("Sharpe", "sharpe", ".3f"),
        ("Sortino", "sortino", ".3f"),
        ("CAGR %", "cagr_pct", ".2f"),
        ("Annual Vol %", "annual_vol_pct", ".1f"),
        ("Max DD %", "max_dd_pct", ".1f"),
        ("Profit Factor", "profit_factor", ".2f"),
        ("Total PnL $", "total_pnl", ",.0f"),
    ]

    for label_m, key, fmt in rows:
        line = f"  {label_m:<16s}"
        for s in scenarios:
            m = s["metrics"]
            val = m.get(key, 0)
            line += f" {val:>16{fmt}}"
        print(line)

    # IDM row
    line = f"  {'IDM':<16s}"
    for s in scenarios:
        idm = s["results"].get("idm", 0)
        line += f" {idm:>16.4f}"
    print(line)

    # N instruments row
    line = f"  {'N instruments':<16s}"
    for s in scenarios:
        n = len(s["results"]["instrument_returns"])
        line += f" {n:>16d}"
    print(line)


def print_per_instrument_net(scenarios):
    print(f"\n{'='*80}")
    print(f" PER-INSTRUMENT NET PnL COMPARISON")
    print(f"{'='*80}")

    labels = [s["label"] for s in scenarios]
    header = f"  {'Instrument':<12s}"
    for lab in labels:
        header += f" {lab:>16s}"
    print(header)
    print(f"  {'-'*(14 + 17*len(labels))}")

    for name in ALL_INSTRUMENTS:
        line = f"  {name:<12s}"
        for s in scenarios:
            inst_ret = s["results"]["instrument_returns"]
            if name in inst_ret:
                pnl = inst_ret[name].sum()
                line += f" ${pnl:>14,.0f}"
            else:
                line += f" {'---':>16s}"
        print(line)

    # Totals
    line = f"  {'TOTAL':<12s}"
    for s in scenarios:
        total = sum(r.sum() for r in s["results"]["instrument_returns"].values())
        line += f" ${total:>14,.0f}"
    print(line)


def compute_gate_diagnostics(instrument_data, costs, rates_daily, ref_rates,
                             threshold):
    diagnostics = {}
    for inst in instrument_data:
        name = inst["name"]
        close = inst["close"]
        forecast = inst["forecast"]
        vol = price_volatility(close)

        if name not in costs:
            continue

        penalties = []
        for date in forecast.index:
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
            p = carry_gate_penalty(fc_sign, costs[name], v, ss, threshold)
            penalties.append(p)

        if penalties:
            arr = np.array(penalties)
            diagnostics[name] = {
                "avg_penalty": arr.mean(),
                "pct_blocked": (arr == 0).mean() * 100,
                "pct_reduced": ((arr > 0) & (arr < 1)).mean() * 100,
                "pct_pass": (arr >= 1.0).mean() * 100,
            }

    return diagnostics


def print_gate_diagnostics(diagnostics):
    print(f"\n{'='*80}")
    print(f" CARRY-GATE DIAGNOSTICS (threshold = {CARRY_GATE_THRESHOLD:.0%} ATR)")
    print(f"{'='*80}")
    print(f"  {'Instrument':<12s} {'Avg Penalty':>12s} {'Full Pass':>10s} "
          f"{'Reduced':>10s} {'Blocked':>10s}")
    print(f"  {'-'*56}")

    for name in ALL_INSTRUMENTS:
        if name not in diagnostics:
            continue
        d = diagnostics[name]
        print(f"  {name:<12s} {d['avg_penalty']:>11.2f}x "
              f"{d['pct_pass']:>9.1f}% "
              f"{d['pct_reduced']:>9.1f}% "
              f"{d['pct_blocked']:>9.1f}%")

    print(f"\n  Legend: Full Pass = swap is income or zero (no penalty)")
    print(f"          Reduced  = 0 < penalty < 1 (forecast scaled down)")
    print(f"          Blocked  = penalty = 0 (forecast killed)")


def plot_equity_comparison(scenarios, save_path=None):
    n = len(scenarios)
    fig, ax = plt.subplots(figsize=(14, 7))
    colors = ["#2196F3", "#F44336", "#4CAF50", "#FF9800"]

    for i, s in enumerate(scenarios):
        eq = s["results"]["equity"]
        ax.plot(eq.index, eq.values, label=s["label"],
                color=colors[i % len(colors)], linewidth=1.2)

    ax.set_title("Phase 6b: Equity Curves - Universe & Carry-Gate", fontsize=12)
    ax.set_ylabel("Portfolio Equity ($)")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  Chart saved: {save_path}")
    if metrics_module.SHOW_INTERACTIVE:
        plt.show()
    plt.close()


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
    print(f" PHASE 6b: UNIVERSE FILTERING + CARRY-GATE")
    print(f"{'='*80}")
    print(f" Full universe: {len(ALL_INSTRUMENTS)} instruments")
    print(f" Survivors: {SURVIVORS}")
    print(f" Carry-gate threshold: {CARRY_GATE_THRESHOLD:.0%} ATR")
    print(f" Vol target: {vol_target:.0%}, Capital: ${capital:,.0f}, "
          f"Buffer: {buffer_fraction:.0%}")
    print(f"{'='*80}")

    # Load historical interest rates
    from core.carry import load_rates, _rates_to_daily

    print(f"\nLoading historical interest rates...")
    rates_monthly = load_rates(ROOT / "data")
    daily_idx = pd.date_range("1999-01-01", "2027-12-31", freq="B")
    rates_daily = _rates_to_daily(rates_monthly, daily_idx)
    ref_rates = build_reference_rates(rates_daily)
    print(f"  Rates: {rates_monthly.index[0].date()} to "
          f"{rates_monthly.index[-1].date()}")
    for ccy, rate in sorted(ref_rates.items()):
        print(f"    {ccy}: {rate:.2f}%")

    # Prepare all 10 instruments
    print(f"\nPreparing all {len(ALL_INSTRUMENTS)} instruments...")
    all_data = prepare_instruments(ALL_INSTRUMENTS)

    # Prepare survivors-only subset
    print(f"\nPreparing {len(SURVIVORS)} survivors...")
    surv_data = prepare_instruments(SURVIVORS)

    # Build cost dicts
    costs_all = build_costs_dict(ALL_INSTRUMENTS)
    costs_surv = build_costs_dict(SURVIVORS)

    # ---- S1: Gross, 10 instruments ----
    res1, met1 = run_scenario(
        "S1: Gross (10)", all_data, costs=None,
        vol_target=vol_target, capital=capital,
        buffer_fraction=buffer_fraction,
    )
    print(f"  IDM = {res1['idm']:.4f}")

    # ---- S2: Net hist-swap, 10 instruments ----
    res2, met2 = run_scenario(
        "S2: Net (10)", all_data, costs=costs_all,
        vol_target=vol_target, capital=capital,
        buffer_fraction=buffer_fraction,
        rates_daily=rates_daily, ref_rates=ref_rates,
    )
    print(f"  IDM = {res2['idm']:.4f}")

    # ---- S3: Net hist-swap, 3 survivors ----
    res3, met3 = run_scenario(
        "S3: Survivors (3)", surv_data, costs=costs_surv,
        vol_target=vol_target, capital=capital,
        buffer_fraction=buffer_fraction,
        rates_daily=rates_daily, ref_rates=ref_rates,
    )
    print(f"  IDM = {res3['idm']:.4f}")

    # ---- S4: Net hist-swap, 10 instruments + carry-gate ----
    res4, met4 = run_scenario(
        "S4: Gate (10)", all_data, costs=costs_all,
        vol_target=vol_target, capital=capital,
        buffer_fraction=buffer_fraction,
        rates_daily=rates_daily, ref_rates=ref_rates,
        carry_gate=CARRY_GATE_THRESHOLD,
    )
    print(f"  IDM = {res4['idm']:.4f}")

    # ---- Comparison table ----
    scenarios = [
        {"label": "S1:Gross(10)", "results": res1, "metrics": met1},
        {"label": "S2:Net(10)", "results": res2, "metrics": met2},
        {"label": "S3:Surv(3)", "results": res3, "metrics": met3},
        {"label": "S4:Gate(10)", "results": res4, "metrics": met4},
    ]
    print_comparison_table(scenarios)

    # ---- Per-instrument net PnL ----
    # Compare S1 (gross), S2 (net), S4 (gated)
    pnl_scenarios = [
        {"label": "Gross(10)", "results": res1, "metrics": met1},
        {"label": "Net(10)", "results": res2, "metrics": met2},
        {"label": "Gate(10)", "results": res4, "metrics": met4},
    ]
    print_per_instrument_net(pnl_scenarios)

    # ---- Carry-gate diagnostics ----
    print(f"\n  Computing carry-gate diagnostics...")
    diag = compute_gate_diagnostics(
        all_data, costs_all, rates_daily, ref_rates,
        CARRY_GATE_THRESHOLD,
    )
    print_gate_diagnostics(diag)

    # ---- Equity curve plot ----
    plot_equity_comparison(
        scenarios,
        save_path=analysis_dir / "phase6b_equity_comparison.png",
    )

    # ---- Summary ----
    print(f"\n{'='*80}")
    print(f" PHASE 6b SUMMARY")
    print(f"{'='*80}")
    print(f"  S1 Gross (10):      Sharpe {met1['sharpe']:.3f}")
    print(f"  S2 Net (10):        Sharpe {met2['sharpe']:.3f}")
    print(f"  S3 Survivors (3):   Sharpe {met3['sharpe']:.3f}")
    print(f"  S4 Gated (10):      Sharpe {met4['sharpe']:.3f}")

    best_label = "S3 Survivors" if met3["sharpe"] > met4["sharpe"] else "S4 Gated"
    best_sharpe = max(met3["sharpe"], met4["sharpe"])
    print(f"\n  Best net strategy: {best_label} (Sharpe {best_sharpe:.3f})")

    if best_sharpe > 0:
        print(f"  System is PROFITABLE after costs.")
    else:
        print(f"  WARNING: System remains UNPROFITABLE after costs.")

    print(f"\n{'='*80}")
    print(f" PHASE 6b COMPLETE")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
