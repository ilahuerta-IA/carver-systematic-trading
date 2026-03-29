"""
Transaction cost model for Carver systematic trading.

Models three cost components per instrument per day:
    - Spread: half-spread on each position change (one-way)
    - Commission: fixed or percentage-based per unit traded
    - Swap: daily overnight financing on held positions

All costs expressed per system unit in the instrument's price currency.
Cost function returns positive values for costs, negative for income.

Swap rates are time-varying: the INSTRUMENT_COSTS swap values are
calibrated at a reference funding rate. Each day the swap is scaled by
(current_funding_rate / reference_rate) so swaps were near-zero during
ZIRP and proportionally higher when rates rise.
"""

import numpy as np

# Swap accrues 365 calendar days but we only iterate 252 trading days.
# Multiply daily swap by this factor to account for weekends/holidays.
SWAP_CALENDAR_MULTIPLIER = 365.0 / 252.0


def calculate_daily_cost(delta_pos, held_pos, price, costs,
                         swap_scale=1.0):
    """
    Calculate total daily cost for one instrument.

    Args:
        delta_pos: position change today (new_pos - prev_pos)
        held_pos: position held overnight (prev_pos, charged swap)
        price: current instrument price (for pct-based commissions)
        costs: dict with half_spread, commission_per_unit, commission_pct,
               swap_long_per_unit, swap_short_per_unit
        swap_scale: multiplier for swap (rate_today / rate_ref).
                    1.0 = use swap as-is (current rates).
                    0.0 = no swap (ZIRP).

    Returns:
        (total_cost, trade_cost, swap_cost)
        Positive = cost (subtracted from PnL).
        Negative = income (e.g. favorable swap carry).
    """
    abs_delta = abs(delta_pos)
    abs_held = abs(held_pos)

    # --- Trade cost (spread + commission), only on position changes ---
    trade_cost = 0.0
    if abs_delta > 0.001:
        spread_cost = abs_delta * costs["half_spread"]

        if costs.get("commission_pct", 0) > 0:
            commission = abs_delta * costs["commission_pct"] * price
        else:
            commission = abs_delta * costs["commission_per_unit"]

        trade_cost = spread_cost + commission

    # --- Swap cost (daily financing on overnight position) ---
    swap_cost = 0.0
    if abs_held > 0.001 and swap_scale != 0.0:
        if held_pos > 0:
            swap_rate = costs["swap_long_per_unit"]
        else:
            swap_rate = costs["swap_short_per_unit"]

        # swap_rate < 0 => pay => positive cost
        # swap_rate > 0 => receive => negative cost (income)
        swap_cost = (abs_held * (-swap_rate) * swap_scale
                     * SWAP_CALENDAR_MULTIPLIER)

    total_cost = trade_cost + swap_cost
    return total_cost, trade_cost, swap_cost


def get_swap_scale(instrument_name, instrument_cfg, date, rates_daily,
                   ref_rates):
    """
    Calculate swap scaling factor for a given date.

    For equity/commodity: swap ~ funding_rate.
        scale = funding_rate_today / funding_rate_ref

    For FX: swap ~ abs(base_rate - quote_rate).
        scale = abs(base_today - quote_today) / abs(base_ref - quote_ref)

    Args:
        instrument_name: str
        instrument_cfg: dict from INSTRUMENTS
        date: pd.Timestamp
        rates_daily: pd.DataFrame with columns USD, EUR, JPY, AUD, GBP
        ref_rates: dict of {currency: rate_at_calibration_time}

    Returns:
        float: scaling factor (0.0 to ~3.0 typically)
    """
    asset_class = instrument_cfg["asset_class"]

    if asset_class in ("equity", "commodity"):
        ccy = instrument_cfg["funding_currency"]
        rate_today = _get_rate(rates_daily, date, ccy)
        rate_ref = ref_rates.get(ccy, 1.0)
        if rate_ref == 0:
            return 0.0
        return max(rate_today / rate_ref, 0.0)

    elif asset_class == "fx":
        base_ccy = instrument_cfg["base_currency"]
        quote_ccy = instrument_cfg["quote_currency"]
        base_today = _get_rate(rates_daily, date, base_ccy)
        quote_today = _get_rate(rates_daily, date, quote_ccy)
        base_ref = ref_rates.get(base_ccy, 1.0)
        quote_ref = ref_rates.get(quote_ccy, 1.0)

        diff_today = abs(base_today - quote_today)
        diff_ref = abs(base_ref - quote_ref)

        if diff_ref < 0.01:
            return 0.0
        return max(diff_today / diff_ref, 0.0)

    return 1.0


def carry_gate_penalty(forecast_sign, costs, vol_today, swap_scale=1.0,
                       threshold=0.10):
    """
    Carry-gate penalty: reduce forecast when swap cost is high vs ATR.

    penalty = max(0, 1 - swap_ratio / threshold)
    where swap_ratio = daily_swap_cost / daily_volatility

    Only penalises adverse swap (cost). Favourable swap (income)
    receives no penalty (returns 1.0).

    Args:
        forecast_sign: +1 long, -1 short, 0 flat
        costs: dict with swap_long_per_unit, swap_short_per_unit
        vol_today: daily price volatility (ATR proxy, same units as swap)
        swap_scale: time-varying rate multiplier
        threshold: swap/ATR ratio at which forecast is fully blocked

    Returns:
        float: penalty factor in [0.0, 1.0]
    """
    if forecast_sign == 0 or vol_today <= 0 or threshold <= 0:
        return 1.0

    if forecast_sign > 0:
        swap_rate = costs.get("swap_long_per_unit", 0.0)
    else:
        swap_rate = costs.get("swap_short_per_unit", 0.0)

    # Positive swap_rate = income (favourable), no penalty
    if swap_rate >= 0:
        return 1.0

    # Negative swap_rate = cost (adverse)
    swap_daily = abs(swap_rate) * swap_scale * SWAP_CALENDAR_MULTIPLIER
    swap_ratio = swap_daily / vol_today

    return max(0.0, 1.0 - swap_ratio / threshold)


def build_reference_rates(rates_daily):
    """
    Extract the reference rates (last available date in data).

    These correspond to the swap values in INSTRUMENT_COSTS.

    Returns:
        dict of {currency: rate_pct} e.g. {"USD": 3.64, "EUR": 2.0, ...}
    """
    last_row = rates_daily.iloc[-1]
    return {col: last_row[col] for col in rates_daily.columns}


def _get_rate(rates_daily, date, currency):
    """Safely get rate for a currency on a date."""
    if currency not in rates_daily.columns:
        return 0.0
    if date in rates_daily.index:
        val = rates_daily.loc[date, currency]
        if np.isnan(val):
            return 0.0
        return val
    # Find nearest prior date
    mask = rates_daily.index <= date
    if mask.any():
        val = rates_daily.loc[rates_daily.index[mask][-1], currency]
        return 0.0 if np.isnan(val) else val
    return 0.0
