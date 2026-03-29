"""
Portfolio-level calculations for multi-instrument trading.

Implements:
    - Instrument correlation matrix from returns
    - IDM (Instrument Diversification Multiplier)
    - Equal-weight allocation
    - Portfolio position sizing (Carver formula with IDM)

All values calculated from data, not optimized.
"""

import numpy as np
import pandas as pd


def instrument_correlation_matrix(returns_dict, min_overlap=500):
    """
    Calculate correlation matrix from instrument daily returns.

    Args:
        returns_dict: dict of {name: pd.Series} of daily PnL or pct returns
        min_overlap: minimum number of overlapping days required

    Returns:
        pd.DataFrame correlation matrix (instruments x instruments)
    """
    df = pd.DataFrame(returns_dict)
    # Use pairwise complete observations
    corr = df.corr(min_periods=min_overlap)
    return corr


def calculate_idm(corr_matrix, weights=None):
    """
    Instrument Diversification Multiplier.

    IDM = 1 / sqrt(w^T * C * w)

    With equal weights and N instruments:
        IDM = 1 / sqrt( (1/N^2) * sum(C_ij) )

    Args:
        corr_matrix: pd.DataFrame or np.ndarray (N x N)
        weights: array-like of instrument weights (sum to 1.0).
                 None = equal weights.

    Returns:
        float: IDM value (typically 1.0 - 2.5)
    """
    C = np.array(corr_matrix)
    n = C.shape[0]

    if weights is None:
        weights = np.array([1.0 / n] * n)
    else:
        weights = np.array(weights)

    # Handle NaN in correlation matrix (use 1.0 = conservative)
    C = np.nan_to_num(C, nan=1.0)

    w_corr_w = weights @ C @ weights
    if w_corr_w <= 0:
        return 1.0

    idm = 1.0 / np.sqrt(w_corr_w)

    # Carver caps IDM at 2.5 for safety
    idm = min(idm, 2.5)

    return idm


def portfolio_position(forecast, capital, vol_target_annual, idm,
                       instrument_weight, price_vol, point_value=1.0):
    """
    Carver portfolio position sizing for one instrument.

    Position_i = (forecast / 10) * (Capital * vol_target * IDM * w_i)
                 / (sqrt(256) * price_vol * point_value)

    Args:
        forecast: float or pd.Series, forecast value [-20, +20]
        capital: float, current portfolio equity
        vol_target_annual: float, e.g. 0.12 for 12%
        idm: float, instrument diversification multiplier
        instrument_weight: float, weight of this instrument (e.g. 0.10)
        price_vol: float or pd.Series, daily price volatility
        point_value: float, value per point per contract

    Returns:
        float or pd.Series: position size
    """
    daily_risk = (capital * vol_target_annual * idm * instrument_weight
                  / np.sqrt(256))

    if isinstance(price_vol, pd.Series):
        vol_safe = price_vol.replace(0, np.nan)
    else:
        vol_safe = price_vol if price_vol != 0 else np.nan

    position = (forecast / 10.0) * (daily_risk / (vol_safe * point_value))
    return position


