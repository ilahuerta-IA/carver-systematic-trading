"""
Phase 6: Transaction cost analysis.

Compares portfolio performance GROSS (no costs) vs NET (spread +
commission + swap) using Darwinex Zero cost parameters.

IMPORTANT: Swap rates are current (2026-03) levels. During ZIRP
(2009-2022), swap costs were near zero. The NET results with swap
represent the WORST CASE (current rate environment). The NO-SWAP
scenario gives a better estimate of historical average impact.

Usage:
    python tools/run_phase6_costs.py
    python tools/run_phase6_costs.py --save-only
    python tools/run_phase6_costs.py --no-swap
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
from config.instruments import INSTRUMENTS, INSTRUMENT_COSTS
from backtest.metrics import (
    calculate_metrics,
    print_metrics,
    plot_equity_drawdown,
    SHOW_INTERACTIVE,
)
import backtest.metrics as metrics_module


ALL_INSTRUMENTS = [
    "SP500", "NASDAQ100", "DAX40", "NIKKEI225",
    "GOLD", "SILVER",
    "EURUSD", "USDJPY", "AUDUSD", "GBPUSD",
]


def load_data(name):
    """Load daily CSV from data/ folder."""
    path = ROOT / "data" / f"{name}_daily.csv"
    df = pd.read_csv(path, index_col="Date", parse_dates=True)
    return df


def calculate_ewmac_combined(close):
    """Calculate combined EWMAC forecast (4 speeds) with empirical FDM."""
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


def prepare_instruments():
    """Prepare EWMAC-only forecast data for all instruments."""
    instrument_data = []

    for name in ALL_INSTRUMENTS:
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


def build_costs_dict(include_swap=True):
    """
    Build the costs dict expected by the portfolio engine.

    Args:
        include_swap: if False, zero out swap to show execution-only costs.

    Returns:
        dict of {name: cost_dict}
    """
    costs = {}
    for name in ALL_INSTRUMENTS:
        if name not in INSTRUMENT_COSTS:
            continue
        c = dict(INSTRUMENT_COSTS[name])
        if not include_swap:
            c["swap_long_per_unit"] = 0.0
            c["swap_short_per_unit"] = 0.0
        costs[name] = c
    return costs


def run_scenario(label, instrument_data, costs, vol_target, capital,
                 buffer_fraction, rates_daily=None, ref_rates=None):
    """Run one scenario (gross, net, or no-swap) and return results + metrics."""
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
    )
    metrics = calculate_metrics(results["equity"], results["returns"], capital)
    return results, metrics


def print_comparison_table(scenarios):
    """Print side-by-side comparison of all scenarios."""
    print(f"\n{'='*70}")
    print(f" PORTFOLIO COMPARISON: GROSS vs NET")
    print(f"{'='*70}")

    # Build header dynamically
    labels = [s["label"] for s in scenarios]
    header = f"  {'Metric':<16s}"
    for lab in labels:
        header += f" {lab:>14s}"
    if len(labels) >= 2:
        header += f" {'Impact':>10s}"
    print(header)
    print(f"  {'-'*(18 + 15*len(labels) + 11)}")

    comparisons = [
        ("Sharpe", "sharpe", ".3f"),
        ("Sortino", "sortino", ".3f"),
        ("CAGR %", "cagr_pct", ".2f"),
        ("Annual Vol %", "annual_vol_pct", ".1f"),
        ("Max DD %", "max_dd_pct", ".1f"),
        ("Profit Factor", "profit_factor", ".2f"),
        ("Calmar", "calmar", ".3f"),
        ("Total PnL $", "total_pnl", ",.0f"),
    ]

    for label_m, key, fmt in comparisons:
        line = f"  {label_m:<16s}"
        for s in scenarios:
            m = s["metrics"]
            val = m.get(key, 0)
            line += f" {val:>14{fmt}}"
        if len(scenarios) >= 2:
            delta = scenarios[-1]["metrics"].get(key, 0) - scenarios[0]["metrics"].get(key, 0)
            sign = "+" if delta > 0 else ""
            line += f" {sign}{delta:>9{fmt}}"
        print(line)


def print_cost_breakdown(results_net, results_gross, capital):
    """Print cost breakdown by instrument and type."""
    print(f"\n{'='*70}")
    print(f" COST BREAKDOWN BY INSTRUMENT")
    print(f"{'='*70}")

    inst_trade = results_net["inst_trade_costs"]
    inst_swap = results_net["inst_swap_costs"]
    inst_ret_net = results_net["instrument_returns"]
    inst_ret_gross = results_gross["instrument_returns"]

    print(f"  {'Instrument':<12s} {'Gross PnL':>11s} {'Trade Cost':>11s} "
          f"{'Swap Cost':>11s} {'Total Cost':>11s} {'Net PnL':>11s} "
          f"{'Cost/Gross':>10s}")
    print(f"  {'-'*80}")

    total_gross = 0
    total_trade = 0
    total_swap = 0
    total_net = 0
    rows = []

    for name in sorted(inst_ret_gross.keys()):
        gross_pnl = inst_ret_gross[name].sum()
        net_pnl = inst_ret_net[name].sum()
        trade_c = inst_trade.get(name, 0)
        swap_c = inst_swap.get(name, 0)
        total_c = trade_c + swap_c

        total_gross += gross_pnl
        total_trade += trade_c
        total_swap += swap_c
        total_net += net_pnl

        if abs(gross_pnl) > 0.01:
            ratio = total_c / abs(gross_pnl) * 100
        else:
            ratio = 0
        rows.append((name, gross_pnl, trade_c, swap_c, total_c, net_pnl, ratio))

    # Sort by net PnL descending
    rows.sort(key=lambda r: r[5], reverse=True)

    for name, gross_pnl, trade_c, swap_c, total_c, net_pnl, ratio in rows:
        swap_sign = "" if swap_c >= 0 else "-"
        print(f"  {name:<12s} ${gross_pnl:>10,.0f} ${trade_c:>10,.0f} "
              f"{swap_sign}${abs(swap_c):>9,.0f} ${total_c:>10,.0f} "
              f"${net_pnl:>10,.0f} {ratio:>8.0f}%")

    total_cost = total_trade + total_swap
    print(f"  {'-'*80}")
    swap_sign = "" if total_swap >= 0 else "-"
    print(f"  {'TOTAL':<12s} ${total_gross:>10,.0f} ${total_trade:>10,.0f} "
          f"{swap_sign}${abs(total_swap):>9,.0f} ${total_cost:>10,.0f} "
          f"${total_net:>10,.0f}")

    # Summary
    n_years = len(results_net["equity"]) / 252
    print(f"\n  Cost Summary ({n_years:.1f} years):")
    print(f"    Total trade costs (spread + commission): ${total_trade:>12,.0f} "
          f"(${total_trade/n_years:>8,.0f}/yr)")
    if total_swap >= 0:
        print(f"    Total swap costs:                        ${total_swap:>12,.0f} "
              f"(${total_swap/n_years:>8,.0f}/yr)")
    else:
        print(f"    Total swap (net income):                -${abs(total_swap):>12,.0f} "
              f"(-${abs(total_swap)/n_years:>8,.0f}/yr)")
    print(f"    Total all costs:                         ${total_cost:>12,.0f} "
          f"(${total_cost/n_years:>8,.0f}/yr)")
    print(f"    Costs as % of gross PnL:                 "
          f"{total_cost/abs(total_gross)*100:>11.1f}%")

    # Profitable instruments after costs
    profitable = sum(1 for _, _, _, _, _, net, _ in rows if net > 0)
    print(f"\n  Profitable instruments after costs: "
          f"{profitable}/{len(rows)}")


def print_instrument_net_metrics(results_net, capital):
    """Print per-instrument Sharpe and key metrics after costs."""
    print(f"\n{'='*70}")
    print(f" PER-INSTRUMENT NET PERFORMANCE")
    print(f"{'='*70}")

    inst_ret = results_net["instrument_returns"]
    n_inst = len(inst_ret)
    alloc_cap = capital / n_inst

    print(f"  {'Instrument':<12s} {'Net PnL':>10s} {'CAGR%':>7s} "
          f"{'AnnVol%':>8s} {'Sharpe':>7s} {'Max DD%':>8s}")
    print(f"  {'-'*56}")

    for name in ALL_INSTRUMENTS:
        if name not in inst_ret:
            continue
        ret = inst_ret[name]
        cum = ret.cumsum() + alloc_cap
        total = ret.sum()
        n_years = len(ret) / 252
        if n_years > 0 and alloc_cap > 0:
            final = alloc_cap + total
            if final > 0:
                cagr = ((final / alloc_cap) ** (1.0 / n_years) - 1) * 100
            else:
                cagr = -100.0
        else:
            cagr = 0

        ann_ret = ret.mean() * 252
        ann_vol = ret.std() * np.sqrt(252)
        sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
        ann_vol_pct = ann_vol / alloc_cap * 100

        peak = cum.expanding().max()
        dd = cum - peak
        max_dd_pct = (dd.min() / alloc_cap * 100) if alloc_cap > 0 else 0

        print(f"  {name:<12s} ${total:>9,.0f} {cagr:>6.1f}% "
              f"{ann_vol_pct:>7.1f}% {sharpe:>7.2f} {max_dd_pct:>7.1f}%")


def plot_equity_comparison(scenarios, save_path=None):
    """Plot overlay of equity curves for all scenarios."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8),
                                    gridspec_kw={"height_ratios": [3, 1]})

    colors = ["#2196F3", "#F44336", "#FF9800"]
    for i, s in enumerate(scenarios):
        eq = s["results"]["equity"]
        ax1.plot(eq.index, eq.values, label=s["label"],
                 color=colors[i % len(colors)], linewidth=1.2)

    ax1.set_title("Phase 6: Equity Curves - Gross vs Net", fontsize=12)
    ax1.set_ylabel("Portfolio Equity ($)")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax1.xaxis.set_major_locator(mdates.YearLocator(2))

    # Cumulative cost curve
    if len(scenarios) >= 2:
        costs_series = scenarios[-1]["results"]["total_costs"]
        cum_costs = costs_series.cumsum()
        ax2.fill_between(cum_costs.index, 0, cum_costs.values,
                         color="#F44336", alpha=0.3, label="Cumulative Costs")
        ax2.plot(cum_costs.index, cum_costs.values, color="#F44336",
                 linewidth=0.8)
        ax2.set_ylabel("Cumulative Costs ($)")
        ax2.set_xlabel("Date")
        ax2.legend(loc="upper left")
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax2.xaxis.set_major_locator(mdates.YearLocator(2))

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  Chart saved: {save_path}")
    if metrics_module.SHOW_INTERACTIVE:
        plt.show()
    plt.close()


