"""
Phase 5: Multi-instrument portfolio with IDM.

Runs portfolio backtest on all 10 instruments with:
    Mode A: EWMAC only (all instruments)
    Mode B: EWMAC + Carry (8 carry + 2 commodity EWMAC-only)

Validates:
    1. IDM calculation from instrument return correlations
    2. Correlation matrix between instruments
    3. Portfolio Sharpe > best individual instrument Sharpe
    4. Carry impact at portfolio level (A vs B)

Usage:
    python tools/run_phase5_portfolio.py
    python tools/run_phase5_portfolio.py --save-only
    python tools/run_phase5_portfolio.py --mode A
    python tools/run_phase5_portfolio.py --mode B
    python tools/run_phase5_portfolio.py --mode both
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
from core.carry import (
    load_rates,
    carry_forecast,
    calibrate_carry_scalar,
    _rates_to_daily,
)
from core.portfolio import (
    instrument_correlation_matrix,
    calculate_idm,
    run_portfolio_backtest,
)
from config.instruments import INSTRUMENTS
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

WEIGHT_TREND = 0.60
WEIGHT_CARRY = 0.40


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
    return combined, fdm


def calculate_trend_carry_combined(ewmac_combined, carry_fc):
    """Combine EWMAC + carry with trend-carry FDM."""
    df = pd.concat([ewmac_combined, carry_fc], axis=1).dropna()
    if len(df) < 100:
        return ewmac_combined, 1.0, 0.0

    corr = df.iloc[:, 0].corr(df.iloc[:, 1])
    wt, wc = WEIGHT_TREND, WEIGHT_CARRY
    w_corr_w = wt**2 + wc**2 + 2 * wt * wc * corr
    fdm = 1.0 / np.sqrt(w_corr_w)

    combined = combine_forecasts(
        [ewmac_combined, carry_fc],
        weights=[wt, wc],
        fdm=fdm,
    )
    return combined, fdm, corr


def prepare_instruments(mode, rates_daily=None):
    """
    Prepare forecast data for all instruments.

    Args:
        mode: "A" (EWMAC only) or "B" (EWMAC + Carry where applicable)
        rates_daily: pd.DataFrame (required for mode B)

    Returns:
        list of dicts for run_portfolio_backtest
    """
    instrument_data = []

    for name in ALL_INSTRUMENTS:
        try:
            df = load_data(name)
        except FileNotFoundError:
            print(f"  [SKIP] {name}: data file not found")
            continue

        close = df["Close"]
        cfg = INSTRUMENTS[name]

        # EWMAC combined (always)
        ewmac_combined, ewmac_fdm = calculate_ewmac_combined(close)

        if mode == "A":
            forecast = ewmac_combined
            forecast_mode = "EWMAC"
        elif mode == "B":
            use_carry = cfg["asset_class"] != "commodity"
            if use_carry and rates_daily is not None:
                carry_fc = carry_forecast(name, close, rates_daily)
                forecast, _, _ = calculate_trend_carry_combined(
                    ewmac_combined, carry_fc
                )
                forecast_mode = "EWMAC+Carry"
            else:
                forecast = ewmac_combined
                forecast_mode = "EWMAC"
        else:
            raise ValueError(f"Unknown mode: {mode}")

        instrument_data.append({
            "name": name,
            "close": close,
            "forecast": forecast,
            "point_value": cfg.get("point_value", 1.0),
            "forecast_mode": forecast_mode,
        })

        print(f"  {name:<12s} [{forecast_mode:<12s}] "
              f"{len(close)} bars, "
              f"{close.index[0].date()} to {close.index[-1].date()}")

    return instrument_data


def print_correlation_matrix(corr_matrix):
    """Pretty-print the instrument correlation matrix."""
    print(f"\n  Instrument Correlation Matrix (daily returns):")
    names = corr_matrix.columns.tolist()

    # Header
    header = "  " + " " * 12
    for n in names:
        header += f"{n:>8s}"
    print(header)
    print("  " + "-" * (12 + 8 * len(names)))

    for i, row_name in enumerate(names):
        line = f"  {row_name:<12s}"
        for j, col_name in enumerate(names):
            val = corr_matrix.iloc[i, j]
            if i == j:
                line += "    ----"
            elif pd.isna(val):
                line += "     N/A"
            else:
                line += f"{val:>8.2f}"
        print(line)


def print_instrument_contributions(results, capital):
    """Print per-instrument contribution to portfolio."""
    print(f"\n  Per-Instrument Contributions:")
    header = (f"  {'Instrument':<12s} {'Total PnL':>12s} {'CAGR%':>7s} "
              f"{'Ann Vol%':>9s} {'Sharpe':>7s} {'MaxDD%':>7s} "
              f"{'Contrib%':>9s}")
    print(header)
    print(f"  {'-'*70}")

    total_pnl = sum(
        ret.sum() for ret in results["instrument_returns"].values()
    )

    for name, ret in results["instrument_returns"].items():
        # Calculate individual metrics from this instrument's returns
        cumulative = ret.cumsum() + capital / len(results["instrument_returns"])
        inst_total = ret.sum()
        years = (ret.index[-1] - ret.index[0]).days / 365.25

        # Simple annualized metrics
        ann_return = inst_total / years if years > 0 else 0
        daily_std = ret.std()
        ann_vol = daily_std * np.sqrt(256)
        ann_vol_pct = ann_vol / capital * 100

        # Contribution to total PnL
        contrib = inst_total / total_pnl * 100 if total_pnl != 0 else 0

        # Simple Sharpe from returns
        if daily_std > 0:
            sharpe = (ret.mean() / daily_std) * np.sqrt(256)
        else:
            sharpe = 0.0

        # CAGR approximation
        initial = capital / len(results["instrument_returns"])
        final = initial + inst_total
        if initial > 0 and final > 0 and years > 0:
            cagr_pct = ((final / initial) ** (1 / years) - 1) * 100
        else:
            cagr_pct = 0

        # Max drawdown of this instrument's cumulative PnL
        cum_pnl = ret.cumsum()
        peak = cum_pnl.expanding().max()
        dd = cum_pnl - peak
        # Express as % of allocated capital
        alloc_cap = capital / len(results["instrument_returns"])
        max_dd_pct = (dd.min() / alloc_cap * 100) if alloc_cap > 0 else 0

        print(f"  {name:<12s} ${inst_total:>10,.0f} {cagr_pct:>6.1f}% "
              f"{ann_vol_pct:>8.1f}% {sharpe:>7.2f} {max_dd_pct:>6.1f}% "
              f"{contrib:>8.1f}%")


def run_mode(mode, rates_daily=None, show_plots=True, save_charts=False,
             analysis_dir=None, vol_target=0.12, capital=100000,
             buffer_fraction=0.10):
    """
    Run one mode of the portfolio backtest.

    Args:
        mode: "A" (EWMAC only) or "B" (EWMAC + Carry)

    Returns:
        dict with portfolio results and metrics
    """
    mode_label = "EWMAC only" if mode == "A" else "EWMAC + Carry"

    print(f"\n{'='*70}")
    print(f" PHASE 5 MODE {mode}: {mode_label}")
    print(f" Portfolio: {len(ALL_INSTRUMENTS)} instruments, "
          f"equal weight ({1/len(ALL_INSTRUMENTS):.0%} each)")
    print(f" Vol target: {vol_target:.0%}, Capital: ${capital:,.0f}, "
          f"Buffer: {buffer_fraction:.0%}")
    print(f"{'='*70}")

    # Prepare forecasts
    print(f"\nPreparing instruments...")
    instrument_data = prepare_instruments(mode, rates_daily)
    n_inst = len(instrument_data)

    if n_inst == 0:
        print("ERROR: No instruments loaded.")
        return None

    print(f"\nLoaded {n_inst} instruments. Running portfolio backtest...")

    # Run portfolio backtest (auto-calculates IDM)
    results = run_portfolio_backtest(
        instrument_data,
        vol_target_annual=vol_target,
        capital=capital,
        buffer_fraction=buffer_fraction,
        idm=None,  # auto-calculate
    )

    idm = results["idm"]
    corr_matrix = results["corr_matrix"]

    print(f"\n  IDM (calculated): {idm:.4f}")
    print(f"  Instrument weight: {1/n_inst:.2%} each")

    # Correlation matrix
    print_correlation_matrix(corr_matrix)

    # Average intra-class and inter-class correlations
    _print_correlation_analysis(corr_matrix)

    # Portfolio metrics
    metrics = calculate_metrics(results["equity"], results["returns"], capital)
    print(f"\n{'='*70}")
    print_metrics(metrics, title=f"Portfolio Mode {mode}: {mode_label}")

    # Per-instrument contributions
    print_instrument_contributions(results, capital)

    # Yearly returns
    print(f"\n  --- Annual Portfolio Returns ---")
    print(f"  {'Year':<6s} {'PnL':>10s} {'%':>8s} "
          f"{'Equity SOY':>14s} {'Equity EOY':>12s}")
    print(f"  {'-'*54}")

    equity = results["equity"]
    yearly = results["returns"].groupby(results["returns"].index.year).sum()
    win_years = 0
    lose_years = 0
    for year, pnl in yearly.items():
        year_mask = equity.index.year == year
        if not year_mask.any():
            continue
        soy = equity[year_mask].iloc[0]
        eoy = equity[year_mask].iloc[-1]
        pct = pnl / soy * 100
        marker = "+" if pnl > 0 else ""
        print(f"  {year:<6d} {marker}${pnl:>8,.0f} {marker}{pct:>6.1f}% "
              f" ${soy:>11,.0f} ${eoy:>11,.0f}")
        if pnl > 0:
            win_years += 1
        else:
            lose_years += 1

    total = win_years + lose_years
    if total > 0:
        print(f"  {'-'*54}")
        print(f"  Win: {win_years}/{total} ({win_years/total*100:.0f}%) | "
              f"Lose: {lose_years}/{total} ({lose_years/total*100:.0f}%)")

    # Plot equity curve
    if show_plots and analysis_dir:
        plot_equity_drawdown(
            results,
            title=(f"Portfolio Mode {mode}: {mode_label} "
                   f"({n_inst} instruments)\n"
                   f"Sharpe {metrics['sharpe']:.2f} | "
                   f"IDM {idm:.2f} | "
                   f"CAGR {metrics['cagr_pct']:.1f}% | "
                   f"Max DD {metrics['max_dd_pct']:.1f}%"),
            save_path=analysis_dir / f"phase5_equity_mode{mode}.png",
        )

        # Plot correlation heatmap
        _plot_correlation_heatmap(
            corr_matrix,
            title=f"Instrument Correlations - Mode {mode}: {mode_label}",
            save_path=analysis_dir / f"phase5_corr_mode{mode}.png",
        )

    return {
        "mode": mode,
        "metrics": metrics,
        "results": results,
        "idm": idm,
        "corr_matrix": corr_matrix,
        "n_instruments": n_inst,
    }


def _print_correlation_analysis(corr_matrix):
    """Analyze correlations by asset class."""
    classes = {}
    for name in corr_matrix.columns:
        if name in INSTRUMENTS:
            cls = INSTRUMENTS[name]["asset_class"]
            classes.setdefault(cls, []).append(name)

    print(f"\n  Correlation Analysis by Asset Class:")

    # Intra-class
    for cls, members in sorted(classes.items()):
        if len(members) < 2:
            continue
        corrs = []
        for i, a in enumerate(members):
            for b in members[i+1:]:
                if a in corr_matrix.columns and b in corr_matrix.columns:
                    val = corr_matrix.loc[a, b]
                    if not pd.isna(val):
                        corrs.append(val)
        if corrs:
            avg = np.mean(corrs)
            print(f"  Intra-{cls:<10s}: avg corr = {avg:.3f} "
                  f"({len(corrs)} pairs)")

    # Inter-class
    class_names = sorted(classes.keys())
    for i, cls_a in enumerate(class_names):
        for cls_b in class_names[i+1:]:
            corrs = []
            for a in classes[cls_a]:
                for b in classes[cls_b]:
                    if a in corr_matrix.columns and b in corr_matrix.columns:
                        val = corr_matrix.loc[a, b]
                        if not pd.isna(val):
                            corrs.append(val)
            if corrs:
                avg = np.mean(corrs)
                print(f"  {cls_a:<10s} vs {cls_b:<10s}: avg corr = {avg:.3f} "
                      f"({len(corrs)} pairs)")


def _plot_correlation_heatmap(corr_matrix, title="", save_path=None):
    """Plot correlation matrix as heatmap."""
    fig, ax = plt.subplots(figsize=(10, 8))

    im = ax.imshow(corr_matrix.values, cmap="RdBu_r", vmin=-1, vmax=1,
                   aspect="equal")

    names = corr_matrix.columns.tolist()
    ax.set_xticks(range(len(names)))
    ax.set_yticks(range(len(names)))
    ax.set_xticklabels(names, rotation=45, ha="right")
    ax.set_yticklabels(names)

    # Add correlation values as text
    for i in range(len(names)):
        for j in range(len(names)):
            val = corr_matrix.iloc[i, j]
            if not pd.isna(val) and i != j:
                color = "white" if abs(val) > 0.5 else "black"
                ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                        color=color, fontsize=8)

    plt.colorbar(im, ax=ax, label="Correlation")
    ax.set_title(title, fontsize=12)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  Chart saved: {save_path}")

    if metrics_module.SHOW_INTERACTIVE:
        plt.show()
    plt.close()


def print_mode_comparison(result_a, result_b):
    """Print side-by-side comparison of Mode A vs Mode B."""
    ma = result_a["metrics"]
    mb = result_b["metrics"]

    print(f"\n{'='*70}")
    print(f" MODE A vs MODE B COMPARISON")
    print(f"{'='*70}")

    comparisons = [
        ("Sharpe", "sharpe", ".3f"),
        ("Sortino", "sortino", ".3f"),
        ("CAGR %", "cagr_pct", ".2f"),
        ("Annual Vol %", "annual_vol_pct", ".1f"),
        ("Max DD %", "max_dd_pct", ".1f"),
        ("Profit Factor", "profit_factor", ".2f"),
        ("Calmar", "calmar", ".3f"),
    ]

    print(f"  {'Metric':<16s} {'Mode A (EW)':>12s} {'Mode B (EC)':>12s} "
          f"{'Delta':>8s}")
    print(f"  {'-'*52}")

    for label, key, fmt in comparisons:
        va = ma[key]
        vb = mb[key]
        delta = vb - va
        sign = "+" if delta > 0 else ""
        print(f"  {label:<16s} {va:>12{fmt}} {vb:>12{fmt}} "
              f"{sign}{delta:>7{fmt}}")

    print(f"\n  IDM Mode A: {result_a['idm']:.4f}")
    print(f"  IDM Mode B: {result_b['idm']:.4f}")

    carry_better = mb["sharpe"] > ma["sharpe"]
    print(f"\n  Carry improves portfolio Sharpe: "
          f"{'YES' if carry_better else 'NO'} "
          f"({ma['sharpe']:.3f} -> {mb['sharpe']:.3f})")

    if carry_better:
        print(f"  >> DECISION: Keep carry for non-commodity instruments")
    else:
        print(f"  >> DECISION: Discard carry, use EWMAC only for all")


def main():
    show_plots = "--no-plot" not in sys.argv
    save_only = "--save-only" in sys.argv

    if save_only:
        show_plots = True
        metrics_module.SHOW_INTERACTIVE = False

    # Parse mode
    mode = "both"
    for arg in sys.argv[1:]:
        if arg.startswith("--mode"):
            idx = sys.argv.index(arg)
            if idx + 1 < len(sys.argv):
                mode = sys.argv[idx + 1].upper()

    if mode not in ("A", "B", "BOTH"):
        print(f"ERROR: Unknown mode '{mode}'. Use A, B, or both.")
        sys.exit(1)

    vol_target = 0.12
    capital = 100000
    buffer_fraction = 0.10
    analysis_dir = ROOT / "analysis"
    analysis_dir.mkdir(exist_ok=True)

    # Load rates for mode B
    rates_daily = None
    if mode in ("B", "BOTH"):
        print("Loading interest rates for carry...")
        try:
            rates_monthly = load_rates(ROOT / "data")
            daily_idx = pd.date_range("2000-01-01", "2026-12-31", freq="B")
            rates_daily = _rates_to_daily(rates_monthly, daily_idx)
            print(f"Rates loaded: {rates_monthly.shape[0]} months, "
                  f"{len(rates_daily.columns)} currencies")
        except FileNotFoundError:
            print("WARNING: interest_rates.csv not found. "
                  "Mode B will use EWMAC only.")

    result_a = None
    result_b = None

    if mode in ("A", "BOTH"):
        result_a = run_mode(
            "A",
            rates_daily=None,
            show_plots=show_plots,
            save_charts=True,
            analysis_dir=analysis_dir,
            vol_target=vol_target,
            capital=capital,
            buffer_fraction=buffer_fraction,
        )

    if mode in ("B", "BOTH"):
        result_b = run_mode(
            "B",
            rates_daily=rates_daily,
            show_plots=show_plots,
            save_charts=True,
            analysis_dir=analysis_dir,
            vol_target=vol_target,
            capital=capital,
            buffer_fraction=buffer_fraction,
        )

    if result_a and result_b:
        print_mode_comparison(result_a, result_b)

    print(f"\n{'='*70}")
    print(" PHASE 5 COMPLETE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
