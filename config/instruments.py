"""
Instrument configuration.

Metadata for all traded instruments: asset class, currencies, carry parameters.
All values from public sources (not optimized).
"""

# Asset class definitions with carry-relevant metadata
# - funding_currency: currency used for financing cost calculation
# - For FX: base and quote currencies define the carry direction
# - For equity: div_yield_approx is a rough average (not time-varying)
# - For commodities: no yield, carry = -funding_rate (always negative)

INSTRUMENTS = {
    # === EQUITY INDICES ===
    "SP500": {
        "asset_class": "equity",
        "funding_currency": "USD",
        "div_yield_approx": 0.015,   # ~1.5% average trailing yield
        "yahoo_ticker": "SPY",
        "point_value": 1.0,
    },
    "NASDAQ100": {
        "asset_class": "equity",
        "funding_currency": "USD",
        "div_yield_approx": 0.006,   # ~0.6% average trailing yield
        "yahoo_ticker": "QQQ",
        "point_value": 1.0,
    },
    "DAX40": {
        "asset_class": "equity",
        "funding_currency": "EUR",
        "div_yield_approx": 0.025,   # ~2.5% average trailing yield
        "yahoo_ticker": "^GDAXI",
        "point_value": 1.0,
    },
    "NIKKEI225": {
        "asset_class": "equity",
        "funding_currency": "JPY",
        "div_yield_approx": 0.015,   # ~1.5% average trailing yield
        "yahoo_ticker": "^N225",
        "point_value": 1.0,
    },

    # === COMMODITIES ===
    "GOLD": {
        "asset_class": "commodity",
        "funding_currency": "USD",
        "yahoo_ticker": "GC=F",
        "point_value": 1.0,
    },
    "SILVER": {
        "asset_class": "commodity",
        "funding_currency": "USD",
        "yahoo_ticker": "SI=F",
        "point_value": 1.0,
    },

    # === FOREX ===
    "EURUSD": {
        "asset_class": "fx",
        "base_currency": "EUR",
        "quote_currency": "USD",
        "yahoo_ticker": "EURUSD=X",
        "point_value": 1.0,
    },
    "USDJPY": {
        "asset_class": "fx",
        "base_currency": "USD",
        "quote_currency": "JPY",
        "yahoo_ticker": "USDJPY=X",
        "point_value": 1.0,
    },
    "AUDUSD": {
        "asset_class": "fx",
        "base_currency": "AUD",
        "quote_currency": "USD",
        "yahoo_ticker": "AUDUSD=X",
        "point_value": 1.0,
    },
    "GBPUSD": {
        "asset_class": "fx",
        "base_currency": "GBP",
        "quote_currency": "USD",
        "yahoo_ticker": "GBPUSD=X",
        "point_value": 1.0,
    },
}