def run_portfolio_backtest(instrument_data, vol_target_annual=0.12,
                           capital=100000, buffer_fraction=0.10,
                           idm=None, costs=None,
                           rates_daily=None, ref_rates=None,
                           carry_gate=None):
    """
    Run a multi-instrument portfolio backtest.

    Each instrument contributes equally (weight = 1/N).
    IDM is pre-calculated or auto-calculated from first pass returns.
    Portfolio equity = capital + sum of all instrument PnLs.

    Args:
        instrument_data: list of dicts, each with:
            - name: str
            - close: pd.Series (daily prices, DatetimeIndex)
            - forecast: pd.Series (forecast values [-20, +20])
            - point_value: float (default 1.0)
        vol_target_annual: float
        capital: float, starting capital
        buffer_fraction: float
        idm: float or None. If None, uses 1.0 for first pass then
             calculates from instrument return correlations.
        costs: dict of {name: cost_dict} or None.
               When provided, transaction costs are deducted from PnL.
        rates_daily: pd.DataFrame of daily interest rates (for time-varying swap).
        ref_rates: dict of reference rates at swap calibration time.
        carry_gate: float or None. When provided, penalises forecasts where
            swap cost exceeds this fraction of daily ATR (e.g. 0.10 = 10%).

    Returns:
        dict with:
            - equity: pd.Series (portfolio equity curve)
            - returns: pd.Series (portfolio daily PnL)
            - instrument_returns: dict of {name: pd.Series}
            - instrument_positions: dict of {name: pd.Series}
            - idm: float (calculated or provided)
            - weights: dict of {name: float}
            - corr_matrix: pd.DataFrame
            - cost_detail: dict (only when costs provided)
    """
    from core.forecast import price_volatility

    n_instruments = len(instrument_data)
    weight = 1.0 / n_instruments

    # Find common date range (union of all dates)
    all_dates = set()
    for inst in instrument_data:
        all_dates.update(inst["close"].index)
    all_dates = sorted(all_dates)
    date_index = pd.DatetimeIndex(all_dates)

    # Two-pass approach:
    # Pass 1: run with IDM=1.0 to get returns for correlation calculation
    # Pass 2: run again with calculated IDM

    if idm is None:
        # Pass 1: IDM = 1.0
        pass1_returns = _run_portfolio_pass(
            instrument_data, date_index, vol_target_annual,
            capital, buffer_fraction, weight, idm=1.0
        )

        # Calculate correlation from percentage returns
        pct_returns_dict = {}
        for name, ret in pass1_returns["instrument_returns"].items():
            # Convert to pct returns relative to capital
            pct = ret / capital  # rough approximation for correlation
            pct_returns_dict[name] = pct

        corr_matrix = instrument_correlation_matrix(pct_returns_dict)
        idm_calc = calculate_idm(corr_matrix)
    else:
        idm_calc = idm
        corr_matrix = None

    # Pass 2 (or only pass): run with actual IDM and optional costs
    results = _run_portfolio_pass(
        instrument_data, date_index, vol_target_annual,
        capital, buffer_fraction, weight, idm=idm_calc, costs=costs,
        rates_daily=rates_daily, ref_rates=ref_rates,
        carry_gate=carry_gate
    )

    # Calculate correlation matrix if not done in pass 1
    if corr_matrix is None:
        pct_returns_dict = {}
        for name, ret in results["instrument_returns"].items():
            pct = ret / capital
            pct_returns_dict[name] = pct
        corr_matrix = instrument_correlation_matrix(pct_returns_dict)

    results["idm"] = idm_calc
    results["weights"] = {inst["name"]: weight for inst in instrument_data}
    results["corr_matrix"] = corr_matrix

    return results


