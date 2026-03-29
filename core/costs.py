"""
Transaction cost model for Carver systematic trading.

Models three cost components per instrument per day:
    - Spread: half-spread on each position change (one-way)
    - Commission: fixed or percentage-based per unit traded
    - Swap: daily overnight financing on held positions

All costs expressed per system unit in the instrument's price currency.
Cost function returns positive values for costs, negative for income.
"""

# Swap accrues 365 calendar days but we only iterate 252 trading days.
# Multiply daily swap by this factor to account for weekends/holidays.
SWAP_CALENDAR_MULTIPLIER = 365.0 / 252.0


def calculate_daily_cost(delta_pos, held_pos, price, costs):
    """
    Calculate total daily cost for one instrument.

    Args:
        delta_pos: position change today (new_pos - prev_pos)
        held_pos: position held overnight (prev_pos, charged swap)
        price: current instrument price (for pct-based commissions)
        costs: dict with half_spread, commission_per_unit, commission_pct,
               swap_long_per_unit, swap_short_per_unit

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
    if abs_held > 0.001:
        if held_pos > 0:
            swap_rate = costs["swap_long_per_unit"]
        else:
            swap_rate = costs["swap_short_per_unit"]

        # swap_rate < 0 => pay => positive cost
        # swap_rate > 0 => receive => negative cost (income)
        swap_cost = abs_held * (-swap_rate) * SWAP_CALENDAR_MULTIPLIER

    total_cost = trade_cost + swap_cost
    return total_cost, trade_cost, swap_cost
