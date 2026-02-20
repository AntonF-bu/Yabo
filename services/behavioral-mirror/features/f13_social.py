"""F13 -- Social / meme-stock influence features (10 features).

Measures how much a trader's behavior is driven by social media hype,
meme-stock trends, and retail crowd dynamics.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from features.utils import safe_divide

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 5

# Module-level reference set during extract(); avoids threading every helper.
_ctx: Any = None


def _meme_mask_trades(trades_df: pd.DataFrame) -> pd.Series:
    """Boolean mask for trades in meme stocks."""
    return trades_df["ticker"].apply(_ctx.is_meme_stock)


def _meme_mask_positions(positions: pd.DataFrame) -> pd.Series:
    """Boolean mask for positions in meme stocks."""
    return positions["ticker"].apply(_ctx.is_meme_stock)


def _social_meme_rate(trades_df: pd.DataFrame) -> float | None:
    """Percentage of trades (by count) in meme stock list."""
    if len(trades_df) < MIN_DATA_POINTS:
        return None
    meme_count = _meme_mask_trades(trades_df).sum()
    return float(meme_count / len(trades_df))


def _social_trend_entry_speed(trades_df: pd.DataFrame) -> float | None:
    """For meme stocks, avg days from start of data to first entry.

    A proxy for early-vs-late adoption: lower values mean the trader
    entered meme stocks early relative to their own trading history.
    """
    meme_trades = trades_df[_meme_mask_trades(trades_df)].copy()
    if len(meme_trades) < MIN_DATA_POINTS:
        return None

    dates = pd.to_datetime(trades_df["date"])
    data_start = dates.min()
    if pd.isna(data_start):
        return None

    meme_dates = pd.to_datetime(meme_trades["date"])
    # For each meme ticker, find the first trade date
    first_entries = meme_trades.groupby("ticker").apply(
        lambda g: pd.to_datetime(g["date"]).min()
    )
    if len(first_entries) == 0:
        return None

    days_to_entry = [(entry - data_start).days for entry in first_entries if pd.notna(entry)]
    if len(days_to_entry) == 0:
        return None

    return float(np.mean(days_to_entry))


def _social_trend_exit_timing(positions: pd.DataFrame) -> float | None:
    """For meme positions, avg return_pct normalized to [-1, 1].

    Positive means sold at profit; negative means bagholding / loss.
    """
    if positions.empty or "return_pct" not in positions.columns:
        return None
    meme_pos = positions[_meme_mask_positions(positions)].copy()
    if meme_pos.empty:
        return None
    # Only consider closed positions with valid return_pct
    meme_closed = meme_pos[meme_pos["return_pct"].notna()]
    if len(meme_closed) < MIN_DATA_POINTS:
        return None

    avg_ret = meme_closed["return_pct"].mean()
    # Normalize: clip to [-100, 100] then scale to [-1, 1]
    normalized = float(np.clip(avg_ret, -100.0, 100.0) / 100.0)
    return normalized


def _social_earnings_reaction_speed() -> None:
    """Cannot determine hours-level reaction speed from daily data."""
    return None


def _social_news_driven_estimate(
    trades_df: pd.DataFrame,
    market_ctx: Any,
) -> float | None:
    """Percentage of trades on high relative volume days (> 2x average).

    Uses market_ctx.get_relative_volume as a proxy for news-driven activity.
    """
    if len(trades_df) < MIN_DATA_POINTS:
        return None
    is_loaded = getattr(market_ctx, "is_loaded", True)
    if not is_loaded:
        return None

    high_vol_count = 0
    checked_count = 0

    for _, row in trades_df.iterrows():
        ticker = row["ticker"]
        date = row["date"]
        try:
            rel_vol = market_ctx.get_relative_volume(ticker, date)
        except Exception:
            rel_vol = None

        if rel_vol is not None:
            checked_count += 1
            if rel_vol > 2.0:
                high_vol_count += 1

    if checked_count < MIN_DATA_POINTS:
        return None

    return float(high_vol_count / checked_count)


def _social_copycat(trades_df: pd.DataFrame) -> float | None:
    """Jaccard similarity of the trader's ticker set to top retail stocks."""
    if len(trades_df) < MIN_DATA_POINTS:
        return None

    trader_tickers = set(trades_df["ticker"].str.upper().unique())
    if not trader_tickers:
        return None

    top_retail = _ctx.get_top_retail_stocks() if hasattr(_ctx, "get_top_retail_stocks") else set()
    intersection = trader_tickers & top_retail
    union = trader_tickers | top_retail
    if not union:
        return None

    return float(len(intersection) / len(union))


