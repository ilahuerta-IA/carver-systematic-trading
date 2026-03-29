"""
Phase 6b deep-dive: detailed annual and per-instrument analysis
for the 3 survivors (NI225, USDJPY, DAX40).

Outputs:
    - Portfolio-level full metrics
    - Year-by-year PnL, Sharpe, drawdown table
    - Per-instrument annual breakdown
    - Rolling 3-year Sharpe
    - Monthly return heatmap
    - Worst drawdown episodes

Usage:
    python tools/run_phase6b_detail.py
    python tools/run_phase6b_detail.py --save-only
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
from core.costs import build_reference_rates
from config.instruments import INSTRUMENTS, INSTRUMENT_COSTS
from backtest.metrics import (
    calculate_metrics,
    print_metrics,
    SHOW_INTERACTIVE,
)
import backtest.metrics as metrics_module


SURVIVORS = ["NIKKEI225", "USDJPY", "DAX40"]


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


def prepare_instruments():
    instrument_data = []
    for name in SURVIVORS:
        df = load_data(name)
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


def build_costs_dict():
    costs = {}
    for name in SURVIVORS:
        if name in INSTRUMENT_COSTS:
            costs[name] = dict(INSTRUMENT_COSTS[name])
    return costs


def yearly_metrics(equity, returns, capital):
    """Calculate metrics per calendar year."""
    years = sorted(returns.index.year.unique())
    rows = []
    for yr in years:
        mask = returns.index.year == yr
        yr_ret = returns[mask]
        yr_eq = equity[mask]
        if len(yr_ret) < 20:
            continue

        yr_pnl = yr_ret.sum()
        eq_start = yr_eq.iloc[0]

        # Pct returns relative to equity
        pct_ret = yr_ret / equity.shift(1).reindex(yr_ret.index)
        pct_ret = pct_ret.dropna()

        daily_mean = pct_ret.mean()
        daily_std = pct_ret.std()
        sharpe = daily_mean / daily_std * np.sqrt(256) if daily_std > 0 else 0

        downside = pct_ret[pct_ret < 0]
        ds_std = downside.std() if len(downside) > 0 else 0
        sortino = daily_mean / ds_std * np.sqrt(256) if ds_std > 0 else 0

        ann_ret_pct = yr_pnl / eq_start * 100

        peak = yr_eq.expanding().max()
        dd = (yr_eq - peak) / peak
        max_dd_pct = dd.min() * 100

        gains = yr_ret[yr_ret > 0].sum()
        losses = abs(yr_ret[yr_ret < 0].sum())
        pf = gains / losses if losses > 0 else float("inf")

        win_days = (yr_ret > 0).sum()
        total_active = (yr_ret != 0).sum()
        win_rate = win_days / total_active * 100 if total_active > 0 else 0

        rows.append({
            "Year": yr,
            "PnL ($)": yr_pnl,
            "Return %": ann_ret_pct,
            "Sharpe": sharpe,
            "Sortino": sortino,
            "Max DD %": max_dd_pct,
            "PF": pf,
            "Win %": win_rate,
            "Days": len(yr_ret),
        })

    return pd.DataFrame(rows)


def instrument_yearly_pnl(inst_returns):
    """Per-instrument PnL per year."""
    all_years = set()
    for name, ret in inst_returns.items():
        all_years.update(ret.index.year.unique())
    years = sorted(all_years)

    rows = []
    for yr in years:
        row = {"Year": yr}
        total = 0
        for name in SURVIVORS:
            if name in inst_returns:
                ret = inst_returns[name]
                mask = ret.index.year == yr
                pnl = ret[mask].sum()
                row[name] = pnl
                total += pnl
            else:
                row[name] = 0
        row["TOTAL"] = total
        rows.append(row)
    return pd.DataFrame(rows)


def top_drawdowns(equity, n=5):
    """Find the N worst drawdown episodes."""
    peak = equity.expanding().max()
    dd = (equity - peak) / peak

    episodes = []
    in_dd = False
    start = None
    trough_date = None
    trough_val = 0

    for i, (date, val) in enumerate(dd.items()):
        if val < 0:
            if not in_dd:
                start = date
                trough_date = date
                trough_val = val
                in_dd = True
            elif val < trough_val:
                trough_date = date
                trough_val = val
        else:
            if in_dd:
                episodes.append({
                    "Start": start,
                    "Trough": trough_date,
                    "Recovery": date,
                    "Depth %": trough_val * 100,
                    "Duration (days)": (date - start).days,
                    "To Trough (days)": (trough_date - start).days,
                })
                in_dd = False

    # If still in drawdown at end
    if in_dd:
        episodes.append({
            "Start": start,
            "Trough": trough_date,
            "Recovery": "Ongoing",
            "Depth %": trough_val * 100,
            "Duration (days)": (equity.index[-1] - start).days,
            "To Trough (days)": (trough_date - start).days,
        })

    episodes.sort(key=lambda x: x["Depth %"])
    return episodes[:n]


def print_yearly_table(df_yearly):
    print(f"\n{'='*90}")
    print(f" YEAR-BY-YEAR PERFORMANCE (3 Survivors, Net)")
    print(f"{'='*90}")
    print(f"  {'Year':>4s}  {'PnL ($)':>10s}  {'Return%':>8s}  {'Sharpe':>7s}"
          f"  {'Sortino':>8s}  {'MaxDD%':>7s}  {'PF':>5s}  {'Win%':>5s}")
    print(f"  {'-'*70}")

    for _, row in df_yearly.iterrows():
        pnl = row["PnL ($)"]
        sign = "+" if pnl >= 0 else ""
        print(f"  {int(row['Year']):>4d}  {sign}${abs(pnl):>9,.0f}  "
              f"{row['Return %']:>7.1f}%  {row['Sharpe']:>7.2f}  "
              f"{row['Sortino']:>8.2f}  {row['Max DD %']:>6.1f}%  "
              f"{row['PF']:>5.2f}  {row['Win %']:>4.0f}%")

    # Summary row
    total_pnl = df_yearly["PnL ($)"].sum()
    avg_sharpe = df_yearly["Sharpe"].mean()
    avg_sortino = df_yearly["Sortino"].mean()
    pct_positive_years = (df_yearly["PnL ($)"] > 0).mean() * 100
    print(f"  {'-'*70}")
    sign = "+" if total_pnl >= 0 else ""
    print(f"  {'TOT':>4s}  {sign}${abs(total_pnl):>9,.0f}  "
          f"{'':>8s}  {avg_sharpe:>7.2f}  "
          f"{avg_sortino:>8.2f}  {'':>7s}  "
          f"{'':>5s}  {'':>5s}")
    print(f"\n  Positive years: {pct_positive_years:.0f}% "
          f"({(df_yearly['PnL ($)'] > 0).sum()}/{len(df_yearly)})")
    print(f"  Best year:  {df_yearly.loc[df_yearly['PnL ($)'].idxmax(), 'Year']:.0f}"
          f" (${df_yearly['PnL ($)'].max():,.0f})")
    print(f"  Worst year: {df_yearly.loc[df_yearly['PnL ($)'].idxmin(), 'Year']:.0f}"
          f" (${df_yearly['PnL ($)'].min():,.0f})")


def print_instrument_yearly(df_inst):
    print(f"\n{'='*70}")
    print(f" PER-INSTRUMENT ANNUAL PnL ($)")
    print(f"{'='*70}")
    header = f"  {'Year':>4s}"
    for name in SURVIVORS:
        header += f"  {name:>12s}"
    header += f"  {'TOTAL':>12s}"
    print(header)
    print(f"  {'-'*(6 + 14 * (len(SURVIVORS) + 1))}")

    for _, row in df_inst.iterrows():
        yr = int(row["Year"])
        line = f"  {yr:>4d}"
        for name in SURVIVORS:
            pnl = row.get(name, 0)
            sign = "+" if pnl >= 0 else "-"
            line += f"  {sign}${abs(pnl):>10,.0f}"
        total = row["TOTAL"]
        sign = "+" if total >= 0 else "-"
        line += f"  {sign}${abs(total):>10,.0f}"
        print(line)

    # Totals
    line = f"  {'TOT':>4s}"
    for name in SURVIVORS:
        total = df_inst[name].sum()
        sign = "+" if total >= 0 else "-"
        line += f"  {sign}${abs(total):>10,.0f}"
    grand = df_inst["TOTAL"].sum()
    sign = "+" if grand >= 0 else "-"
    line += f"  {sign}${abs(grand):>10,.0f}"
    print(f"  {'-'*(6 + 14 * (len(SURVIVORS) + 1))}")
    print(line)


def print_drawdown_episodes(episodes):
    print(f"\n{'='*80}")
    print(f" TOP 5 WORST DRAWDOWN EPISODES")
    print(f"{'='*80}")
    print(f"  {'#':>2s}  {'Start':>12s}  {'Trough':>12s}  {'Recovery':>12s}  "
          f"{'Depth':>7s}  {'Duration':>9s}  {'ToTrough':>9s}")
    print(f"  {'-'*72}")

    for i, ep in enumerate(episodes, 1):
        start = ep["Start"].strftime("%Y-%m-%d") if hasattr(ep["Start"], "strftime") else str(ep["Start"])
        trough = ep["Trough"].strftime("%Y-%m-%d") if hasattr(ep["Trough"], "strftime") else str(ep["Trough"])
        recovery = ep["Recovery"].strftime("%Y-%m-%d") if hasattr(ep["Recovery"], "strftime") else str(ep["Recovery"])
        print(f"  {i:>2d}  {start:>12s}  {trough:>12s}  {recovery:>12s}  "
              f"{ep['Depth %']:>6.1f}%  {ep['Duration (days)']:>7d} d  "
              f"{ep['To Trough (days)']:>7d} d")


def print_monthly_stats(returns, equity):
    """Monthly return statistics and heatmap data."""
    monthly_pnl = returns.resample("ME").sum()
    monthly_eq_start = equity.resample("MS").first()
    monthly_pct = pd.Series(index=monthly_pnl.index, dtype=float)
    for date in monthly_pnl.index:
        ms = date.replace(day=1)
        if ms in monthly_eq_start.index:
            monthly_pct[date] = monthly_pnl[date] / monthly_eq_start[ms] * 100

    monthly_pct = monthly_pct.dropna()

    print(f"\n{'='*80}")
    print(f" MONTHLY RETURN DISTRIBUTION (%)")
    print(f"{'='*80}")

    # Year x Month heatmap (text)
    years = sorted(monthly_pct.index.year.unique())
    months_label = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    header = f"  {'Year':>4s}"
    for m in months_label:
        header += f" {m:>6s}"
    header += f" {'TOTAL':>7s}"
    print(header)
    print(f"  {'-'*(6 + 7*12 + 8)}")

    for yr in years:
        line = f"  {yr:>4d}"
        yr_total = 0
        for m in range(1, 13):
            mask = (monthly_pct.index.year == yr) & (monthly_pct.index.month == m)
            vals = monthly_pct[mask]
            if len(vals) > 0:
                val = vals.iloc[0]
                yr_total += val
                line += f" {val:>6.1f}"
            else:
                line += f" {'--':>6s}"
        line += f" {yr_total:>6.1f}%"
        print(line)

    # Summary stats
    print(f"\n  Monthly return statistics:")
    print(f"    Mean:   {monthly_pct.mean():>6.2f}%")
    print(f"    Median: {monthly_pct.median():>6.2f}%")
    print(f"    Std:    {monthly_pct.std():>6.2f}%")
    print(f"    Skew:   {monthly_pct.skew():>6.2f}")
    print(f"    Kurt:   {monthly_pct.kurtosis():>6.2f}")
    print(f"    Best:   {monthly_pct.max():>6.2f}% ({monthly_pct.idxmax().strftime('%Y-%m')})")
    print(f"    Worst:  {monthly_pct.min():>6.2f}% ({monthly_pct.idxmin().strftime('%Y-%m')})")
    print(f"    %Pos:   {(monthly_pct > 0).mean()*100:>5.1f}%")

    return monthly_pct


def plot_detailed(equity, returns, monthly_pct, df_yearly, save_path=None):
    """4-panel detailed chart."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))

    # Panel 1: Equity curve
    ax = axes[0, 0]
    ax.plot(equity.index, equity.values, color="#2196F3", linewidth=1)
    ax.axhline(y=equity.iloc[0], color="gray", linestyle="--", alpha=0.5)
    ax.set_title("Equity Curve (3 Survivors, Net)")
    ax.set_ylabel("Equity ($)")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    # Panel 2: Underwater (drawdown) chart
    ax = axes[0, 1]
    peak = equity.expanding().max()
    dd = (equity - peak) / peak * 100
    ax.fill_between(dd.index, 0, dd.values, color="#F44336", alpha=0.4)
    ax.set_title("Drawdown")
    ax.set_ylabel("Drawdown (%)")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    # Panel 3: Rolling 3-year Sharpe
    ax = axes[1, 0]
    pct_ret = returns / equity.shift(1)
    pct_ret = pct_ret.dropna()
    rolling_mean = pct_ret.rolling(756).mean() * 256
    rolling_std = pct_ret.rolling(756).std() * np.sqrt(256)
    rolling_sharpe = rolling_mean / rolling_std
    rolling_sharpe = rolling_sharpe.dropna()
    ax.plot(rolling_sharpe.index, rolling_sharpe.values, color="#FF9800",
            linewidth=1)
    ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
    ax.set_title("Rolling 3-Year Sharpe")
    ax.set_ylabel("Sharpe Ratio")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    # Panel 4: Annual PnL bar chart
    ax = axes[1, 1]
    years = df_yearly["Year"].values
    pnls = df_yearly["PnL ($)"].values
    colors = ["#4CAF50" if p >= 0 else "#F44336" for p in pnls]
    ax.bar(years, pnls, color=colors, alpha=0.8)
    ax.axhline(y=0, color="gray", linewidth=0.5)
    ax.set_title("Annual PnL ($)")
    ax.set_ylabel("PnL ($)")
    ax.grid(True, alpha=0.3, axis="y")

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
    print(f" PHASE 6b DETAIL: 3 SURVIVORS DEEP DIVE")
    print(f"{'='*80}")
    print(f" Instruments: {SURVIVORS}")
    print(f" Vol target: {vol_target:.0%}, Capital: ${capital:,.0f}, "
          f"Buffer: {buffer_fraction:.0%}")
    print(f" Costs: Darwinex Zero (spread + commission + hist swap)")
    print(f"{'='*80}")

    # Load rates
    from core.carry import load_rates, _rates_to_daily
    rates_monthly = load_rates(ROOT / "data")
    daily_idx = pd.date_range("1999-01-01", "2027-12-31", freq="B")
    rates_daily = _rates_to_daily(rates_monthly, daily_idx)
    ref_rates = build_reference_rates(rates_daily)

    # Prepare instruments
    print(f"\nPreparing instruments...")
    instrument_data = prepare_instruments()
    costs = build_costs_dict()

    # Run backtest
    print(f"\nRunning backtest (net, hist swap)...")
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

    equity = results["equity"]
    returns = results["returns"]
    metrics = calculate_metrics(equity, returns, capital)

    # 1. Full portfolio metrics
    print_metrics(metrics, title="PORTFOLIO: 3 Survivors (Net, Hist Swap)")
    print(f"  IDM: {results['idm']:.4f}")
    print(f"  Weights: {1.0/len(SURVIVORS):.2%} each")

    # 2. Yearly breakdown
    df_yearly = yearly_metrics(equity, returns, capital)
    print_yearly_table(df_yearly)

    # 3. Per-instrument yearly PnL
    df_inst = instrument_yearly_pnl(results["instrument_returns"])
    print_instrument_yearly(df_inst)

    # 4. Drawdown episodes
    episodes = top_drawdowns(equity, n=5)
    print_drawdown_episodes(episodes)

    # 5. Monthly detail
    monthly_pct = print_monthly_stats(returns, equity)

    # 6. Cost breakdown
    print(f"\n{'='*80}")
    print(f" COST BREAKDOWN (3 Survivors)")
    print(f"{'='*80}")
    n_years = len(equity) / 252
    for name in SURVIVORS:
        tc = results["inst_trade_costs"].get(name, 0)
        sc = results["inst_swap_costs"].get(name, 0)
        gross = results["instrument_returns"][name].sum() + tc + sc
        print(f"  {name:<12s}  Gross: ${gross:>9,.0f}  "
              f"Trade: ${tc:>7,.0f}  Swap: ${sc:>7,.0f}  "
              f"Net: ${results['instrument_returns'][name].sum():>9,.0f}")
    total_tc = sum(results["inst_trade_costs"].values())
    total_sc = sum(results["inst_swap_costs"].values())
    print(f"  {'TOTAL':<12s}  Trade: ${total_tc:>7,.0f}/total "
          f"(${total_tc/n_years:>5,.0f}/yr)  "
          f"Swap: ${total_sc:>7,.0f}/total "
          f"(${total_sc/n_years:>5,.0f}/yr)")

    # 7. Detailed chart
    plot_detailed(
        equity, returns, monthly_pct, df_yearly,
        save_path=analysis_dir / "phase6b_survivors_detail.png",
    )

    print(f"\n{'='*80}")
    print(f" ANALYSIS COMPLETE")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