def main():
    save_only = "--save-only" in sys.argv
    no_swap = "--no-swap" in sys.argv

    if save_only:
        metrics_module.SHOW_INTERACTIVE = False

    vol_target = 0.12
    capital = 100000
    buffer_fraction = 0.10
    analysis_dir = ROOT / "analysis"
    analysis_dir.mkdir(exist_ok=True)

    print(f"{'='*70}")
    print(f" PHASE 6: TRANSACTION COST ANALYSIS")
    print(f"{'='*70}")
    print(f" Portfolio: {len(ALL_INSTRUMENTS)} instruments, EWMAC only")
    print(f" Vol target: {vol_target:.0%}, Capital: ${capital:,.0f}, "
          f"Buffer: {buffer_fraction:.0%}")
    print(f" Costs: Darwinex Zero (spread + commission + swap)")
    if no_swap:
        print(f" NOTE: --no-swap flag active, swap costs excluded")
    print(f" Swap: TIME-VARYING using historical interest rates.")
    print(f"       Swap calibrated at 2026-03 rates, scaled by")
    print(f"       rate(date) / rate(2026-03) for each day.")
    print(f"{'='*70}")

    # Load historical interest rates for time-varying swap
    from core.carry import load_rates, _rates_to_daily
    from core.costs import build_reference_rates

    print(f"\nLoading historical interest rates...")
    rates_monthly = load_rates(ROOT / "data")
    daily_idx = pd.date_range("1999-01-01", "2027-12-31", freq="B")
    rates_daily = _rates_to_daily(rates_monthly, daily_idx)
    ref_rates = build_reference_rates(rates_daily)
    print(f"  Rates: {rates_monthly.index[0].date()} to "
          f"{rates_monthly.index[-1].date()}, "
          f"{len(rates_monthly.columns)} currencies")
    print(f"  Reference rates (swap calibration):")
    for ccy, rate in sorted(ref_rates.items()):
        print(f"    {ccy}: {rate:.2f}%")

    # Prepare instruments (EWMAC only)
    print(f"\nPreparing instruments...")
    instrument_data = prepare_instruments()
    n_inst = len(instrument_data)

    if n_inst == 0:
        print("ERROR: No instruments loaded.")
        sys.exit(1)

    print(f"\nLoaded {n_inst} instruments.")

    # --- SCENARIO 1: GROSS (no costs) ---
    res_gross, met_gross = run_scenario(
        "Gross", instrument_data, costs=None,
        vol_target=vol_target, capital=capital,
        buffer_fraction=buffer_fraction
    )
    idm = res_gross["idm"]
    print(f"  IDM: {idm:.4f}")
    print_metrics(met_gross, title="Portfolio GROSS (no costs)")

    # --- SCENARIO 2: NET with time-varying swap ---
    costs_full = build_costs_dict(include_swap=not no_swap)
    res_net, met_net = run_scenario(
        "Net (hist swap)" if not no_swap else "Net (no swap)",
        instrument_data, costs=costs_full,
        vol_target=vol_target, capital=capital,
        buffer_fraction=buffer_fraction,
        rates_daily=rates_daily if not no_swap else None,
        ref_rates=ref_rates if not no_swap else None,
    )
    net_label = "Net (hist swap)" if not no_swap else "Net (no swap)"
    print_metrics(met_net, title=f"Portfolio {net_label}")

    # --- SCENARIO 3: NET no swap (if not already --no-swap) ---
    scenarios = [
        {"label": "Gross", "results": res_gross, "metrics": met_gross},
    ]

    if not no_swap:
        costs_no_swap = build_costs_dict(include_swap=False)
        res_no_swap, met_no_swap = run_scenario(
            "Net (no swap)", instrument_data, costs=costs_no_swap,
            vol_target=vol_target, capital=capital,
            buffer_fraction=buffer_fraction
        )
        scenarios.append({
            "label": "Net (no swap)",
            "results": res_no_swap,
            "metrics": met_no_swap,
        })

    scenarios.append({
        "label": net_label,
        "results": res_net,
        "metrics": met_net,
    })

    # --- Comparison table ---
    print_comparison_table(scenarios)

    # --- Cost breakdown (always from full-cost scenario) ---
    print_cost_breakdown(res_net, res_gross, capital)

    # --- Per-instrument net metrics ---
    print_instrument_net_metrics(res_net, capital)

    # --- Equity curve comparison plot ---
    plot_equity_comparison(
        scenarios,
        save_path=analysis_dir / "phase6_equity_gross_vs_net.png",
    )

    # --- Key takeaway ---
    gross_sharpe = met_gross["sharpe"]
    net_sharpe = met_net["sharpe"]
    cost_drag = gross_sharpe - net_sharpe

    print(f"\n{'='*70}")
    print(f" PHASE 6 SUMMARY")
    print(f"{'='*70}")
    print(f"  Gross Sharpe: {gross_sharpe:.3f}")
    print(f"  Net Sharpe:   {net_sharpe:.3f}")
    print(f"  Cost drag:    {cost_drag:.3f} Sharpe units")

    if net_sharpe > 0:
        print(f"\n  System remains PROFITABLE after costs.")
    else:
        print(f"\n  WARNING: System is UNPROFITABLE after costs.")

    total_cost = sum(res_net["inst_trade_costs"].values()) + \
                 sum(res_net["inst_swap_costs"].values())
    n_years = len(res_net["equity"]) / 252
    print(f"  Annual cost burden: ${total_cost/n_years:,.0f}/yr "
          f"on ${capital:,.0f} account")

    print(f"\n{'='*70}")
    print(f" PHASE 6 COMPLETE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