def _social_contrarian_independence(meme_rate: float | None) -> float | None:
    """1 - meme_rate. Higher value = more independent from crowd."""
    if meme_rate is None:
        return None
    return float(1.0 - meme_rate)


def _social_hype_position() -> None:
    """Cannot determine early/middle/late positioning in hype runs
    without broader multi-trader market participation data."""
    return None


def _social_bagholding(positions: pd.DataFrame) -> float | None:
    """Percentage of meme stock positions still held (is_open) 30+ days
    after open_date."""
    if positions.empty:
        return None
    meme_pos = positions[_meme_mask_positions(positions)].copy()
    if len(meme_pos) < MIN_DATA_POINTS:
        return None

    open_meme = meme_pos[meme_pos["is_open"] == True].copy()  # noqa: E712
    if len(open_meme) == 0:
        # No open meme positions: 0% bagholding
        return 0.0

    # Compute days held for open positions (from open_date to now)
    today = pd.Timestamp.now().normalize()
    bagholding_count = 0
    valid_count = 0

    for _, row in open_meme.iterrows():
        open_date = pd.to_datetime(row["open_date"], errors="coerce")
        if pd.isna(open_date):
            continue
        valid_count += 1
        days_held = (today - open_date).days
        if days_held >= 30:
            bagholding_count += 1

    total_meme = len(meme_pos)
    if total_meme == 0:
        return None

    return float(bagholding_count / total_meme)


def _social_influence_trend(trades_df: pd.DataFrame) -> float | None:
    """Slope of meme stock trade percentage over time.

    Compares the meme-trade ratio in the first half of the trading history
    to the second half.  Positive = increasing meme influence over time.
    """
    if len(trades_df) < MIN_DATA_POINTS * 2:
        return None

    df = trades_df.sort_values("date").reset_index(drop=True)
    mid = len(df) // 2

    first_half = df.iloc[:mid]
    second_half = df.iloc[mid:]

    if len(first_half) == 0 or len(second_half) == 0:
        return None

    first_meme_rate = _meme_mask_trades(first_half).sum() / len(first_half)
    second_meme_rate = _meme_mask_trades(second_half).sum() / len(second_half)

    return float(second_meme_rate - first_meme_rate)


# ── Public API ───────────────────────────────────────────────────────────────


def extract(
    trades_df: pd.DataFrame,
    positions: pd.DataFrame,
    market_ctx: Any,
) -> dict[str, Any]:
    """Extract all 10 social/meme-influence features.

    Features that cannot be computed are returned as None.
    """
    global _ctx
    _ctx = market_ctx

    try:
        meme_rate = _social_meme_rate(trades_df)
    except Exception:
        logger.exception("Error computing social_meme_rate")
        meme_rate = None

    try:
        trend_entry = _social_trend_entry_speed(trades_df)
    except Exception:
        logger.exception("Error computing social_trend_entry_speed")
        trend_entry = None

    try:
        trend_exit = _social_trend_exit_timing(positions)
    except Exception:
        logger.exception("Error computing social_trend_exit_timing")
        trend_exit = None

    try:
        news_driven = _social_news_driven_estimate(trades_df, market_ctx)
    except Exception:
        logger.exception("Error computing social_news_driven_estimate")
        news_driven = None

    try:
        copycat = _social_copycat(trades_df)
    except Exception:
        logger.exception("Error computing social_copycat")
        copycat = None

    try:
        contrarian = _social_contrarian_independence(meme_rate)
    except Exception:
        logger.exception("Error computing social_contrarian_independence")
        contrarian = None

    try:
        bagholding = _social_bagholding(positions)
    except Exception:
        logger.exception("Error computing social_bagholding")
        bagholding = None

    try:
        influence_trend = _social_influence_trend(trades_df)
    except Exception:
        logger.exception("Error computing social_influence_trend")
        influence_trend = None

    return {
        "social_meme_rate": meme_rate,
        "social_trend_entry_speed": trend_entry,
        "social_trend_exit_timing": trend_exit,
        "social_earnings_reaction_speed": _social_earnings_reaction_speed(),
        "social_news_driven_estimate": news_driven,
        "social_copycat": copycat,
        "social_contrarian_independence": contrarian,
        "social_hype_position": _social_hype_position(),
        "social_bagholding": bagholding,
        "social_influence_trend": influence_trend,
    }
