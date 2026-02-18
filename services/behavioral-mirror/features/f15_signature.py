"""F15 -- Trader signature / fingerprint features (8 features).

Captures idiosyncratic, persistent behavioral patterns that make
each trader's "style" identifiable -- favorite tickers, timing
regularities, portfolio-reset events, and strategy drift.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

from features.utils import (
    compute_cv,
    safe_divide,
)
from features.market_context import MarketContext

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 5


def _sig_favorite_devotion(trades_df: pd.DataFrame) -> float | None:
    """Fraction of all trades that go to the #1 most-traded ticker."""
    if len(trades_df) < MIN_DATA_POINTS:
        return None

    counts = trades_df["ticker"].value_counts()
    if len(counts) == 0:
        return None

    top_count = counts.iloc[0]
    return float(top_count / len(trades_df))


def _sig_recurring_dates(trades_df: pd.DataFrame) -> float | None:
    """1 if any day-of-month has >= 3x the average trade count, 0 otherwise.

    Detects traders who habitually trade on the same calendar day
    (e.g., paycheck day).
    """
    if len(trades_df) < MIN_DATA_POINTS:
        return None

    dates = pd.to_datetime(trades_df["date"], errors="coerce").dropna()
    if len(dates) < MIN_DATA_POINTS:
        return None

    day_of_month = dates.dt.day
    counts = day_of_month.value_counts()
    if len(counts) == 0:
        return None

    avg_count = counts.mean()
    if avg_count <= 0:
        return None

    max_count = counts.max()
    return 1.0 if max_count >= 3.0 * avg_count else 0.0


def _sig_payday_pattern(trades_df: pd.DataFrame) -> float | None:
    """Trade clustering at ~14-day or ~30-day intervals.

    Computes autocorrelation of daily trade counts at lag 14 and lag 30,
    returns the max.  High value suggests pay-cycle-driven trading.
    """
    if len(trades_df) < MIN_DATA_POINTS:
        return None

    dates = pd.to_datetime(trades_df["date"], errors="coerce").dropna()
    if len(dates) < MIN_DATA_POINTS:
        return None

    min_date = dates.min()
    max_date = dates.max()
    if pd.isna(min_date) or pd.isna(max_date):
        return None

    span_days = (max_date - min_date).days
    if span_days < 60:
        # Need at least 60 days of history for meaningful autocorrelation
        return None

    # Build a daily trade count series (including zero-trade days)
    date_range = pd.date_range(start=min_date, end=max_date, freq="D")
    daily_counts = dates.dt.normalize().value_counts().reindex(date_range, fill_value=0)

    if len(daily_counts) < 31:
        return None

    # Compute autocorrelation at lags 14 and 30
    series = daily_counts.astype(float)
    autocorrs = []
    for lag in (14, 30):
        if len(series) <= lag:
            continue
        try:
            ac = series.autocorr(lag=lag)
            if pd.notna(ac):
                autocorrs.append(ac)
        except Exception:
            continue

    if not autocorrs:
        return None

    # Return the max autocorrelation (strongest periodic signal)
    return float(max(autocorrs))


def _sig_seasonal_score(trades_df: pd.DataFrame) -> float | None:
    """Max monthly activity / min monthly activity (across months with trades).

    Higher values indicate strong seasonal preferences.
    """
    if len(trades_df) < MIN_DATA_POINTS:
        return None

    dates = pd.to_datetime(trades_df["date"], errors="coerce").dropna()
    if len(dates) < MIN_DATA_POINTS:
        return None

    months = dates.dt.month
    month_counts = months.value_counts()

    # Need at least 3 months of data for a meaningful ratio
    if len(month_counts) < 3:
        return None

    max_month = month_counts.max()
    min_month = month_counts.min()
    if min_month == 0:
        return None

    return float(max_month / min_month)


def _sig_preferred_hold(positions: pd.DataFrame) -> float | None:
    """Mode of hold duration buckets.

    Buckets:
      0 = day trade (0-1 days)
      1 = swing (2-10 days)
      2 = position (11-60 days)
      3 = investment (61+ days)

    Returns the bucket integer of the most common style.
    """
    valid = positions[positions["hold_days"].notna()].copy()
    if len(valid) < MIN_DATA_POINTS:
        return None

    def _bucket(days: float) -> int:
        d = int(days)
        if d <= 1:
            return 0
        elif d <= 10:
            return 1
        elif d <= 60:
            return 2
        else:
            return 3

    buckets = valid["hold_days"].apply(_bucket)
    counts = buckets.value_counts()
    if len(counts) == 0:
        return None

    return float(counts.index[0])


def _sig_portfolio_reset(
    trades_df: pd.DataFrame,
    positions: pd.DataFrame,
) -> float | None:
    """1 if the trader ever sold 80%+ of open positions in a 7-day window,
    0 otherwise.

    Detects "rage quits" or deliberate portfolio resets.
    """
    if trades_df.empty:
        return None
    sells = trades_df[trades_df["action"].str.upper() == "SELL"].copy()
    if len(sells) < MIN_DATA_POINTS:
        return 0.0

    dates = pd.to_datetime(sells["date"], errors="coerce").dropna()
    if len(dates) < MIN_DATA_POINTS:
        return 0.0

    # Reconstruct rough open-position count over time from positions data
    # For each date, count positions that were open (open_date <= date and
    # (close_date > date or is_open))
    pos = positions.copy()
    pos["open_date"] = pd.to_datetime(pos["open_date"], errors="coerce")
    pos["close_date"] = pd.to_datetime(pos["close_date"], errors="coerce")
    valid_pos = pos.dropna(subset=["open_date"])

    if len(valid_pos) < MIN_DATA_POINTS:
        return None

    sell_dates = sorted(dates.unique())

    for i, check_date in enumerate(sell_dates):
        check_date = pd.Timestamp(check_date)
        window_start = check_date - pd.Timedelta(days=7)

        # Count positions that were open at window_start
        open_at_start = valid_pos[
            (valid_pos["open_date"] <= window_start)
            & (
                (valid_pos["close_date"].isna())
                | (valid_pos["close_date"] > window_start)
            )
        ]
        n_open = len(open_at_start)
        if n_open < 3:
            # Too few positions to be a meaningful reset
            continue

        # Count how many of those were closed within the 7-day window
        closed_in_window = open_at_start[
            (open_at_start["close_date"].notna())
            & (open_at_start["close_date"] >= window_start)
            & (open_at_start["close_date"] <= check_date)
        ]

        if len(closed_in_window) >= 0.8 * n_open:
            return 1.0

    return 0.0


