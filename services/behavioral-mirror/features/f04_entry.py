"""F04 — Entry behavior features (16 features).

Analyses *how* a trader enters positions: timing relative to technicals,
volume, earnings, sector rotation, and order-type preferences.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from features.utils import compute_cv, safe_divide, compute_trend

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _buy_rows(trades_df: pd.DataFrame) -> pd.DataFrame:
    """Return only BUY rows with valid price and date."""
    if trades_df.empty:
        return trades_df
    mask = trades_df["action"].str.upper() == "BUY"
    buys = trades_df.loc[mask].copy()
    buys = buys.dropna(subset=["price", "date"])
    return buys


def _safe_ratio(count: int, total: int) -> float | None:
    """Return count / total as a float, or None when total < MIN_DATA_POINTS."""
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
    """Extract 16 entry-behaviour features.

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
        Feature name -> float | None.  ``None`` means the feature could not
        be computed (insufficient data or missing market context).
    """

    result: dict[str, Any] = {
        "entry_limit_ratio": None,
        "entry_vs_20d_high": None,
        "entry_vs_52w_range": None,
        "entry_dip_buyer_score": None,
        "entry_breakout_score": None,
        "entry_above_ma_score": None,
        "entry_below_ma_score": None,
        "entry_on_red_days": None,
        "entry_on_green_days": None,
        "entry_volume_relative": None,
        "entry_buildup_days": None,
        "entry_gap_score": None,
        "entry_earnings_proximity": None,
        "entry_pre_earnings": None,
        "entry_post_earnings": None,
        "entry_sector_rotation_speed": None,
    }

    if trades_df is None or trades_df.empty:
        return result

    buys = _buy_rows(trades_df)
    if len(buys) < MIN_DATA_POINTS:
        return result

    n_buys = len(buys)

    # ------------------------------------------------------------------
    # 1. entry_limit_ratio — % of buys that are limit orders
    # ------------------------------------------------------------------
    if "order_type" in buys.columns:
        non_null = buys["order_type"].dropna()
        if len(non_null) >= MIN_DATA_POINTS:
            limit_count = (non_null.str.upper().isin({"LIMIT", "LMT"})).sum()
            result["entry_limit_ratio"] = float(limit_count / len(non_null))
    # else stays None — no order-type column

    # ------------------------------------------------------------------
    # 2. entry_vs_20d_high — avg (entry price / 20-day high)
    # ------------------------------------------------------------------
    ratios_20d: list[float] = []
    for _, row in buys.iterrows():
        high_20d = market_ctx.get_20d_high(row["ticker"], row["date"])
        if high_20d is not None and high_20d > 0:
            ratios_20d.append(float(row["price"]) / high_20d)
    if len(ratios_20d) >= MIN_DATA_POINTS:
        result["entry_vs_20d_high"] = float(np.mean(ratios_20d))

    # ------------------------------------------------------------------
    # 3. entry_vs_52w_range — avg position in 52-week range (0=low, 1=high)
    # ------------------------------------------------------------------
    range_positions: list[float] = []
    for _, row in buys.iterrows():
        rng = market_ctx.get_52w_range(row["ticker"], row["date"])
        if rng is not None:
            lo, hi = rng
            span = hi - lo
            if span > 0:
                range_positions.append((float(row["price"]) - lo) / span)
    if len(range_positions) >= MIN_DATA_POINTS:
        result["entry_vs_52w_range"] = float(np.mean(range_positions))

    # ------------------------------------------------------------------
    # 4. entry_dip_buyer_score — % of buys when stock is down 5%+ from 20d high
    # ------------------------------------------------------------------
    dip_count = 0
    dip_eligible = 0
    for _, row in buys.iterrows():
        high_20d = market_ctx.get_20d_high(row["ticker"], row["date"])
        if high_20d is not None and high_20d > 0:
            dip_eligible += 1
            if float(row["price"]) <= high_20d * 0.95:
                dip_count += 1
    result["entry_dip_buyer_score"] = _safe_ratio(dip_count, dip_eligible)

    # ------------------------------------------------------------------
    # 5. entry_breakout_score — % of buys within 2% of 20-day high
    # ------------------------------------------------------------------
    breakout_count = 0
    breakout_eligible = 0
    for _, row in buys.iterrows():
        high_20d = market_ctx.get_20d_high(row["ticker"], row["date"])
        if high_20d is not None and high_20d > 0:
            breakout_eligible += 1
            if float(row["price"]) >= high_20d * 0.98:
                breakout_count += 1
    result["entry_breakout_score"] = _safe_ratio(breakout_count, breakout_eligible)

    # ------------------------------------------------------------------
    # 6 & 7. entry_above_ma_score / entry_below_ma_score
    # ------------------------------------------------------------------
    above_count = 0
    below_count = 0
    ma_eligible = 0
    for _, row in buys.iterrows():
        ma20 = market_ctx.get_20d_ma(row["ticker"], row["date"])
        if ma20 is not None and ma20 > 0:
            ma_eligible += 1
            if float(row["price"]) >= ma20:
                above_count += 1
            else:
                below_count += 1
    result["entry_above_ma_score"] = _safe_ratio(above_count, ma_eligible)
    result["entry_below_ma_score"] = _safe_ratio(below_count, ma_eligible)

    # ------------------------------------------------------------------
    # 8 & 9. entry_on_red_days / entry_on_green_days
    # ------------------------------------------------------------------
    red_count = 0
    green_count = 0
    day_color_eligible = 0
    for _, row in buys.iterrows():
        daily_ret = market_ctx.get_stock_daily_return(row["ticker"], row["date"])
        if daily_ret is not None:
            day_color_eligible += 1
            if daily_ret < 0:
                red_count += 1
            else:
                green_count += 1
    result["entry_on_red_days"] = _safe_ratio(red_count, day_color_eligible)
    result["entry_on_green_days"] = _safe_ratio(green_count, day_color_eligible)

    # ------------------------------------------------------------------
    # 10. entry_volume_relative — avg relative volume on buy days
    # ------------------------------------------------------------------
    rel_vols: list[float] = []
    for _, row in buys.iterrows():
        rv = market_ctx.get_relative_volume(row["ticker"], row["date"])
        if rv is not None:
            rel_vols.append(rv)
    if len(rel_vols) >= MIN_DATA_POINTS:
        result["entry_volume_relative"] = float(np.mean(rel_vols))

    # ------------------------------------------------------------------
    # 11. entry_buildup_days — for multi-buy positions, avg days first→last buy
    # ------------------------------------------------------------------
    try:
        buys_sorted = buys.sort_values("date")
        grouped = buys_sorted.groupby("ticker")["date"]
        buildup_spans: list[float] = []
        for _ticker, dates in grouped:
            date_vals = pd.to_datetime(dates)
            if len(date_vals) >= 2:
                span = (date_vals.max() - date_vals.min()).days
                if span >= 0:
                    buildup_spans.append(float(span))
        if len(buildup_spans) >= MIN_DATA_POINTS:
            result["entry_buildup_days"] = float(np.mean(buildup_spans))
    except Exception:
        logger.debug("entry_buildup_days computation failed", exc_info=True)

    # ------------------------------------------------------------------
    # 12. entry_gap_score — % of buys after overnight gap > 2%
    # ------------------------------------------------------------------
    gap_count = 0
    gap_eligible = 0
    for _, row in buys.iterrows():
        gap = market_ctx.get_overnight_gap(row["ticker"], row["date"])
        if gap is not None:
            gap_eligible += 1
            if abs(gap) > 0.02:
                gap_count += 1
    result["entry_gap_score"] = _safe_ratio(gap_count, gap_eligible)

    # ------------------------------------------------------------------
    # 13, 14, 15. entry_earnings_proximity / pre / post
    # ------------------------------------------------------------------
    earnings_nearby_count = 0
    pre_earnings_count = 0
    post_earnings_count = 0
    earnings_eligible = 0

    for _, row in buys.iterrows():
        ticker = row["ticker"]
        buy_date = pd.Timestamp(row["date"])

        # Check if earnings are nearby at all (within 5 trading days)
        is_nearby = market_ctx.is_earnings_nearby(ticker, buy_date, window=5)
        earnings_eligible += 1

        if is_nearby:
            earnings_nearby_count += 1

            # Distinguish pre vs post by checking if the volatility spike is
            # before or after the buy date.  We test a tighter window: the
            # spike within [-5, 0] days vs [0, +5] days.
            is_pre = market_ctx.is_earnings_nearby(ticker, buy_date, window=0)
            # If earnings spike is found when looking only at [date, date],
            # we are ON earnings day — count as post (reaction buy).
            # Otherwise check before/after asymmetry.
            is_before = market_ctx.is_earnings_nearby(
                ticker, buy_date - pd.Timedelta(days=3), window=2,
            )
            is_after = market_ctx.is_earnings_nearby(
                ticker, buy_date + pd.Timedelta(days=3), window=2,
            )

            if is_after and not is_before:
                pre_earnings_count += 1   # earnings are AFTER buy → pre-earnings buy
            elif is_before and not is_after:
                post_earnings_count += 1  # earnings were BEFORE buy → post-earnings buy
            else:
                # Ambiguous — split equally or count both
                pre_earnings_count += 0.5
                post_earnings_count += 0.5

    if earnings_eligible >= MIN_DATA_POINTS:
        result["entry_earnings_proximity"] = float(earnings_nearby_count / earnings_eligible)
        result["entry_pre_earnings"] = float(pre_earnings_count / earnings_eligible)
        result["entry_post_earnings"] = float(post_earnings_count / earnings_eligible)

    # ------------------------------------------------------------------
    # 16. entry_sector_rotation_speed — avg days between selling one sector
    #     and buying another
    # ------------------------------------------------------------------
    try:
        all_trades = trades_df.sort_values("date").copy()
        all_trades["_sector"] = all_trades["ticker"].apply(market_ctx.get_sector)
        all_trades["_action_upper"] = all_trades["action"].str.upper()
        all_trades["_date_ts"] = pd.to_datetime(all_trades["date"])

        sells = all_trades[all_trades["_action_upper"] == "SELL"].copy()
        buy_all = all_trades[all_trades["_action_upper"] == "BUY"].copy()

        rotation_gaps: list[float] = []

        for _, sell_row in sells.iterrows():
            sell_sector = sell_row["_sector"]
            sell_date = sell_row["_date_ts"]
            if sell_sector == "unknown":
                continue

            # Find the next buy in a DIFFERENT sector after this sell
            future_buys = buy_all[
                (buy_all["_date_ts"] > sell_date)
                & (buy_all["_sector"] != sell_sector)
                & (buy_all["_sector"] != "unknown")
            ]
            if len(future_buys) > 0:
                next_buy_date = future_buys.iloc[0]["_date_ts"]
                gap_days = (next_buy_date - sell_date).days
                if 0 <= gap_days <= 365:  # cap at 1 year to avoid outliers
                    rotation_gaps.append(float(gap_days))

        if len(rotation_gaps) >= MIN_DATA_POINTS:
            result["entry_sector_rotation_speed"] = float(np.mean(rotation_gaps))
    except Exception:
        logger.debug("entry_sector_rotation_speed computation failed", exc_info=True)

    return result
