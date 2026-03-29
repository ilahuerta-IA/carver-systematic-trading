"""
Phase 4: EWMAC + Carry combined signal.

Validates:
    1. Carry forecast distribution and scaling
    2. Correlation between EWMAC and Carry (expect ~0.2)
    3. Combined Sharpe > EWMAC-only Sharpe (Phase 3)
    4. FDM for trend-carry combination

Usage:
    python tools/run_phase4_carry.py
    python tools/run_phase4_carry.py --save-only
    python tools/run_phase4_carry.py --no-plot
    python tools/run_phase4_carry.py --all-instruments
    python tools/run_phase4_carry.py SP500 GOLD EURUSD
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
from core.carry import (
    load_rates,
    carry_forecast,
    carry_annualized,
    calibrate_carry_scalar,
    _rates_to_daily,
    _annualized_vol,
    CARRY_SCALAR,
)
from config.instruments import INSTRUMENTS
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


# All instruments
ALL_INSTRUMENTS = [
    "SP500", "NASDAQ100", "DAX40", "NIKKEI225",
    "GOLD", "SILVER",
    "EURUSD", "USDJPY", "AUDUSD", "GBPUSD",
]

# Combination weights (Carver: 60% trend, 40% carry — "surfer + farmer")
WEIGHT_TREND = 0.60
WEIGHT_CARRY = 0.40


def load_data(name):
    """Load daily CSV from data/ folder."""
    path = ROOT / "data" / f"{name}_daily.csv"
    df = pd.read_csv(path, index_col="Date", parse_dates=True)
    return df


def calculate_ewmac_combined(close):
    """
    Calculate combined EWMAC forecast (4 speeds) with empirical FDM.
    Same as Phase 3.

    Returns:
        tuple: (combined_forecast, fdm, individual_forecasts)
    """
    individual = []
    for fast, slow in EWMAC_SPEEDS:
        fc = ewmac_forecast(close, fast, slow)
        individual.append(fc)

    # FDM from correlations between speeds
    df_fc = pd.concat(individual, axis=1).dropna()
    n = len(individual)
    weights = np.array([1.0 / n] * n)
    corr = df_fc.corr().values
    w_corr_w = weights @ corr @ weights
    fdm = 1.0 / np.sqrt(w_corr_w)

    combined = combine_forecasts(individual, weights=None, fdm=fdm)
    return combined, fdm, individual


def calculate_trend_carry_fdm(trend_forecast, carry_fc):
    """
    Calculate FDM for the trend-carry combination.

    FDM = 1 / sqrt(wt^2 + wc^2 + 2*wt*wc*corr(trend, carry))

    Args:
        trend_forecast: pd.Series (combined EWMAC)
        carry_fc: pd.Series (carry forecast)

    Returns:
        tuple: (fdm, correlation)
    """
    df = pd.concat([trend_forecast, carry_fc], axis=1).dropna()
    if len(df) < 100:
        return 1.0, 0.0

    corr = df.iloc[:, 0].corr(df.iloc[:, 1])

    wt = WEIGHT_TREND
    wc = WEIGHT_CARRY
    w_corr_w = wt**2 + wc**2 + 2 * wt * wc * corr
    fdm = 1.0 / np.sqrt(w_corr_w)

    return fdm, corr


def run_single_instrument(instrument, rates_daily, show_plots=True,
                          save_charts=False, analysis_dir=None,
                          vol_target=0.12, capital=100000,
                          buffer_fraction=0.10, quiet=False):
    """
    Run Phase 4 (EWMAC + Carry) on a single instrument.

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

    cfg = INSTRUMENTS[instrument]
    use_carry = cfg["asset_class"] != "commodity"

    if not quiet:
        print(f"\n{'='*70}")
        if use_carry:
            print(f" {instrument} - EWMAC + Carry (Phase 4)")
        else:
            print(f" {instrument} - EWMAC only (commodity: carry excluded)")
        print(f"{'='*70}")
        print(f"Data: {len(close)} bars, "
              f"{close.index[0].date()} to {close.index[-1].date()}")

    # === EWMAC COMBINED (same as Phase 3) ===
    ewmac_combined, ewmac_fdm, _ = calculate_ewmac_combined(close)

    # === CARRY FORECAST (skip for commodities) ===
    carry_fc = None
    carry_scalar_used = None
    tc_fdm = 1.0
    tc_corr = 0.0

    if use_carry:
        carry_scalar_used = calibrate_carry_scalar(
            instrument, close, rates_daily
        )
        carry_fc = carry_forecast(
            instrument, close, rates_daily,
            carry_scalar=carry_scalar_used,
        )

        if not quiet:
            carry_clean = carry_fc.dropna()
            print(f"\nCarry Forecast ({instrument}):")
            print(f"  Scalar:   {carry_scalar_used} "
                  f"(auto-calibrated, was {CARRY_SCALAR})")
            print(f"  Mean:     {carry_clean.mean():.2f}")
            print(f"  Std:      {carry_clean.std():.2f}")
            print(f"  Abs Mean: {carry_clean.abs().mean():.2f} (target: ~10)")
            print(f"  Min/Max:  {carry_clean.min():.2f} / "
                  f"{carry_clean.max():.2f}")
            pct_cap = (carry_clean.abs() >= 19.9).mean() * 100
            print(f"  % at cap: {pct_cap:.1f}%")

            cfg_inst = INSTRUMENTS[instrument]
            if cfg_inst["asset_class"] == "fx":
                carry_ann = carry_annualized(instrument, rates_daily)
                carry_ann = carry_ann.reindex(
                    close.index, method="ffill"
                ).dropna()
                print(f"  Avg carry (ann): {carry_ann.mean()*100:.2f}% "
                      f"({cfg_inst['base_currency']}-"
                      f"{cfg_inst['quote_currency']})")
                print(f"  Carry > 0:  "
                      f"{(carry_ann > 0).mean()*100:.0f}% of days")
            elif cfg_inst["asset_class"] == "equity":
                print(f"  Div yield approx: "
                      f"{cfg_inst['div_yield_approx']*100:.1f}%")

        # === TREND-CARRY FDM ===
        tc_fdm, tc_corr = calculate_trend_carry_fdm(
            ewmac_combined, carry_fc
        )

        if not quiet:
            print(f"\nTrend-Carry Combination:")
            print(f"  Weights: {WEIGHT_TREND:.0%} trend + "
                  f"{WEIGHT_CARRY:.0%} carry")
            print(f"  Correlation(EWMAC, Carry): {tc_corr:.3f}")
            print(f"  FDM (trend-carry): {tc_fdm:.4f}")
            print(f"  EWMAC FDM (speeds): {ewmac_fdm:.4f}")

        # === COMBINE TREND + CARRY ===
        final_forecast = combine_forecasts(
            [ewmac_combined, carry_fc],
            weights=[WEIGHT_TREND, WEIGHT_CARRY],
            fdm=tc_fdm,
        )
    else:
        # Commodity: use EWMAC only (no carry available)
        final_forecast = ewmac_combined
        if not quiet:
            print(f"\n  Carry EXCLUDED (commodity without term structure)")
            print(f"  Using 100% EWMAC combined (same as Phase 3)")

    if not quiet and use_carry:
        final_clean = final_forecast.dropna()
        ewmac_clean = ewmac_combined.dropna()
        print(f"\nFinal Combined Forecast:")
        print(f"  Mean:     {final_clean.mean():.2f} "
              f"(EWMAC only: {ewmac_clean.mean():.2f})")
        print(f"  Std:      {final_clean.std():.2f} "
              f"(EWMAC only: {ewmac_clean.std():.2f})")
        print(f"  Abs Mean: {final_clean.abs().mean():.2f} "
              f"(EWMAC only: {ewmac_clean.abs().mean():.2f})")

    # === RUN BACKTEST ===
    if not quiet:
        print(f"\nRunning backtest (EWMAC + Carry)...")

    results_combined = run_backtest(
        close=close,
        forecast=final_forecast,
        vol_target_annual=vol_target,
        capital=capital,
        point_value=1.0,
        buffer_fraction=buffer_fraction,
    )

    # Also run EWMAC-only for comparison
    results_ewmac = run_backtest(
        close=close,
        forecast=ewmac_combined,
        vol_target_annual=vol_target,
        capital=capital,
        point_value=1.0,
        buffer_fraction=buffer_fraction,
    )

    metrics_combined = calculate_metrics(
        results_combined["equity"], results_combined["returns"], capital
    )
    metrics_ewmac = calculate_metrics(
        results_ewmac["equity"], results_ewmac["returns"], capital
    )

    if not quiet:
        print_metrics(metrics_combined,
                      title=f"EWMAC + Carry on {instrument}")

        # Comparison
        print(f"\n  --- Phase 3 vs Phase 4 Comparison ---")
        print(f"  {'Metric':<16s} {'EWMAC only':>12s} {'EWMAC+Carry':>12s} "
              f"{'Delta':>8s}")
        print(f"  {'-'*52}")
        comparisons = [
            ("Sharpe", "sharpe", ".2f"),
            ("Sortino", "sortino", ".2f"),
            ("CAGR %", "cagr_pct", ".2f"),
            ("Vol %", "annual_vol_pct", ".1f"),
            ("Max DD %", "max_dd_pct", ".1f"),
            ("Profit Factor", "profit_factor", ".2f"),
            ("Calmar", "calmar", ".3f"),
        ]
        for label, key, fmt in comparisons:
            v_ew = metrics_ewmac[key]
            v_co = metrics_combined[key]
            delta = v_co - v_ew
            sign = "+" if delta > 0 else ""
            print(f"  {label:<16s} {v_ew:>12{fmt}} {v_co:>12{fmt}} "
                  f"{sign}{delta:>7{fmt}}")

        sharpe_improved = metrics_combined["sharpe"] > metrics_ewmac["sharpe"]
        print(f"\n  Sharpe improved: {'YES' if sharpe_improved else 'NO'} "
              f"({metrics_ewmac['sharpe']:.3f} -> "
              f"{metrics_combined['sharpe']:.3f})")

        # Yearly breakdown
        print(f"\n  --- Annual Returns (EWMAC+Carry) ---")
        print(f"  {'Year':<6s} {'PnL':>10s} {'%':>8s} "
              f"{'Equity SOY':>14s} {'Equity EOY':>12s}")
        print(f"  {'-'*54}")
        equity = results_combined["equity"]
        yearly = results_combined["returns"].groupby(
            results_combined["returns"].index.year
        ).sum()
        win_years = 0
        lose_years = 0
        for year, pnl in yearly.items():
            year_mask = equity.index.year == year
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

    # Adjustment log
    if analysis_dir:
        log_df = generate_adjustment_log(
            results_combined, close,
            save_path=analysis_dir / f"phase4_adjustments_{instrument}.csv",
        )
        if not quiet:
            print_adjustment_summary(log_df)

    # Plots
    if show_plots and analysis_dir:
        title_base = f"EWMAC+Carry {instrument}"
        plot_equity_drawdown(
            results_combined,
            title=(f"{title_base} -- Equity & Drawdown\n"
                   f"Sharpe {metrics_combined['sharpe']:.2f} | "
                   f"Sortino {metrics_combined['sortino']:.2f} | "
                   f"Max DD {metrics_combined['max_dd_pct']:.1f}% | "
                   f"CAGR {metrics_combined['cagr_pct']:.1f}%"),
            save_path=analysis_dir / f"phase4_equity_{instrument}.png",
        )

        plot_position_on_price(
            results_combined, close,
            title=(f"{title_base} -- Position on Price\n"
                   f"Green=Long | Red=Short | Intensity=Position size"),
            save_path=analysis_dir / f"phase4_position_{instrument}.png",
        )

        plot_forecast_distribution(
            final_forecast,
            title=f"EWMAC+Carry Forecast - {instrument}",
            save_path=analysis_dir / f"phase4_forecast_dist_{instrument}.png",
        )

    return {
        "instrument": instrument,
        "metrics_combined": metrics_combined,
        "metrics_ewmac": metrics_ewmac,
        "results": results_combined,
        "carry_forecast": carry_fc,
        "ewmac_forecast": ewmac_combined,
        "final_forecast": final_forecast,
        "ewmac_fdm": ewmac_fdm,
        "tc_fdm": tc_fdm,
        "tc_corr": tc_corr,
        "use_carry": use_carry,
        "carry_scalar_used": carry_scalar_used,
    }