def _sig_strategy_drift(
    trades_df: pd.DataFrame,
    positions: pd.DataFrame,
) -> float | None:
    """Euclidean distance between first-quarter and last-quarter feature
    sub-vectors: (position_sizing_CV, avg_hold_days, win_rate).

    Higher distance = more strategy drift over time.
    """
    # Need enough positions to split into quarters
    closed = positions[
        (positions["return_pct"].notna()) & (positions["hold_days"].notna())
    ].copy()
    sort_col = "open_date" if not closed["open_date"].isna().all() else "close_date"
    closed = closed.dropna(subset=[sort_col]).sort_values(sort_col).reset_index(drop=True)

    if len(closed) < MIN_DATA_POINTS * 4:
        return None

    q_size = len(closed) // 4
    first_q = closed.iloc[:q_size]
    last_q = closed.iloc[-q_size:]

    if len(first_q) < MIN_DATA_POINTS or len(last_q) < MIN_DATA_POINTS:
        return None

    # Feature 1: position sizing CV
    buys = trades_df[trades_df["action"].str.upper() == "BUY"].copy()
    buys["trade_value"] = buys["price"].astype(float) * buys["quantity"].astype(float)
    buys = buys.sort_values("date").reset_index(drop=True)

    buy_q_size = len(buys) // 4
    if buy_q_size < MIN_DATA_POINTS:
        # Fall back: use position shares * avg_cost as sizing proxy
        first_cv = compute_cv(first_q["shares"].astype(float) * first_q["avg_cost"].astype(float))
        last_cv = compute_cv(last_q["shares"].astype(float) * last_q["avg_cost"].astype(float))
    else:
        first_buys = buys.iloc[:buy_q_size]
        last_buys = buys.iloc[-buy_q_size:]
        first_cv = compute_cv(first_buys["trade_value"])
        last_cv = compute_cv(last_buys["trade_value"])

    # Feature 2: avg hold duration
    first_hold = first_q["hold_days"].mean()
    last_hold = last_q["hold_days"].mean()

    # Feature 3: win rate
    first_wr = first_q["is_winner"].mean() if first_q["is_winner"].notna().sum() > 0 else 0.0
    last_wr = last_q["is_winner"].mean() if last_q["is_winner"].notna().sum() > 0 else 0.0

    # Assemble vectors (normalize hold_days to [0,1] range roughly)
    # Max expected hold ~365, CV typically 0-3, win rate 0-1
    hold_scale = 365.0
    cv_scale = 3.0

    v1 = np.array([
        (first_cv or 0.0) / cv_scale,
        first_hold / hold_scale,
        first_wr,
    ])
    v2 = np.array([
        (last_cv or 0.0) / cv_scale,
        last_hold / hold_scale,
        last_wr,
    ])

    dist = float(np.linalg.norm(v2 - v1))
    return dist


def _sig_uniqueness() -> None:
    """Requires multi-trader context to compute how different this trader
    is from the cohort.  Always None for single-trader extraction."""
    return None


# ── Public API ───────────────────────────────────────────────────────────────


def extract(
    trades_df: pd.DataFrame,
    positions: pd.DataFrame,
    market_ctx: MarketContext,
) -> dict[str, Any]:
    """Extract all 8 trader-signature features.

    Features that cannot be computed are returned as None.
    """
    try:
        favorite_devotion = _sig_favorite_devotion(trades_df)
    except Exception:
        logger.exception("Error computing sig_favorite_devotion")
        favorite_devotion = None

    try:
        recurring_dates = _sig_recurring_dates(trades_df)
    except Exception:
        logger.exception("Error computing sig_recurring_dates")
        recurring_dates = None

    try:
        payday_pattern = _sig_payday_pattern(trades_df)
    except Exception:
        logger.exception("Error computing sig_payday_pattern")
        payday_pattern = None

    try:
        seasonal_score = _sig_seasonal_score(trades_df)
    except Exception:
        logger.exception("Error computing sig_seasonal_score")
        seasonal_score = None

    try:
        preferred_hold = _sig_preferred_hold(positions)
    except Exception:
        logger.exception("Error computing sig_preferred_hold")
        preferred_hold = None

    try:
        portfolio_reset = _sig_portfolio_reset(trades_df, positions)
    except Exception:
        logger.exception("Error computing sig_portfolio_reset")
        portfolio_reset = None

    try:
        strategy_drift = _sig_strategy_drift(trades_df, positions)
    except Exception:
        logger.exception("Error computing sig_strategy_drift")
        strategy_drift = None

    return {
        "sig_favorite_devotion": favorite_devotion,
        "sig_recurring_dates": recurring_dates,
        "sig_payday_pattern": payday_pattern,
        "sig_seasonal_score": seasonal_score,
        "sig_preferred_hold": preferred_hold,
        "sig_portfolio_reset": portfolio_reset,
        "sig_strategy_drift": strategy_drift,
        "sig_uniqueness": _sig_uniqueness(),
    }
