"""
Performance metrics and plotting for backtest results.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Set to False to skip plt.show() (e.g. when saving only)
SHOW_INTERACTIVE = True


def calculate_metrics(equity, returns, capital=100000):
    """
    Calculate comprehensive performance metrics from backtest results.

    Args:
        equity: pd.Series (equity curve)
        returns: pd.Series (daily PnL in currency)
        capital: starting capital

    Returns:
        dict of metrics
    """
    returns_clean = returns.dropna()

    total_return = (equity.iloc[-1] / capital) - 1.0
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

    # Percentage returns (daily PnL / previous day equity)
    pct_returns = returns / equity.shift(1)
    pct_returns = pct_returns.dropna()
    pct_returns = pct_returns[pct_returns.index >= returns_clean.index[0]]

    # Annualized volatility (from percentage returns)
    daily_vol_pct = pct_returns.std()
    annual_vol = daily_vol_pct * np.sqrt(256)

    # Sharpe ratio (assuming 0 risk-free rate)
    daily_mean_pct = pct_returns.mean()
    sharpe = (daily_mean_pct / daily_vol_pct * np.sqrt(256)) if daily_vol_pct > 0 else 0

    # Sortino ratio (downside deviation only)
    downside = pct_returns[pct_returns < 0]
    downside_std = downside.std() if len(downside) > 0 else 0
    sortino = (daily_mean_pct / downside_std * np.sqrt(256)) if downside_std > 0 else 0

    # Max drawdown + duration
    peak = equity.expanding().max()
    drawdown = (equity - peak) / peak
    max_dd = drawdown.min()

    # Drawdown duration (longest time underwater)
    underwater = drawdown < 0
    groups = (~underwater).cumsum()
    if underwater.any():
        dd_durations = underwater.groupby(groups).sum()
        max_dd_days = int(dd_durations.max())
    else:
        max_dd_days = 0

    # Calmar ratio (CAGR / |MaxDD|)
    calmar = abs(cagr / max_dd) if max_dd != 0 else 0

    # Profit factor
    gains = returns_clean[returns_clean > 0].sum()
    losses = abs(returns_clean[returns_clean < 0].sum())
    pf = gains / losses if losses > 0 else float("inf")

    # Win rate (daily)
    win_days = (returns_clean > 0).sum()
    total_days = len(returns_clean[returns_clean != 0])
    win_rate = win_days / total_days if total_days > 0 else 0

    # Average win / average loss
    avg_win = returns_clean[returns_clean > 0].mean() if (returns_clean > 0).any() else 0
    avg_loss = returns_clean[returns_clean < 0].mean() if (returns_clean < 0).any() else 0
    payoff_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0

    # Monthly returns for Monte Carlo-style stats
    monthly_pnl = returns.resample("ME").sum()
    monthly_pct = monthly_pnl / equity.resample("ME").first().shift(0)
    monthly_pct = monthly_pct.dropna()
    pct_positive_months = (monthly_pct > 0).mean() * 100 if len(monthly_pct) > 0 else 0
    best_month_pct = monthly_pct.max() * 100 if len(monthly_pct) > 0 else 0
    worst_month_pct = monthly_pct.min() * 100 if len(monthly_pct) > 0 else 0

    return {
        "total_return_pct": total_return * 100,
        "cagr_pct": cagr * 100,
        "annual_vol_pct": annual_vol * 100,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "max_dd_pct": max_dd * 100,
        "max_dd_days": max_dd_days,
        "profit_factor": pf,
        "win_rate_pct": win_rate * 100,
        "payoff_ratio": payoff_ratio,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "pct_positive_months": pct_positive_months,
        "best_month_pct": best_month_pct,
        "worst_month_pct": worst_month_pct,
        "total_pnl": equity.iloc[-1] - capital,
        "years": years,
    }


def print_metrics(metrics, title=""):
    """Print metrics in a clean table."""
    if title:
        print(f"\n{'=' * 50}")
        print(f"  {title}")
        print(f"{'=' * 50}")

    print(f"  --- Rendimiento ---")
    print(f"  Total Return:      {metrics['total_return_pct']:>8.2f}%")
    print(f"  CAGR:              {metrics['cagr_pct']:>8.2f}%")
    print(f"  Total PnL:       ${metrics['total_pnl']:>10,.0f}")
    print(f"  Duration:          {metrics['years']:>8.1f} years")
    print()
    print(f"  --- Riesgo ---")
    print(f"  Annual Vol:        {metrics['annual_vol_pct']:>8.2f}%")
    print(f"  Max Drawdown:      {metrics['max_dd_pct']:>8.2f}%")
    print(f"  Max DD Duration:   {metrics['max_dd_days']:>5d} days")
    print()
    print(f"  --- Ratios ---")
    print(f"  Sharpe:            {metrics['sharpe']:>8.2f}")
    print(f"  Sortino:           {metrics['sortino']:>8.2f}")
    print(f"  Calmar:            {metrics['calmar']:>8.2f}")
    print(f"  Profit Factor:     {metrics['profit_factor']:>8.2f}")
    print()
    print(f"  --- Win/Loss ---")
    print(f"  Win Rate (daily):  {metrics['win_rate_pct']:>8.1f}%")
    print(f"  Payoff Ratio:      {metrics['payoff_ratio']:>8.2f}")
    print(f"  Avg Win:         ${metrics['avg_win']:>10,.2f}")
    print(f"  Avg Loss:        ${metrics['avg_loss']:>10,.2f}")
    print()
    print(f"  --- Mensual ---")
    print(f"  Meses positivos:   {metrics['pct_positive_months']:>8.1f}%")
    print(f"  Mejor mes:         {metrics['best_month_pct']:>8.2f}%")
    print(f"  Peor mes:          {metrics['worst_month_pct']:>8.2f}%")
    print()


def plot_equity_drawdown(results, title="Equity & Drawdown", save_path=None):
    """
    Chart 1: Equity curve with drawdown overlay and underwater periods.
    Similar to what TradingSystem produced.
    """
    equity = results["equity"]

    peak = equity.expanding().max()
    drawdown = (equity - peak) / peak * 100

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1.5]})
    fig.suptitle(title, fontsize=14, fontweight="bold")

    # --- Top: Equity ---
    ax1.plot(equity.index, equity.values, color="#2196F3", linewidth=1.2,
             label=f"Equity (final: ${equity.iloc[-1]:,.0f})")
    ax1.fill_between(equity.index, equity.iloc[0], equity.values,
                     where=equity >= equity.iloc[0], color="#4CAF50", alpha=0.08)
    ax1.fill_between(equity.index, equity.iloc[0], equity.values,
                     where=equity < equity.iloc[0], color="#F44336", alpha=0.08)
    ax1.axhline(y=equity.iloc[0], color="gray", linestyle="--", alpha=0.5,
                label=f"Capital inicial: ${equity.iloc[0]:,.0f}")

    # Mark max equity and max drawdown point
    max_eq_idx = equity.idxmax()
    ax1.annotate(f"Max: ${equity.max():,.0f}",
                 xy=(max_eq_idx, equity.max()),
                 fontsize=8, color="#2196F3",
                 ha="center", va="bottom")

    ax1.set_ylabel("Equity ($)", fontsize=11)
    ax1.legend(loc="upper left", fontsize=9)
    ax1.grid(True, alpha=0.3)

    # --- Bottom: Drawdown ---
    ax2.fill_between(drawdown.index, drawdown.values, 0,
                     color="#F44336", alpha=0.4)
    ax2.plot(drawdown.index, drawdown.values, color="#D32F2F", linewidth=0.6)

    # Mark worst drawdown
    worst_dd_idx = drawdown.idxmin()
    worst_dd_val = drawdown.min()
    ax2.annotate(f"Max DD: {worst_dd_val:.1f}%",
                 xy=(worst_dd_idx, worst_dd_val),
                 xytext=(worst_dd_idx, worst_dd_val - 3),
                 fontsize=9, fontweight="bold", color="#D32F2F",
                 ha="center",
                 arrowprops=dict(arrowstyle="->", color="#D32F2F"))

    ax2.set_ylabel("Drawdown (%)", fontsize=11)
    ax2.set_xlabel("Fecha", fontsize=11)
    ax2.set_ylim(worst_dd_val * 1.3, 2)
    ax2.grid(True, alpha=0.3)
    ax2.axhline(y=0, color="gray", linewidth=0.5)

    ax2.xaxis.set_major_locator(mdates.YearLocator(2))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    plt.tight_layout()

    if save_path:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  Chart saved: {save_path}")

    if SHOW_INTERACTIVE:
        plt.show()
    else:
        plt.close()


def plot_position_on_price(results, close, title="Position on Price",
                           save_path=None):
    """
    Chart 2: Price with position overlay (colored background).
    Green = long, red = short, gray = flat. Position size shown as intensity.
    """
    positions = results["positions"]
    forecast = results["forecast"]

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True,
                              gridspec_kw={"height_ratios": [3, 1.5, 1.5]})
    fig.suptitle(title, fontsize=14, fontweight="bold")

    # --- Top: Price with position-colored background ---
    ax = axes[0]
    ax.plot(close.index, close.values, color="#333333", linewidth=0.8,
            label="Precio", zorder=3)

    # Normalize position for color intensity (alpha)
    pos_abs_max = positions.abs().max()
    if pos_abs_max > 0:
        pos_norm = positions / pos_abs_max
    else:
        pos_norm = positions * 0

    # Color spans based on position direction
    for i in range(1, len(close)):
        p = pos_norm.iloc[i]
        if abs(p) < 0.01:
            continue
        color = "#4CAF50" if p > 0 else "#F44336"
        alpha = min(abs(p) * 0.35, 0.35)
        ax.axvspan(close.index[i - 1], close.index[i],
                   color=color, alpha=alpha, linewidth=0)

    # Mark significant position changes (>30% of max)
    pos_changes = positions.diff().abs()
    significant = pos_changes > pos_abs_max * 0.3
    sig_dates = positions.index[significant]
    for d in sig_dates:
        ax.axvline(d, color="#FF9800", alpha=0.3, linewidth=0.5)

    ax.set_ylabel("Precio", fontsize=11)
    ax.grid(True, alpha=0.3)

    # Legend proxy
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#4CAF50", alpha=0.3, label="Long"),
        Patch(facecolor="#F44336", alpha=0.3, label="Short"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", fontsize=9)

    # --- Middle: Position size ---
    ax = axes[1]
    ax.fill_between(positions.index, positions.values, 0,
                    where=positions >= 0, color="#4CAF50", alpha=0.5)
    ax.fill_between(positions.index, positions.values, 0,
                    where=positions < 0, color="#F44336", alpha=0.5)
    ax.axhline(y=0, color="gray", linewidth=0.8)
    ax.set_ylabel("Posición (unidades)", fontsize=11)
    ax.grid(True, alpha=0.3)

    # --- Bottom: Forecast ---
    ax = axes[2]
    ax.plot(forecast.index, forecast.values, color="#FF9800", linewidth=0.6)
    ax.axhline(y=0, color="gray", linestyle="-", alpha=0.5)
    ax.axhline(y=20, color="red", linestyle="--", alpha=0.3, label="Cap ±20")
    ax.axhline(y=-20, color="red", linestyle="--", alpha=0.3)
    ax.axhline(y=10, color="green", linestyle="--", alpha=0.2, label="Base ±10")
    ax.axhline(y=-10, color="green", linestyle="--", alpha=0.2)
    ax.set_ylabel("Forecast", fontsize=11)
    ax.set_xlabel("Fecha", fontsize=11)
    ax.set_ylim(-25, 25)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.3)

    axes[-1].xaxis.set_major_locator(mdates.YearLocator(2))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    plt.tight_layout()

    if save_path:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  Chart saved: {save_path}")

    if SHOW_INTERACTIVE:
        plt.show()
    else:
        plt.close()


def generate_adjustment_log(results, close, save_path=None):
    """
    Generate a log of every position adjustment.
    Returns a DataFrame with date, action, old_pos, new_pos, delta, price, equity.
    Optionally saves to CSV.
    """
    positions = results["positions"]
    equity = results["equity"]
    forecast = results["forecast"]

    pos_diff = positions.diff()
    changes = pos_diff[pos_diff.abs() > 0.001]

    records = []
    for date in changes.index:
        old_pos = positions.shift(1).loc[date]
        new_pos = positions.loc[date]
        delta = new_pos - old_pos
        price = close.loc[date]
        eq = equity.loc[date]
        fc = forecast.loc[date] if date in forecast.index else np.nan

        if old_pos == 0 and new_pos != 0:
            action = "OPEN_LONG" if new_pos > 0 else "OPEN_SHORT"
        elif new_pos == 0:
            action = "CLOSE_ALL"
        elif abs(new_pos) > abs(old_pos):
            action = "ADD" if np.sign(new_pos) == np.sign(old_pos) else "FLIP"
        elif abs(new_pos) < abs(old_pos):
            action = "REDUCE"
        else:
            action = "FLIP" if np.sign(new_pos) != np.sign(old_pos) else "ADJUST"

        records.append({
            "date": date,
            "action": action,
            "old_pos": round(old_pos, 4),
            "new_pos": round(new_pos, 4),
            "delta": round(delta, 4),
            "price": round(price, 2),
            "forecast": round(fc, 2) if not np.isnan(fc) else "",
            "equity": round(eq, 2),
        })

    log_df = pd.DataFrame(records)

    if save_path and len(log_df) > 0:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        log_df.to_csv(save_path, index=False)
        print(f"  Adjustment log saved: {save_path} ({len(log_df)} entries)")

    return log_df


def print_adjustment_summary(log_df):
    """Print summary stats from the adjustment log."""
    if len(log_df) == 0:
        print("  No position adjustments.")
        return

    print(f"\n  --- Log de Ajustes ---")
    print(f"  Total ajustes:     {len(log_df):>6d}")

    action_counts = log_df["action"].value_counts()
    for action, count in action_counts.items():
        print(f"    {action:<15s} {count:>5d}")

    years = (log_df["date"].iloc[-1] - log_df["date"].iloc[0]).days / 365.25
    if years > 0:
        print(f"  Ajustes/año:       {len(log_df) / years:>6.1f}")

    # Show last 10 adjustments
    print(f"\n  Últimos 10 ajustes:")
    print(f"  {'Fecha':<12s} {'Acción':<12s} {'Pos Ant':>8s} {'Pos New':>8s} {'Delta':>8s} {'Precio':>10s} {'FC':>6s}")
    print(f"  {'-'*70}")
    for _, row in log_df.tail(10).iterrows():
        fc_str = f"{row['forecast']:.1f}" if row['forecast'] != "" else ""
        print(f"  {str(row['date'].date()):<12s} {row['action']:<12s} "
              f"{row['old_pos']:>8.2f} {row['new_pos']:>8.2f} "
              f"{row['delta']:>+8.2f} {row['price']:>10.2f} {fc_str:>6s}")


def plot_forecast_distribution(forecast, title="Forecast Distribution",
                               save_path=None):
    """
    Plot forecast distribution to validate it approximates N(0, 10).

    Args:
        forecast: pd.Series of forecast values
        title: plot title
        save_path: if provided, save figure
    """
    forecast_clean = forecast.dropna()

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle(title, fontsize=13, fontweight="bold")

    # Histogram — exclude capped values to avoid spike
    ax = axes[0]
    pct_at_pos_cap = (forecast_clean >= 19.9).mean() * 100
    pct_at_neg_cap = (forecast_clean <= -19.9).mean() * 100
    inner = forecast_clean[(forecast_clean > -19.9) & (forecast_clean < 19.9)]

    ax.hist(inner, bins=60, density=True, alpha=0.7,
            color="#2196F3", edgecolor="white", label="Inner values")

    # Overlay normal distribution N(0, 10)
    x = np.linspace(-25, 25, 200)
    mu = 0
    sigma = 10
    normal = (1 / (sigma * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x - mu) / sigma) ** 2)
    ax.plot(x, normal, "r--", linewidth=2, label="N(0, 10) target")

    # Annotate capped percentages
    if pct_at_pos_cap > 0.5:
        ax.annotate(f"Cap +20\n{pct_at_pos_cap:.1f}%",
                    xy=(20, 0), xytext=(18, ax.get_ylim()[1] * 0.85),
                    fontsize=9, fontweight="bold", color="#D32F2F",
                    ha="center",
                    arrowprops=dict(arrowstyle="->", color="#D32F2F"))
    if pct_at_neg_cap > 0.5:
        ax.annotate(f"Cap -20\n{pct_at_neg_cap:.1f}%",
                    xy=(-20, 0), xytext=(-18, ax.get_ylim()[1] * 0.85),
                    fontsize=9, fontweight="bold", color="#D32F2F",
                    ha="center",
                    arrowprops=dict(arrowstyle="->", color="#D32F2F"))

    ax.set_xlabel("Forecast")
    ax.set_ylabel("Density")
    ax.set_title("Distribution")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Stats text
    stats_text = (
        f"Mean: {forecast_clean.mean():.2f}\n"
        f"Std: {forecast_clean.std():.2f}\n"
        f"Abs Mean: {forecast_clean.abs().mean():.2f}\n"
        f"  (target: 10.0)\n"
        f"% at cap: {(forecast_clean.abs() >= 19.9).mean() * 100:.1f}%\n"
        f"Skew: {forecast_clean.skew():.2f}\n"
        f"Kurt: {forecast_clean.kurtosis():.2f}"
    )
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
            verticalalignment="top", fontsize=9, fontfamily="monospace",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

    # Time series
    ax = axes[1]
    ax.plot(forecast_clean.index, forecast_clean.values, linewidth=0.5,
            color="#FF9800", alpha=0.8)
    ax.axhline(y=0, color="gray", linestyle="-", alpha=0.5)
    ax.axhline(y=20, color="red", linestyle="--", alpha=0.3)
    ax.axhline(y=-20, color="red", linestyle="--", alpha=0.3)
    ax.set_xlabel("Date")
    ax.set_ylabel("Forecast")
    ax.set_title("Forecast Over Time")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  Chart saved: {save_path}")

    if SHOW_INTERACTIVE:
        plt.show()
    else:
        plt.close()