def _run_portfolio_pass(instrument_data, date_index, vol_target_annual,
                        capital, buffer_fraction, weight, idm, costs=None,
                        rates_daily=None, ref_rates=None,
                        carry_gate=None):
    """
    Internal: run one pass of the portfolio backtest.

    Day-by-day loop across all instruments with shared capital.
    When costs dict is provided, deducts spread + commission + swap.
    When rates_daily + ref_rates provided, swap is time-varying.
    When carry_gate is set, forecasts are penalised proportionally
    when swap cost exceeds carry_gate fraction of daily ATR.
    """
    from core.forecast import price_volatility
    from core.costs import calculate_daily_cost, get_swap_scale, carry_gate_penalty
    from config.instruments import INSTRUMENTS

    n_days = len(date_index)

    # Pre-compute volatilities per instrument
    inst_vol = {}
    inst_close = {}
    inst_forecast = {}
    inst_pv = {}
    for inst in instrument_data:
        name = inst["name"]
        close = inst["close"]
        vol = price_volatility(close)
        inst_vol[name] = vol
        inst_close[name] = close
        inst_forecast[name] = inst["forecast"]
        inst_pv[name] = inst.get("point_value", 1.0)

    names = [inst["name"] for inst in instrument_data]

    # Storage
    equity_arr = pd.Series(float(capital), index=date_index)
    portfolio_pnl = pd.Series(0.0, index=date_index)
    inst_positions = {n: pd.Series(0.0, index=date_index) for n in names}
    inst_returns = {n: pd.Series(0.0, index=date_index) for n in names}

    # Cost tracking (populated only when costs provided)
    total_costs = pd.Series(0.0, index=date_index)
    inst_trade_costs = {n: 0.0 for n in names}
    inst_swap_costs = {n: 0.0 for n in names}

    for i in range(1, n_days):
        date = date_index[i]
        prev_date = date_index[i - 1]
        current_capital = equity_arr.iloc[i - 1]

        day_pnl = 0.0

        for name in names:
            close = inst_close[name]
            vol = inst_vol[name]
            forecast = inst_forecast[name]
            pv = inst_pv[name]

            # Check if this instrument has data for today and yesterday
            if date not in close.index or prev_date not in close.index:
                inst_positions[name].iloc[i] = inst_positions[name].iloc[i - 1]
                continue

            vol_today = vol.get(date, np.nan)
            fc_today = forecast.get(date, np.nan)

            if pd.isna(vol_today) or vol_today == 0 or pd.isna(fc_today):
                inst_positions[name].iloc[i] = inst_positions[name].iloc[i - 1]
                continue

            # Time-varying swap scale (shared by carry-gate and costs)
            ss = 1.0
            if costs and name in costs:
                if rates_daily is not None and ref_rates is not None:
                    if name in INSTRUMENTS:
                        ss = get_swap_scale(
                            name, INSTRUMENTS[name], date,
                            rates_daily, ref_rates
                        )

                # Carry-gate: penalise forecast when swap is high vs ATR
                if carry_gate is not None:
                    fc_sign = (1 if fc_today > 0
                               else (-1 if fc_today < 0 else 0))
                    gate_p = carry_gate_penalty(
                        fc_sign, costs[name], vol_today, ss,
                        carry_gate
                    )
                    fc_today *= gate_p

            # Ideal position using portfolio formula
            daily_risk = (current_capital * vol_target_annual * idm
                          * weight / np.sqrt(256))
            ideal = (fc_today / 10.0) * (daily_risk / (vol_today * pv))

            # Buffer
            base_pos = abs(daily_risk / (vol_today * pv))
            buf = buffer_fraction * base_pos

            prev_pos = inst_positions[name].iloc[i - 1]
            if ideal > prev_pos + buf:
                new_pos = ideal
            elif ideal < prev_pos - buf:
                new_pos = ideal
            else:
                new_pos = prev_pos

            inst_positions[name].iloc[i] = new_pos

            # PnL from yesterday's position (gross)
            price_change = close[date] - close[prev_date]
            pnl = prev_pos * price_change * pv

            # Transaction costs
            if costs and name in costs:
                delta = new_pos - prev_pos

                cost_total, cost_trade, cost_swap = calculate_daily_cost(
                    delta, prev_pos, close[date], costs[name],
                    swap_scale=ss
                )
                pnl -= cost_total
                inst_trade_costs[name] += cost_trade
                inst_swap_costs[name] += cost_swap
                total_costs.iloc[i] += cost_total

            inst_returns[name].iloc[i] = pnl
            day_pnl += pnl

        portfolio_pnl.iloc[i] = day_pnl
        equity_arr.iloc[i] = current_capital + day_pnl

    return {
        "equity": equity_arr,
        "returns": portfolio_pnl,
        "instrument_returns": inst_returns,
        "instrument_positions": inst_positions,
        "total_costs": total_costs,
        "inst_trade_costs": inst_trade_costs,
        "inst_swap_costs": inst_swap_costs,
    }