def print_comparison_table(results_dict):
    """Print multi-instrument comparison: EWMAC only vs EWMAC+Carry."""
    print(f"\n{'='*115}")
    print(f" PHASE 4 SUMMARY -- EWMAC + Carry ({WEIGHT_TREND:.0%} / "
          f"{WEIGHT_CARRY:.0%}) | Commodities = EWMAC only")
    print(f"{'='*115}")

    # Header
    header = (f"  {'Instrument':<12s} "
              f"{'Sharpe_EW':>10s} {'Sharpe_EC':>10s} {'Delta':>7s} "
              f"{'CAGR%_EC':>9s} {'Vol%':>6s} {'MaxDD%':>7s} "
              f"{'PF_EC':>6s} {'Corr_TC':>8s} {'FDM_TC':>7s} "
              f"{'Scalar':>7s} {'Mode':>10s}")
    print(header)
    print(f"  {'-'*115}")

    improved = 0
    total_carry = 0
    for name, data in results_dict.items():
        me = data["metrics_ewmac"]
        mc = data["metrics_combined"]
        delta = mc["sharpe"] - me["sharpe"]
        sign = "+" if delta > 0 else ""
        use_carry = data["use_carry"]

        if use_carry:
            total_carry += 1
            if delta > 0:
                improved += 1
            scalar_str = f"{data['carry_scalar_used']:.1f}"
            mode_str = "EWMAC+Carry"
        else:
            scalar_str = "N/A"
            mode_str = "EWMAC only"

        print(f"  {name:<12s} "
              f"{me['sharpe']:>10.3f} {mc['sharpe']:>10.3f} "
              f"{sign}{delta:>6.3f} "
              f"{mc['cagr_pct']:>9.2f} {mc['annual_vol_pct']:>6.1f} "
              f"{mc['max_dd_pct']:>7.1f} {mc['profit_factor']:>6.2f} "
              f"{data['tc_corr']:>8.3f} {data['tc_fdm']:>7.4f} "
              f"{scalar_str:>7s} {mode_str:>10s}")

    total_all = len(results_dict)
    print(f"\n  Sharpe improved in {improved}/{total_carry} "
          f"carry instruments (+ {total_all - total_carry} commodity "
          f"= EWMAC only)")

    # Carry scalar diagnostic (only for carry instruments)
    carry_items = {k: v for k, v in results_dict.items() if v["use_carry"]}
    if carry_items:
        print(f"\n  Carry Forecast Scaling Diagnostic (auto-calibrated):")
        print(f"  {'Instrument':<12s} {'Scalar':>8s} {'AbsMean':>8s} "
              f"{'Std':>8s} {'%Cap':>6s} {'Status':>10s}")
        print(f"  {'-'*56}")
        for name, data in carry_items.items():
            carry_clean = data["carry_forecast"].dropna()
            abs_mean = carry_clean.abs().mean()
            std = carry_clean.std()
            pct_cap = (carry_clean.abs() >= 19.9).mean() * 100
            status = "OK" if 5 < abs_mean < 15 else "CHECK"
            scalar = data["carry_scalar_used"]
            print(f"  {name:<12s} {scalar:>8.1f} {abs_mean:>8.2f} "
                  f"{std:>8.2f} {pct_cap:>5.1f}% {status:>10s}")


