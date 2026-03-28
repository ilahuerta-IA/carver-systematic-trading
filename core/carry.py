"""
Carry forecast calculation.

Carry = expected return from holding a position, excluding price movements.
- FX: interest rate differential (base - quote)
- Equity: dividend yield - funding rate
- Commodities: -funding rate (no yield, pay financing)

Normalized by instrument volatility, scaled to forecast range [-20, +20].
Carry scalar from Carver's published literature.
"""

import numpy as np
import pandas as pd
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.forecast import price_volatility, FORECAST_CAP, VOL_LOOKBACK
from config.instruments import INSTRUMENTS

# Carry forecast scalar (Carver, pysystemtrade)
# Calibrated so abs(carry_forecast).mean() ~ 10
# Carry signals are smoother/smaller than EWMAC, so scalar is larger
CARRY_SCALAR = 30.0


def load_rates(data_dir):
    """
    Load interest rate CSV (monthly frequency).

    Args:
        data_dir: Path to data/ directory containing interest_rates.csv

    Returns:
        pd.DataFrame with DatetimeIndex and columns: USD, EUR, JPY, AUD, GBP
        Values in percent per annum (e.g. 5.0 = 5%).
    """
    path = Path(data_dir) / "interest_rates.csv"
    rates = pd.read_csv(path, index_col="Date", parse_dates=True)
    return rates


def _rates_to_daily(rates_monthly, daily_index):
    """
    Expand monthly rates to daily frequency by forward-filling.

    Args:
        rates_monthly: pd.DataFrame with monthly DatetimeIndex
        daily_index: pd.DatetimeIndex (target daily dates)

    Returns:
        pd.DataFrame reindexed to daily frequency
    """
    # Reindex to daily and forward-fill
    rates_daily = rates_monthly.reindex(daily_index, method="ffill")
    # Backfill any leading NaNs at the start
    rates_daily = rates_daily.bfill()
    return rates_daily


def _annualized_vol(close, span=VOL_LOOKBACK):
    """
    Annualized volatility from daily returns (same method as EWMAC).

    Args:
        close: pd.Series of daily prices

    Returns:
        pd.Series of annualized volatility (decimal, e.g. 0.12 = 12%)
    """
    pct_returns = close.pct_change()
    daily_vol = pct_returns.ewm(span=span, min_periods=span).std()
    return daily_vol * np.sqrt(256)


def carry_annualized(instrument_name, rates_daily):
    """
    Calculate annualized carry for one instrument (in decimal terms).

    Args:
        instrument_name: key in INSTRUMENTS dict (e.g. 'EURUSD', 'SP500')
        rates_daily: pd.DataFrame of daily rates (columns: USD, EUR, etc.)
                     Values in % p.a.

    Returns:
        pd.Series of annualized carry (decimal, e.g. 0.03 = 3%)
    """
    cfg = INSTRUMENTS[instrument_name]
    asset_class = cfg["asset_class"]

    if asset_class == "fx":
        # FX carry = base rate - quote rate
        # Long EURUSD = earn EUR rate, pay USD rate
        base = cfg["base_currency"]
        quote = cfg["quote_currency"]
        carry = (rates_daily[base] - rates_daily[quote]) / 100.0

    elif asset_class == "equity":
        # Equity carry = dividend yield - funding rate
        funding_ccy = cfg["funding_currency"]
        div_yield = cfg["div_yield_approx"]  # static approximation
        funding_rate = rates_daily[funding_ccy] / 100.0
        carry = pd.Series(div_yield, index=rates_daily.index) - funding_rate

    elif asset_class == "commodity":
        # Commodity carry = -funding rate (no yield, pay financing)
        funding_ccy = cfg["funding_currency"]
        carry = -rates_daily[funding_ccy] / 100.0

    else:
        raise ValueError(f"Unknown asset class: {asset_class}")

    carry.name = instrument_name
    return carry


def carry_forecast(instrument_name, close, rates_daily,
                   carry_scalar=CARRY_SCALAR):
    """
    Calculate carry forecast for one instrument.

    Steps:
        1. Calculate annualized carry (rate differential or yield - funding)
        2. Normalize by annualized volatility of the instrument
        3. Scale by carry_scalar (so abs(forecast).mean() ~ 10)
        4. Cap at +/- 20

    Args:
        instrument_name: key in INSTRUMENTS dict
        close: pd.Series of daily prices (DatetimeIndex)
        rates_daily: pd.DataFrame of daily rates (% p.a.)
        carry_scalar: multiplier for normalization (default 30.0)

    Returns:
        pd.Series of carry forecast values in [-20, +20]
    """
    # Annualized carry (decimal)
    carry = carry_annualized(instrument_name, rates_daily)

    # Align carry to price index
    carry = carry.reindex(close.index, method="ffill")

    # Annualized vol of the instrument (decimal)
    ann_vol = _annualized_vol(close)

    # Avoid division by zero
    ann_vol_safe = ann_vol.replace(0, np.nan)

    # Raw carry forecast = carry / vol
    raw = carry / ann_vol_safe

    # Scale
    scaled = raw * carry_scalar

    # Cap
    forecast = scaled.clip(lower=-FORECAST_CAP, upper=FORECAST_CAP)

    return forecast
