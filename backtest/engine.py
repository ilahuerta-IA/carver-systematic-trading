"""
Backtest engine for Carver systematic trading.

Simple pandas-based daily loop:
    forecast -> position ideal -> buffer -> adjust -> PnL

No backtrader dependency. One pass through daily bars.
"""

import numpy as np
import pandas as pd
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.forecast import (
    ewmac_forecast,
    price_volatility,
    FORECAST_CAP,
    VOL_LOOKBACK,
)


def calculate_position(forecast, vol_target_annual, capital,
                       price_vol, point_value=1.0):
    """
    Carver position sizing formula.

    Position = (Forecast / 10) * (Daily_Risk / (Price_Vol * Point_Value))

    where Daily_Risk = Capital * Vol_Target_Annual / sqrt(256)

    Args:
        forecast: pd.Series of forecast values [-20, +20]
        vol_target_annual: float, e.g. 0.12 for 12%
        capital: float, starting capital
        price_vol: pd.Series of daily price volatility (absolute)
        point_value: float, value per point move per contract (1.0 for stocks/ETFs)

    Returns:
        pd.Series of ideal position size (can be fractional, negative = short)
    """
    daily_risk = capital * vol_target_annual / np.sqrt(256)

    # Avoid division by zero
    vol_safe = price_vol.replace(0, np.nan)

    position = (forecast / 10.0) * (daily_risk / (vol_safe * point_value))

    return position


def apply_buffer(ideal_position, current_position, buffer_fraction=0.10,
                 base_forecast=10.0, vol_target_annual=0.12,
                 capital=100000, price_vol=None, point_value=1.0):
    """
    Apply Carver buffering (dead zone).

    Buffer = buffer_fraction * position_at_base_forecast

    Only adjust if ideal is outside current +/- buffer.

    Args:
        ideal_position: pd.Series
        current_position: pd.Series
        buffer_fraction: float (0.10 = 10%)
        Others: for calculating base position size

    Returns:
        pd.Series of actual position after buffering
    """
    daily_risk = capital * vol_target_annual / np.sqrt(256)
    vol_safe = price_vol.replace(0, np.nan)
    base_position = abs((base_forecast / 10.0) * (daily_risk / (vol_safe * point_value)))
    buffer_size = buffer_fraction * base_position

    upper = current_position + buffer_size
    lower = current_position - buffer_size

    # If ideal is within buffer, keep current; otherwise move to ideal
    new_position = current_position.copy()
    above = ideal_position > upper
    below = ideal_position < lower

    new_position[above] = ideal_position[above]
    new_position[below] = ideal_position[below]

    return new_position


def run_backtest(close, forecast, vol_target_annual=0.12, capital=100000,
                 point_value=1.0, buffer_fraction=0.10,
                 cost_per_trade=0.0):
    """
    Run a single-instrument backtest with Carver position sizing.

    Args:
        close: pd.Series of daily closing prices (DatetimeIndex)
        forecast: pd.Series of forecast values [-20, +20]
        vol_target_annual: target portfolio volatility (e.g. 0.12)
        capital: starting capital
        point_value: value per point per contract
        buffer_fraction: buffering dead zone (0.10 = 10%)
        cost_per_trade: estimated cost per unit traded (in currency)

    Returns:
        dict with:
            - equity: pd.Series (equity curve)
            - positions: pd.Series (position held each day)
            - returns: pd.Series (daily returns in currency)
            - forecast: pd.Series (forecast used)
            - trades: int (number of position changes)
    """
    vol = price_volatility(close)

    # Day-by-day loop with dynamic capital (mark-to-market)
    position = pd.Series(0.0, index=close.index)
    ideal_pos = pd.Series(0.0, index=close.index)
    equity_arr = pd.Series(float(capital), index=close.index)
    daily_pnl = pd.Series(0.0, index=close.index)

    for i in range(1, len(close)):
        # Current equity = mark-to-market capital
        current_capital = equity_arr.iloc[i - 1]

        # Skip if vol not available
        vol_today = vol.iloc[i]
        fc_today = forecast.iloc[i]

        if pd.isna(vol_today) or vol_today == 0 or pd.isna(fc_today):
            position.iloc[i] = position.iloc[i - 1]
            equity_arr.iloc[i] = current_capital
            continue

        # Ideal position with mark-to-market capital
        daily_risk = current_capital * vol_target_annual / np.sqrt(256)
        ideal = (fc_today / 10.0) * (daily_risk / (vol_today * point_value))
        ideal_pos.iloc[i] = ideal

        # Buffer based on base position (forecast = 10)
        base_pos = abs(daily_risk / (vol_today * point_value))
        buf = buffer_fraction * base_pos

        prev_pos = position.iloc[i - 1]
        if ideal > prev_pos + buf:
            position.iloc[i] = ideal
        elif ideal < prev_pos - buf:
            position.iloc[i] = ideal
        else:
            position.iloc[i] = prev_pos

        # PnL from yesterday's position
        price_change = close.iloc[i] - close.iloc[i - 1]
        pnl = position.iloc[i - 1] * price_change * point_value

        # Trading costs
        pos_change = abs(position.iloc[i] - position.iloc[i - 1])
        cost = pos_change * cost_per_trade

        daily_pnl.iloc[i] = pnl - cost
        equity_arr.iloc[i] = current_capital + daily_pnl.iloc[i]

    # Trade count (days where position changed)
    trades = (position.diff().abs() > 0.001).sum()

    return {
        "equity": equity_arr,
        "positions": position,
        "returns": daily_pnl,
        "forecast": forecast,
        "price_vol": vol,
        "ideal_positions": ideal_pos,
        "trades": int(trades),
    }
