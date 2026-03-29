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


# ---------------------------------------------------------------------------
# Transaction cost parameters (Darwinex Zero, as of 2026-03)
# ---------------------------------------------------------------------------
#
# All values are PRE-COMPUTED per SYSTEM UNIT in the instrument's price
# currency (same currency as PnL). This keeps the cost function trivial.
#
# Mapping from broker contracts to system units:
#   SP500     -> SPY data (~index/10).  1 contract = 10 x index = 100 SPY units
#   NASDAQ100 -> QQQ data (~NDX/40).    1 contract = 10 x NDX   = 400 QQQ units
#   DAX40     -> ^GDAXI (direct).       1 contract = 10 units   (EUR)
#   NIKKEI225 -> ^N225  (direct).       1 contract = 100 units  (JPY)
#   GOLD      -> GC=F   (per oz).       1 contract = 100 oz
#   SILVER    -> SI=F   (per oz).       1 contract = 5000 oz
#   Forex     -> direct quotes.         1 lot      = 100000 units
#
# Fields:
#   half_spread          - half-spread per unit (one-way execution cost)
#   commission_per_unit  - fixed commission per unit traded (per order)
#   commission_pct       - pct of price per unit (GOLD/SILVER only, 0.0025%)
#   swap_long_per_unit   - daily swap for LONG  (neg=pay, pos=receive)
#   swap_short_per_unit  - daily swap for SHORT (neg=pay, pos=receive)
#   units_per_contract   - system units per broker contract (reference only)
#
# IMPORTANT: Swap rates are CURRENT (2026-03) levels. During ZIRP
# (2009-2022), swaps were near zero. Results overestimate historical
# swap costs but reflect current live trading reality.
# ---------------------------------------------------------------------------

INSTRUMENT_COSTS = {
    # === EQUITY INDICES ===
    "SP500": {
        # Broker: SP500 CFD, 10x index, spread 0.6 pts, comm $0.275/contract
        # Swap: -$9.28 long / +$3.93 short per contract per day
        "units_per_contract": 100,
        "half_spread": 0.03,
        "commission_per_unit": 0.00275,
        "commission_pct": 0.0,
        "swap_long_per_unit": -0.0928,
        "swap_short_per_unit": 0.0393,
    },
    "NASDAQ100": {
        # Broker: NDX CFD, 10x index, spread 0.9 pts, comm $2.75/contract
        # Swap: -$35.62 long / +$14.71 short per contract per day
        "units_per_contract": 400,
        "half_spread": 0.01125,
        "commission_per_unit": 0.006875,
        "commission_pct": 0.0,
        "swap_long_per_unit": -0.08905,
        "swap_short_per_unit": 0.036775,
    },
    "DAX40": {
        # Broker: GDAXI CFD, 10x index, spread 0.8 pts, comm EUR 2.75
        # Swap: EUR -22.46 long / +2.54 short per contract per day
        # System currency: EUR
        "units_per_contract": 10,
        "half_spread": 0.40,
        "commission_per_unit": 0.275,
        "commission_pct": 0.0,
        "swap_long_per_unit": -2.246,
        "swap_short_per_unit": 0.254,
    },
    "NIKKEI225": {
        # Broker: NI225 CFD, 100x index, spread 10.0 pts, comm JPY 35
        # Swap: JPY -320.63 long / -112.77 short per contract per day
        # System currency: JPY. Both swaps negative (always pay).
        "units_per_contract": 100,
        "half_spread": 5.0,
        "commission_per_unit": 0.35,
        "commission_pct": 0.0,
        "swap_long_per_unit": -3.2063,
        "swap_short_per_unit": -1.1277,
    },

    # === COMMODITIES ===
    "GOLD": {
        # Broker: XAUUSD, 100 oz, spread 1.87 pts, comm 0.0025% of value
        # Swap: -$65.7 long / +$38.1 short per contract per day
        "units_per_contract": 100,
        "half_spread": 0.935,
        "commission_per_unit": 0.0,
        "commission_pct": 0.000025,
        "swap_long_per_unit": -0.657,
        "swap_short_per_unit": 0.381,
    },
    "SILVER": {
        # Broker: XAGUSD, 5000 oz, spread 0.08 pts, comm 0.0025% of value
        # Swap: -$45 long / +$35 short per contract per day
        "units_per_contract": 5000,
        "half_spread": 0.04,
        "commission_per_unit": 0.0,
        "commission_pct": 0.000025,
        "swap_long_per_unit": -0.009,
        "swap_short_per_unit": 0.007,
    },

    # === FOREX ===
    "EURUSD": {
        # Broker: 100k EUR lot, spread 0.3 pips, comm EUR 2.50/lot (~USD 2.70)
        # Swap: -$9.1 long / +$1.7 short per lot per day
        "units_per_contract": 100000,
        "half_spread": 0.000015,
        "commission_per_unit": 0.000027,
        "commission_pct": 0.0,
        "swap_long_per_unit": -0.000091,
        "swap_short_per_unit": 0.000017,
    },
    "USDJPY": {
        # Broker: 100k USD lot, spread 0.8 pips, comm USD 2.50 (~JPY 375)
        # Swap: JPY +770 long (receive) / -1760 short (pay) per lot per day
        # System currency: JPY. Long = carry trade (receive swap).
        "units_per_contract": 100000,
        "half_spread": 0.004,
        "commission_per_unit": 0.00375,
        "commission_pct": 0.0,
        "swap_long_per_unit": 0.0077,
        "swap_short_per_unit": -0.0176,
    },
    "AUDUSD": {
        # Broker: 100k AUD lot, spread 1.4 pips, comm AUD 2.50 (~USD 1.65)
        # Swap: -$1.2 long / -$2.9 short per lot per day
        # Both swaps negative (always pay).
        "units_per_contract": 100000,
        "half_spread": 0.00007,
        "commission_per_unit": 0.0000165,
        "commission_pct": 0.0,
        "swap_long_per_unit": -0.000012,
        "swap_short_per_unit": -0.000029,
    },
    "GBPUSD": {
        # Broker: 100k GBP lot, spread 0.7 pips, comm GBP 2.50 (~USD 3.18)
        # Swap: -$3.0 long / -$3.5 short per lot per day
        # Both swaps negative (always pay).
        "units_per_contract": 100000,
        "half_spread": 0.000035,
        "commission_per_unit": 0.0000318,
        "commission_pct": 0.0,
        "swap_long_per_unit": -0.00003,
        "swap_short_per_unit": -0.000035,
    },
}
