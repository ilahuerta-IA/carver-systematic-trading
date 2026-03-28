"""
Phase 3: EWMAC multi-speed (4 speeds combined) on SP500.

Validates:
    1. FDM calculation from empirical forecast correlations
    2. Combined forecast still ~ N(0, 10)
    3. Improvement vs single-speed Phase 2
    4. DD respects vol target +/- 20%

Usage:
    python tools/run_phase3_multispeed.py
    python tools/run_phase3_multispeed.py --save-only
    python tools/run_phase3_multispeed.py --no-plot
    python tools/run_phase3_multispeed.py --all-instruments
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
from core.forecast import (
    ewmac_forecast,
    combine_forecasts,
    EWMAC_SPEEDS,
    EWMAC_FORECAST_SCALARS,
    FORECAST_CAP,
)
from backtest.engine import run_backtest
from backtest.metrics import (
    calculate_metrics,
    print_metrics,
    plot_equity_drawdown,
    plot_position_on_price,
    plot_forecast_distribution,
    generate_adjustment_log,
    print_adjustment_summary,
)
import backtest.metrics as metrics_module


# All instruments available
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


def calculate_fdm(forecasts):
    """
    Calculate Forecast Diversification Multiplier from empirical correlations.

    FDM = 1 / sqrt(w' * C * w)

    where w = equal weights, C = correlation matrix of forecasts.
    This restores the forecast to ~N(0,10) after averaging correlated signals.

    Args:
        forecasts: list of pd.Series (individual forecasts, before capping)

    Returns:
        float: FDM value
    """
    # Align all forecasts and drop NaN rows
    df = pd.concat(forecasts, axis=1).dropna()
    n = len(forecasts)
    weights = np.array([1.0 / n] * n)

    # Correlation matrix
    corr_matrix = df.corr().values

    # FDM = 1 / sqrt(w' C w)
    w_corr_w = weights @ corr_matrix @ weights
    fdm = 1.0 / np.sqrt(w_corr_w)

    return fdm, corr_matrix, df.columns.tolist()


def run_single_instrument(instrument, show_plots=True, save_charts=False,
                          analysis_dir=None, vol_target=0.12, capital=100000,
                          buffer_fraction=0.10, quiet=False):
    """
    Run Phase 3 multi-speed EWMAC on a single instrument.

    Returns dict with metrics and results, or None if data unavailable.
    """
    # Load data
    try:
        df = load_data(instrument)
    except FileNotFoundError:
        if not quiet:
            print(f"  [SKIP] {instrument}: data file not found")
        return None

    close = df["Close"]

    if not quiet:
        print(f"\n{'='*60}")
        print(f" {instrument} - EWMAC Multi-Speed (4 speeds)")
        print(f"{'='*60}")
        print(f"Data: {len(close)} bars, {close.index[0].date()} to {close.index[-1].date()}")

    # Calculate individual forecasts for all 4 speeds
    individual_forecasts = []
    speed_names = []
    for fast, slow in EWMAC_SPEEDS:
        fc = ewmac_forecast(close, fast, slow)
        individual_forecasts.append(fc)
        speed_names.append(f"EWMAC({fast}/{slow})")

    # Calculate FDM from empirical correlations
    fdm, corr_matrix, _ = calculate_fdm(individual_forecasts)

    if not quiet:
        print(f"\nForecast Correlations:")
        print(f"  {'':20s}", end="")
        for name in speed_names:
            print(f" {name:>14s}", end="")
        print()
        for i, name_i in enumerate(speed_names):
            print(f"  {name_i:20s}", end="")
            for j in range(len(speed_names)):
                print(f" {corr_matrix[i, j]:14.3f}", end="")
            print()
        print(f"\n  FDM (empirical): {fdm:.4f}")

    # Combine with equal weights + FDM
    combined = combine_forecasts(individual_forecasts, weights=None, fdm=fdm)

    if not quiet:
        combined_clean = combined.dropna()
        print(f"\nCombined Forecast Distribution:")
        print(f"  Mean:     {combined_clean.mean():.2f}")
        print(f"  Std:      {combined_clean.std():.2f} (target: ~10)")
        print(f"  Abs Mean: {combined_clean.abs().mean():.2f} (target: ~10)")
        print(f"  % at cap: {(combined_clean.abs() >= 19.9).mean() * 100:.1f}%")

        # Individual forecast stats
        print(f"\n  Individual Forecast Stats:")
        print(f"  {'Speed':20s} {'Scalar':>7s} {'Mean':>7s} {'Std':>7s} {'AbsMean':>8s} {'%Cap':>6s}")
        print(f"  {'-'*60}")
        for i, (fast, slow) in enumerate(EWMAC_SPEEDS):
            fc = individual_forecasts[i].dropna()
            scalar = EWMAC_FORECAST_SCALARS.get((fast, slow), 0)
            print(f"  EWMAC({fast}/{slow}){'':<8s} {scalar:>7.2f} "
                  f"{fc.mean():>7.2f} {fc.std():>7.2f} "
                  f"{fc.abs().mean():>8.2f} {(fc.abs() >= 19.9).mean() * 100:>5.1f}%")

    # Run backtest
    if not quiet:
        print(f"\nRunning backtest...")

    results = run_backtest(
        close=close,
        forecast=combined,
        vol_target_annual=vol_target,
        capital=capital,
        point_value=1.0,
        buffer_fraction=buffer_fraction,
    )

    # Calculate metrics
    metrics = calculate_metrics(results["equity"], results["returns"], capital)

    if not quiet:
        print_metrics(metrics, title=f"EWMAC Multi-Speed on {instrument}")
        print(f"  Position changes: {results['trades']}")

        # Yearly breakdown
        print(f"\n  --- Annual Returns ---")
        print(f"  {'Year':<6s} {'PnL':>10s} {'%':>8s} {'Equity SOY':>14s} {'Equity EOY':>12s}")
        print(f"  {'-'*54}")
        equity = results["equity"]
        yearly = results["returns"].groupby(results["returns"].index.year).sum()
        win_years = 0
        lose_years = 0
        current_streak = 0
        worst_streak = 0
        for year, pnl in yearly.items():
            year_mask = equity.index.year == year
            soy = equity[year_mask].iloc[0]
            eoy = equity[year_mask].iloc[-1]
            pct = pnl / soy * 100
            marker = "+" if pnl > 0 else ""
            n_blocks = min(int(abs(pct) / 2), 20)
            bar_char = "\u2588" if pnl > 0 else "\u2593"
            direction = "UP" if pnl > 0 else "DN"
            print(f"  {year:<6d} {marker}${pnl:>8,.0f} {marker}{pct:>6.1f}% "
                  f" ${soy:>11,.0f} ${eoy:>11,.0f}  {direction}{'*' * n_blocks}")
            if pnl > 0:
                win_years += 1
                current_streak = 0
            else:
                lose_years += 1
                current_streak += 1
                worst_streak = max(worst_streak, current_streak)

        total_years = win_years + lose_years
        if total_years > 0:
            print(f"  {'-'*54}")
            print(f"  Winning: {win_years}/{total_years} ({win_years/total_years*100:.0f}%) | "
                  f"Losing: {lose_years}/{total_years} ({lose_years/total_years*100:.0f}%) | "
                  f"Worst streak: {worst_streak}")

    # Adjustment log
    if analysis_dir:
        log_df = generate_adjustment_log(
            results, close,
            save_path=analysis_dir / f"phase3_adjustments_{instrument}.csv",
        )
        if not quiet:
            print_adjustment_summary(log_df)

    # Plots
    if show_plots and analysis_dir:
        title_base = f"EWMAC Multi-Speed {instrument}"
        plot_equity_drawdown(
            results,
            title=f"{title_base} - Equity & Drawdown\n"
                  f"Sharpe {metrics['sharpe']:.2f} | Sortino {metrics['sortino']:.2f} | "
                  f"Max DD {metrics['max_dd_pct']:.1f}% | CAGR {metrics['cagr_pct']:.1f}%",
            save_path=analysis_dir / f"phase3_equity_{instrument}.png",
        )

        plot_position_on_price(
            results, close,
            title=f"{title_base} - Position on Price\n"
                  f"Green=Long | Red=Short | Intensity=Position size",
            save_path=analysis_dir / f"phase3_position_{instrument}.png",
        )

        plot_forecast_distribution(
            combined,
            title=f"EWMAC Multi-Speed Forecast - {instrument}",
            save_path=analysis_dir / f"phase3_forecast_dist_{instrument}.png",
        )

    return {
        "instrument": instrument,
        "metrics": metrics,
        "results": results,
        "fdm": fdm,
        "corr_matrix": corr_matrix,
        "combined_forecast": combined,
    }


def print_comparison_table(results_dict, phase2_metrics=None):
    """Print multi-instrument comparison table."""
    print(f"\n{'='*90}")
    print(f" PHASE 3 SUMMARY - EWMAC Multi-Speed (4 speeds)")
    print(f"{'='*90}")

    header = (f"  {'Instrument':<12s} {'Sharpe':>7s} {'Sortino':>8s} {'CAGR%':>7s} "
              f"{'Vol%':>6s} {'MaxDD%':>7s} {'PF':>5s} {'Calmar':>7s} {'FDM':>5s} {'Trades':>7s}")
    print(header)
    print(f"  {'-'*86}")

    for name, data in results_dict.items():
        m = data["metrics"]
        print(f"  {name:<12s} {m['sharpe']:>7.2f} {m['sortino']:>8.2f} "
              f"{m['cagr_pct']:>7.2f} {m['annual_vol_pct']:>6.1f} "
              f"{m['max_dd_pct']:>7.1f} {m['profit_factor']:>5.2f} "
              f"{m['calmar']:>7.3f} {data['fdm']:>5.2f} "
              f"{data['results']['trades']:>7d}")

    if phase2_metrics:
        print(f"\n  Phase 2 (single-speed 64/256 SP500) for comparison:")
        m = phase2_metrics
        print(f"  {'SP500-P2':<12s} {m['sharpe']:>7.2f} {m['sortino']:>8.2f} "
              f"{m['cagr_pct']:>7.2f} {m['annual_vol_pct']:>6.1f} "
              f"{m['max_dd_pct']:>7.1f} {m['profit_factor']:>5.2f} "
              f"{m['calmar']:>7.3f} {'N/A':>5s} {'N/A':>7s}")


def main():
    show_plots = "--no-plot" not in sys.argv
    save_only = "--save-only" in sys.argv
    all_instruments = "--all-instruments" in sys.argv

    if save_only:
        show_plots = True
        metrics_module.SHOW_INTERACTIVE = False

    # Config (all from literature)
    vol_target = 0.12
    capital = 100000
    buffer_fraction = 0.10

    print("Phase 3: EWMAC Multi-Speed (4 speeds combined)")
    print(f"Speeds: {EWMAC_SPEEDS}")
    print(f"Weights: equal (0.25 each), FDM: empirical from correlations")
    print(f"Vol target: {vol_target*100}%, Capital: ${capital:,}, Buffer: {buffer_fraction*100}%")

    analysis_dir = ROOT / "analysis"
    analysis_dir.mkdir(exist_ok=True)

    instruments = ALL_INSTRUMENTS if all_instruments else ["SP500"]
    all_results = {}

    for instrument in instruments:
        result = run_single_instrument(
            instrument,
            show_plots=show_plots,
            save_charts=True,
            analysis_dir=analysis_dir,
            vol_target=vol_target,
            capital=capital,
            buffer_fraction=buffer_fraction,
        )
        if result:
            all_results[instrument] = result

    # Run Phase 2 single-speed for comparison (SP500 only)
    phase2_metrics = None
    if "SP500" in all_results:
        print(f"\n{'='*60}")
        print(f" Phase 2 vs Phase 3 Comparison (SP500)")
        print(f"{'='*60}")

        # Quick Phase 2 re-run for comparison
        df = load_data("SP500")
        close = df["Close"]
        fc_single = ewmac_forecast(close, 64, 256)
        results_p2 = run_backtest(
            close=close, forecast=fc_single,
            vol_target_annual=vol_target, capital=capital,
            buffer_fraction=buffer_fraction,
        )
        phase2_metrics = calculate_metrics(
            results_p2["equity"], results_p2["returns"], capital
        )

        p3 = all_results["SP500"]["metrics"]
        p2 = phase2_metrics

        print(f"\n  {'Metric':<22s} {'Phase 2 (64/256)':>16s} {'Phase 3 (multi)':>16s} {'Delta':>8s}")
        print(f"  {'-'*64}")
        comparisons = [
            ("Sharpe", "sharpe", ".2f"),
            ("Sortino", "sortino", ".2f"),
            ("CAGR %", "cagr_pct", ".2f"),
            ("Annual Vol %", "annual_vol_pct", ".1f"),
            ("Max DD %", "max_dd_pct", ".1f"),
            ("Profit Factor", "profit_factor", ".2f"),
            ("Calmar", "calmar", ".3f"),
            ("Win Rate %", "win_rate_pct", ".1f"),
        ]
        for label, key, fmt in comparisons:
            v2 = p2[key]
            v3 = p3[key]
            delta = v3 - v2
            sign = "+" if delta > 0 else ""
            print(f"  {label:<22s} {v2:>16{fmt}} {v3:>16{fmt}} {sign}{delta:>7{fmt}}")

        print(f"\n  FDM used: {all_results['SP500']['fdm']:.4f}")

    # Multi-instrument summary
    if len(all_results) > 1:
        print_comparison_table(all_results, phase2_metrics)


if __name__ == "__main__":
    main()
