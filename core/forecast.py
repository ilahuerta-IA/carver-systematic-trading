"""
Forecast calculation module.

Implements EWMAC (Exponentially Weighted Moving Average Crossover)
following Robert Carver's framework. All parameters from published literature.
"""

import numpy as np
import pandas as pd

# Carver's standard EWMAC speed pairs (DO NOT OPTIMIZE)
EWMAC_SPEEDS = [
    (8, 32),
    (16, 64),
    (32, 128),
    (64, 256),
]

# Forecast scalars per speed pair from pysystemtrade (Carver, Ch. 15)
# Calibrated so that abs(forecast).mean() ~ 10 for each individual speed
# Slower crossovers have SMALLER scalars (less raw signal variance)
EWMAC_FORECAST_SCALARS = {
    (2, 8): 10.6,
    (4, 16): 7.5,
    (8, 32): 5.3,
    (16, 64): 3.75,
    (32, 128): 2.65,
    (64, 256): 1.87,
}

# Absolute cap on forecast (Carver's rule)
FORECAST_CAP = 20.0

# Volatility lookback for price vol estimate (exponential std, span in days)
VOL_LOOKBACK = 36


def price_volatility(close, span=VOL_LOOKBACK):
    """
    Daily price volatility in price units.
    Uses exponentially weighted standard deviation of percentage returns,
    then multiplied by current price to get point volatility.

    Args:
        close: pd.Series of closing prices
        span: lookback period for exponential weighting (default 36 days)

    Returns:
        pd.Series of daily price volatility in absolute terms
    """
    pct_returns = close.pct_change()
    vol_pct = pct_returns.ewm(span=span, min_periods=span).std()
    return vol_pct * close


def ewmac_raw(close, fast_span, slow_span):
    """
    Raw EWMAC signal: EMA(fast) - EMA(slow).

    Args:
        close: pd.Series of closing prices
        fast_span: fast EMA period
        slow_span: slow EMA period

    Returns:
        pd.Series of raw EWMAC values (in price units)
    """
    ema_fast = close.ewm(span=fast_span, min_periods=fast_span).mean()
    ema_slow = close.ewm(span=slow_span, min_periods=slow_span).mean()
    return ema_fast - ema_slow


def ewmac_forecast(close, fast_span, slow_span, forecast_scalar=None):
    """
    Scaled and capped EWMAC forecast.

    Steps:
        1. Raw EWMAC = EMA(fast) - EMA(slow)
        2. Normalize by price volatility
        3. Scale by forecast scalar (so abs(forecast).mean() ~ 10)
        4. Cap at +/- 20

    Args:
        close: pd.Series of closing prices
        fast_span: fast EMA period (e.g. 64)
        slow_span: slow EMA period (e.g. 256)
        forecast_scalar: multiplier to normalize. If None, uses
                         per-speed lookup from EWMAC_FORECAST_SCALARS.

    Returns:
        pd.Series of forecast values in [-20, +20]
    """
    raw = ewmac_raw(close, fast_span, slow_span)
    vol = price_volatility(close)

    if forecast_scalar is None:
        forecast_scalar = EWMAC_FORECAST_SCALARS.get(
            (fast_span, slow_span), 5.3  # fallback to middle value
        )

    # Avoid division by zero
    vol_safe = vol.replace(0, np.nan)

    scaled = (raw / vol_safe) * forecast_scalar

    # Cap at +/- FORECAST_CAP
    capped = scaled.clip(lower=-FORECAST_CAP, upper=FORECAST_CAP)

    return capped


def combine_forecasts(forecasts, weights=None, fdm=1.0):
    """
    Combine multiple forecast Series into one using weighted average + FDM.

    Args:
        forecasts: list of pd.Series (individual forecasts)
        weights: list of floats (must sum to 1.0). None = equal weights.
        fdm: Forecast Diversification Multiplier (typically 1.2-1.3)

    Returns:
        pd.Series of combined forecast, capped at +/- 20
    """
    n = len(forecasts)
    if weights is None:
        weights = [1.0 / n] * n

    if abs(sum(weights) - 1.0) > 0.01:
        raise ValueError(f"Weights must sum to 1.0, got {sum(weights):.3f}")

    combined = sum(f * w for f, w in zip(forecasts, weights))
    combined = combined * fdm
    combined = combined.clip(lower=-FORECAST_CAP, upper=FORECAST_CAP)

    return combined
