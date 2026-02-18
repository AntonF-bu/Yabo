"""F05 — Exit behavior features (16 features).

Analyses *how* a trader exits positions: profit-taking discipline, stop-loss
consistency, panic selling, partial vs full exits, and market-timing at exit.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from features.utils import compute_cv, safe_divide, classify_ticker_type, get_sector, compute_trend
from features.market_context import MarketContext

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sell_rows(trades_df: pd.DataFrame) -> pd.DataFrame:
    """Return only SELL rows with valid price and date."""
    if trades_df.empty:
        return trades_df
    mask = trades_df["action"].str.upper() == "SELL"
    sells = trades_df.loc[mask].copy()
    sells = sells.dropna(subset=["price", "date"])
    return sells


def _closed_positions(positions: pd.DataFrame) -> pd.DataFrame:
    """Return positions that are fully or partially closed (have return_pct)."""
    if positions.empty:
        return positions
    closed = positions[positions["is_open"] == False].copy()  # noqa: E712
    closed = closed.dropna(subset=["return_pct"])
    return closed


def _safe_ratio(count: int | float, total: int) -> float | None:
    """Return count / total, or None when total < MIN_DATA_POINTS."""
    if total < MIN_DATA_POINTS:
        return None
    return float(count / total)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract(
    trades_df: pd.DataFrame,
    positions: pd.DataFrame,
    market_ctx: MarketContext,
) -> dict[str, Any]:
    """Extract 16 exit-behaviour features.

    Parameters
    ----------
    trades_df : DataFrame
        Raw trade log with columns: ticker, action, quantity, price, date, fees.
    positions : DataFrame
        Position-level history from ``build_position_history``.
    market_ctx : MarketContext
        Pre-loaded market data helper.

    Returns
    -------
    dict
        Feature name -> float | None.
    """

    result: dict[str, Any] = {
        "exit_limit_ratio": None,
        "exit_avg_gain_pct": None,
        "exit_avg_loss_pct": None,
        "exit_profit_target_cluster": None,
        "exit_stop_loss_cluster": None,
        "exit_stop_tightness": None,
        "exit_trailing_stop_score": None,
        "exit_at_high_of_day": None,
        "exit_panic_score": None,
        "exit_take_profit_discipline": None,
        "exit_time_based": None,
        "exit_partial_ratio": None,
        "exit_full_ratio": None,
        "exit_into_strength": None,
        "exit_into_weakness": None,
        "exit_after_earnings": None,
    }

    if trades_df is None or trades_df.empty:
        return result
    if positions is None or positions.empty:
        return result

    sells = _sell_rows(trades_df)
    closed = _closed_positions(positions)

    if len(sells) < MIN_DATA_POINTS and len(closed) < MIN_DATA_POINTS:
        return result

    n_sells = len(sells)
    n_closed = len(closed)

    # Separate winners and losers from closed positions
    winners = closed[closed["is_winner"] == True] if n_closed > 0 else pd.DataFrame()  # noqa: E712
    losers = closed[closed["is_winner"] == False] if n_closed > 0 else pd.DataFrame()  # noqa: E712

    # ------------------------------------------------------------------
    # 1. exit_limit_ratio — % of sells that are limit orders
    # ------------------------------------------------------------------
    if "order_type" in sells.columns and n_sells >= MIN_DATA_POINTS:
        non_null = sells["order_type"].dropna()
        if len(non_null) >= MIN_DATA_POINTS:
            limit_count = (non_null.str.upper().isin({"LIMIT", "LMT"})).sum()
            result["exit_limit_ratio"] = float(limit_count / len(non_null))
    # else stays None

    # ------------------------------------------------------------------
    # 2. exit_avg_gain_pct — mean return on winning closes
    # ------------------------------------------------------------------
    if len(winners) >= MIN_DATA_POINTS:
        result["exit_avg_gain_pct"] = float(winners["return_pct"].mean())

    # ------------------------------------------------------------------
    # 3. exit_avg_loss_pct — mean return on losing closes (negative number)
    # ------------------------------------------------------------------
    if len(losers) >= MIN_DATA_POINTS:
        result["exit_avg_loss_pct"] = float(losers["return_pct"].mean())

    # ------------------------------------------------------------------
    # 4. exit_profit_target_cluster — std dev of gain % for winners
    #    Low value = consistent profit target
    # ------------------------------------------------------------------
    if len(winners) >= MIN_DATA_POINTS:
        result["exit_profit_target_cluster"] = float(winners["return_pct"].std(ddof=1))

    # ------------------------------------------------------------------
    # 5. exit_stop_loss_cluster — std dev of loss % for losers
    #    Low value = consistent stop loss
    # ------------------------------------------------------------------
    if len(losers) >= MIN_DATA_POINTS:
        result["exit_stop_loss_cluster"] = float(losers["return_pct"].std(ddof=1))

    # ------------------------------------------------------------------
    # 6. exit_stop_tightness — median loss % on losing trades
    # ------------------------------------------------------------------
    if len(losers) >= MIN_DATA_POINTS:
        result["exit_stop_tightness"] = float(losers["return_pct"].median())

    # ------------------------------------------------------------------
    # 7. exit_trailing_stop_score — % of winners where exit is 5-15% below
    #    max unrealized gain.  Use return_pct as proxy: if the exit gain
    #    is moderate (5-30%) we assume a trailing stop could have been in play
    #    when the exit is 5-15% below a hypothetical max (approx 1.5x exit).
    # ------------------------------------------------------------------
    if len(winners) >= MIN_DATA_POINTS:
        trailing_count = 0
        for _, row in winners.iterrows():
            ret = row["return_pct"]
            if ret is None or np.isnan(ret):
                continue
            # Estimate max unrealized gain as ~1.5x the exit return_pct
            est_max = ret * 1.5
            if est_max <= 0:
                continue
            drawdown_from_max = (est_max - ret) / est_max
            if 0.05 <= drawdown_from_max <= 0.15:
                trailing_count += 1
        result["exit_trailing_stop_score"] = _safe_ratio(trailing_count, len(winners))

    # ------------------------------------------------------------------
    # 8. exit_at_high_of_day — % of sells in top 20% of day's range
    # ------------------------------------------------------------------
    high_of_day_count = 0
    high_of_day_eligible = 0
    for _, row in sells.iterrows():
        ohlcv = market_ctx.get_ohlcv_at_date(row["ticker"], row["date"])
        if ohlcv is None:
            continue
        day_high = ohlcv["high"]
        day_low = ohlcv["low"]
        day_range = day_high - day_low
        if day_range <= 0:
            continue
        high_of_day_eligible += 1
        sell_price = float(row["price"])
        # Check if sell price is in the top 20% of the day's range
        threshold = day_low + day_range * 0.80
        if sell_price >= threshold:
            high_of_day_count += 1
    result["exit_at_high_of_day"] = _safe_ratio(high_of_day_count, high_of_day_eligible)

    # ------------------------------------------------------------------
    # 9. exit_panic_score — % of sells on days stock drops 3%+
    # ------------------------------------------------------------------
    panic_count = 0
    panic_eligible = 0
    for _, row in sells.iterrows():
        daily_ret = market_ctx.get_stock_daily_return(row["ticker"], row["date"])
        if daily_ret is None:
            continue
        panic_eligible += 1
        if daily_ret <= -0.03:
            panic_count += 1
    result["exit_panic_score"] = _safe_ratio(panic_count, panic_eligible)

    # ------------------------------------------------------------------
    # 10. exit_take_profit_discipline — consistency of gain% on winners
    #     Defined as 1 / (1 + std_dev) so higher = more consistent
    # ------------------------------------------------------------------
    if len(winners) >= MIN_DATA_POINTS:
        std_gain = float(winners["return_pct"].std(ddof=1))
        result["exit_take_profit_discipline"] = float(1.0 / (1.0 + std_gain))

    # ------------------------------------------------------------------
    # 11. exit_time_based — % of exits not explained by price target or stop
    #     Heuristic: exits where return_pct is within -5% to +5% (neither
    #     a clear profit target hit nor a stop loss trigger).
    # ------------------------------------------------------------------
    if n_closed >= MIN_DATA_POINTS:
        time_based_count = 0
        for _, row in closed.iterrows():
            ret = row["return_pct"]
            if ret is not None and not np.isnan(ret):
                if -5.0 <= ret <= 5.0:
                    time_based_count += 1
        result["exit_time_based"] = float(time_based_count / n_closed)

    # ------------------------------------------------------------------
    # 12. exit_partial_ratio — % of sells that reduce but don't close
    # ------------------------------------------------------------------
    if n_closed >= MIN_DATA_POINTS:
        partial_count = int(closed["is_partial_close"].sum()) if "is_partial_close" in closed.columns else 0
        result["exit_partial_ratio"] = float(partial_count / n_closed)

    # ------------------------------------------------------------------
    # 13. exit_full_ratio — % of sells that close entire position
    # ------------------------------------------------------------------
    if n_closed >= MIN_DATA_POINTS:
        partial_count = int(closed["is_partial_close"].sum()) if "is_partial_close" in closed.columns else 0
        full_count = n_closed - partial_count
        result["exit_full_ratio"] = float(full_count / n_closed)

    # ------------------------------------------------------------------
    # 14. exit_into_strength — % of sells on green stock days
    # ------------------------------------------------------------------
    strength_count = 0
    strength_eligible = 0
    for _, row in sells.iterrows():
        daily_ret = market_ctx.get_stock_daily_return(row["ticker"], row["date"])
        if daily_ret is None:
            continue
        strength_eligible += 1
        if daily_ret >= 0:
            strength_count += 1
    result["exit_into_strength"] = _safe_ratio(strength_count, strength_eligible)

    # ------------------------------------------------------------------
    # 15. exit_into_weakness — % of sells on red stock days
    # ------------------------------------------------------------------
    if strength_eligible >= MIN_DATA_POINTS:
        weakness_count = strength_eligible - strength_count
        result["exit_into_weakness"] = float(weakness_count / strength_eligible)

    # ------------------------------------------------------------------
    # 16. exit_after_earnings — % of sells within 5 days of likely earnings
    # ------------------------------------------------------------------
    earnings_exit_count = 0
    earnings_exit_eligible = 0
    for _, row in sells.iterrows():
        ticker = row["ticker"]
        sell_date = pd.Timestamp(row["date"])
        earnings_exit_eligible += 1
        if market_ctx.is_earnings_nearby(ticker, sell_date, window=5):
            earnings_exit_count += 1
    result["exit_after_earnings"] = _safe_ratio(earnings_exit_count, earnings_exit_eligible)

    return result