def main():
    show_plots = "--no-plot" not in sys.argv
    save_only = "--save-only" in sys.argv
    all_instruments = "--all-instruments" in sys.argv

    if save_only:
        show_plots = True
        metrics_module.SHOW_INTERACTIVE = False

    # Parse instrument arguments
    named_args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if all_instruments:
        instruments = ALL_INSTRUMENTS
    elif named_args:
        instruments = [i.upper() for i in named_args]
    else:
        instruments = ALL_INSTRUMENTS

    # Config
    vol_target = 0.12
    capital = 100000
    buffer_fraction = 0.10
    analysis_dir = ROOT / "analysis"
    analysis_dir.mkdir(exist_ok=True)

    # Load interest rates
    print("Loading interest rates...")
    try:
        rates_monthly = load_rates(ROOT / "data")
    except FileNotFoundError:
        print("ERROR: interest_rates.csv not found. "
              "Run 'python tools/download_rates.py' first.")
        sys.exit(1)

    # Expand to daily (will be aligned per instrument later)
    # Use a broad daily range
    daily_idx = pd.date_range("2000-01-01", "2026-12-31", freq="B")
    rates_daily = _rates_to_daily(rates_monthly, daily_idx)
    print(f"Rates loaded: {rates_monthly.shape[0]} months, "
          f"{len(rates_daily.columns)} currencies")

    # Run all instruments
    all_results = {}
    for instrument in instruments:
        result = run_single_instrument(
            instrument,
            rates_daily=rates_daily,
            show_plots=show_plots,
            save_charts=True,
            analysis_dir=analysis_dir,
            vol_target=vol_target,
            capital=capital,
            buffer_fraction=buffer_fraction,
        )
        if result is not None:
            all_results[instrument] = result

    # Summary table
    if len(all_results) > 1:
        print_comparison_table(all_results)

    print(f"\n{'='*70}")
    print(" PHASE 4 COMPLETE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
