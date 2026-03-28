"""
Phase 2: Run EWMAC single-speed (64/256) on SP500.

Validates:
    1. Forecast distribution ~ N(0, 10)
    2. Basic backtest metrics (Sharpe, DD, PF)
    3. Position sizing with vol targeting at 12%

Usage:
    python tools/run_phase2_ewmac.py
    python tools/run_phase2_ewmac.py --no-plot
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if "--save-only" in sys.argv:
    import matplotlib
    matplotlib.use("Agg")

import pandas as pd
from core.forecast import ewmac_forecast, EWMAC_FORECAST_SCALARS
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


def load_data(name):
    """Load daily CSV from data/ folder."""
    path = ROOT / "data" / f"{name}_daily.csv"
    df = pd.read_csv(path, index_col="Date", parse_dates=True)
    return df


def main():
    show_plots = "--no-plot" not in sys.argv
    save_only = "--save-only" in sys.argv
    if save_only:
        show_plots = True  # generate plots but don't display
        metrics_module.SHOW_INTERACTIVE = False

    # Configuration (all from Carver literature, NOTHING optimized)
    instrument = "SP500"
    fast_span = 64
    slow_span = 256
    vol_target = 0.12  # 12% annual
    capital = 100000
    buffer_fraction = 0.10

    scalar = EWMAC_FORECAST_SCALARS.get((fast_span, slow_span), 5.3)
    print(f"Phase 2: EWMAC({fast_span}/{slow_span}) on {instrument}")
    print(f"Forecast scalar: {scalar}")
    print(f"Vol target: {vol_target * 100}%, Capital: ${capital:,}")
    print(f"Buffer: {buffer_fraction * 100}%")
    print("=" * 50)

    # Load data
    df = load_data(instrument)
    close = df["Close"]
    print(f"Data: {len(close)} bars, {close.index[0].date()} to {close.index[-1].date()}")

    # Calculate forecast
    forecast = ewmac_forecast(close, fast_span, slow_span)
    forecast_clean = forecast.dropna()

    # Forecast distribution stats
    print(f"\nForecast Distribution:")
    print(f"  Mean:     {forecast_clean.mean():.2f} (target: ~0)")
    print(f"  Std:      {forecast_clean.std():.2f} (target: ~10)")
    print(f"  Abs Mean: {forecast_clean.abs().mean():.2f} (target: ~10)")
    print(f"  % at cap: {(forecast_clean.abs() >= 19.9).mean() * 100:.1f}%")
    print(f"  Min/Max:  {forecast_clean.min():.1f} / {forecast_clean.max():.1f}")

    # Run backtest
    print(f"\nRunning backtest...")
    results = run_backtest(
        close=close,
        forecast=forecast,
        vol_target_annual=vol_target,
        capital=capital,
        point_value=1.0,
        buffer_fraction=buffer_fraction,
    )

    # Calculate and print metrics
    metrics = calculate_metrics(results["equity"], results["returns"], capital)
    print_metrics(metrics, title=f"EWMAC({fast_span}/{slow_span}) on {instrument}")
    print(f"  Position changes: {results['trades']}")

    # Yearly breakdown
    print(f"\n  --- Retorno Anual ---")
    print(f"  {'Año':<6s} {'PnL':>10s} {'%':>8s} {'Equity inicio':>14s} {'Equity fin':>12s}")
    print(f"  {'-'*54}")
    equity = results["equity"]
    yearly = results["returns"].groupby(results["returns"].index.year).sum()
    win_years = 0
    lose_years = 0
    current_streak = 0
    worst_streak = 0
    for year, pnl in yearly.items():
        year_mask = equity.index.year == year
        soy_equity = equity[year_mask].iloc[0]
        eoy_equity = equity[year_mask].iloc[-1]
        pct = pnl / soy_equity * 100
        marker = "+" if pnl > 0 else ""
        bar = "█" * min(int(abs(pct) / 2), 20)
        color_bar = f"{'↑' if pnl > 0 else '↓'}{bar}"
        print(f"  {year:<6d} {marker}${pnl:>8,.0f} {marker}{pct:>6.1f}%  ${soy_equity:>11,.0f} ${eoy_equity:>11,.0f}  {color_bar}")
        if pnl > 0:
            win_years += 1
            current_streak = 0
        else:
            lose_years += 1
            current_streak += 1
            worst_streak = max(worst_streak, current_streak)

    total_years = win_years + lose_years
    print(f"  {'-'*54}")
    print(f"  Años ganadores: {win_years}/{total_years} ({win_years/total_years*100:.0f}%)")
    print(f"  Años perdedores: {lose_years}/{total_years} ({lose_years/total_years*100:.0f}%)")
    print(f"  Peor racha perdedora: {worst_streak} años consecutivos")

    # Adjustment log
    analysis_dir = ROOT / "analysis"
    log_df = generate_adjustment_log(
        results, close,
        save_path=analysis_dir / f"phase2_adjustments_{instrument}.csv",
    )
    print_adjustment_summary(log_df)

    # Plots
    if show_plots:
        plot_equity_drawdown(
            results,
            title=f"EWMAC({fast_span}/{slow_span}) {instrument} — Equity & Drawdown\n"
                  f"Sharpe {metrics['sharpe']:.2f} | Sortino {metrics['sortino']:.2f} | "
                  f"Max DD {metrics['max_dd_pct']:.1f}% | CAGR {metrics['cagr_pct']:.1f}%",
            save_path=analysis_dir / f"phase2_equity_{instrument}.png",
        )

        plot_position_on_price(
            results, close,
            title=f"EWMAC({fast_span}/{slow_span}) {instrument} — Posición sobre Precio\n"
                  f"Verde=Long | Rojo=Short | Intensidad=Tamaño posición",
            save_path=analysis_dir / f"phase2_position_{instrument}.png",
        )

        plot_forecast_distribution(
            forecast,
            title=f"EWMAC({fast_span}/{slow_span}) Forecast - {instrument}",
            save_path=analysis_dir / f"phase2_forecast_dist_{instrument}.png",
        )


if __name__ == "__main__":
    main()
