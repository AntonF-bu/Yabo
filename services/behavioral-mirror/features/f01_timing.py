"""Timing-related behavioral features (18 features).

Analyzes *when* a trader executes trades: time of day, day of week,
seasonal patterns, activity frequency, and gaps between trading days.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

from features.utils import compute_cv, compute_trend, safe_divide

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 5


def _has_intraday_time(dates: pd.Series) -> bool:
    """Return True if the date series contains meaningful intraday time info.

    CSV-sourced data often has dates at midnight (00:00:00).  We consider
    time information present only when a meaningful fraction of timestamps
    have non-midnight times within market hours.
    """
    if not hasattr(dates.dtype, "tz") and not pd.api.types.is_datetime64_any_dtype(dates):
        return False
    times = dates.dt.time
    non_midnight = times[times != pd.Timestamp("00:00:00").time()]
    # Need at least MIN_DATA_POINTS non-midnight timestamps and > 20% of data
    return len(non_midnight) >= MIN_DATA_POINTS and len(non_midnight) / len(times) > 0.20


def _shannon_entropy(counts: np.ndarray) -> float:
    """Compute Shannon entropy of a discrete distribution (in nats)."""
    total = counts.sum()
    if total == 0:
        return 0.0
    probs = counts / total
    probs = probs[probs > 0]
    return float(-np.sum(probs * np.log(probs)))


def _is_quarter_end_period(date: pd.Timestamp) -> bool:
    """Return True if date falls in the last 2 weeks of a calendar quarter."""
    month = date.month
    day = date.day
    # Quarter-end months: 3, 6, 9, 12
    if month in (3, 6, 9, 12):
        # Last 2 weeks = day >= 17 (roughly)
        return day >= 17
    return False


def extract(trades_df: pd.DataFrame, positions: pd.DataFrame, market_ctx: Any) -> dict:
    """Extract 18 timing-related behavioral features.

    Parameters
    ----------
    trades_df : pd.DataFrame
        Trade history with columns: ticker, action, quantity, price, date, fees.
    positions : pd.DataFrame
        Position history from build_position_history().
    market_ctx : MarketContext
        Market data context (unused by this module but kept for interface consistency).

    Returns
    -------
    dict
        Feature name -> value (or None if not computable).
    """
    result: dict[str, Any] = {
        "timing_time_of_day_mode": None,
        "timing_time_of_day_entropy": None,
        "timing_morning_score": None,
        "timing_lunch_score": None,
        "timing_close_score": None,
        "timing_day_of_week_mode": None,
        "timing_monday_ratio": None,
        "timing_friday_ratio": None,
        "timing_avg_trades_per_active_day": None,
        "timing_trading_days_per_month": None,
        "timing_longest_inactive_streak": None,
        "timing_avg_inactive_gap": None,
        "timing_gap_volatility": None,
        "timing_frequency_trend": None,
        "timing_first_week_bias": None,
        "timing_end_of_quarter_spike": None,
        "timing_december_shift": None,
        "timing_january_shift": None,
    }

    if trades_df is None or len(trades_df) < MIN_DATA_POINTS:
        return result

    df = trades_df.copy()

    # Ensure date column is datetime
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        try:
            df["date"] = pd.to_datetime(df["date"])
        except Exception:
            logger.warning("Could not parse date column; returning all None.")
            return result

    df = df.sort_values("date").reset_index(drop=True)
    dates = df["date"]

    # ── Time-of-day features (require intraday timestamps) ──────────────

    has_time = _has_intraday_time(dates)
    if has_time:
        hours = dates.dt.hour
        # Only consider market-hours trades (hour 9-16 inclusive)
        market_hours = hours[(hours >= 9) & (hours <= 16)]

        if len(market_hours) >= MIN_DATA_POINTS:
            # timing_time_of_day_mode
            hour_counts = Counter(market_hours)
            result["timing_time_of_day_mode"] = int(hour_counts.most_common(1)[0][0])

            # timing_time_of_day_entropy
            # Build histogram for hours 9-16
            bins = np.zeros(8, dtype=float)  # hours 9,10,11,12,13,14,15,16
            for h, c in hour_counts.items():
                idx = int(h) - 9
                if 0 <= idx < 8:
                    bins[idx] = c
            result["timing_time_of_day_entropy"] = round(_shannon_entropy(bins), 4)

            # For session scoring we use fractional hours (hour + minute/60)
            frac_hours = dates.dt.hour + dates.dt.minute / 60.0

            # timing_morning_score: 9:30-10:30
            morning = ((frac_hours >= 9.5) & (frac_hours <= 10.5)).sum()
            result["timing_morning_score"] = round(float(morning / len(dates)), 4)

            # timing_lunch_score: 11:30-13:00
            lunch = ((frac_hours >= 11.5) & (frac_hours <= 13.0)).sum()
            result["timing_lunch_score"] = round(float(lunch / len(dates)), 4)

            # timing_close_score: 14:30-16:00
            close_session = ((frac_hours >= 14.5) & (frac_hours <= 16.0)).sum()
            result["timing_close_score"] = round(float(close_session / len(dates)), 4)

    # ── Day-of-week features ────────────────────────────────────────────

    dow = dates.dt.dayofweek  # 0=Monday, 6=Sunday
    # Filter to weekdays only (just in case)
    weekday_dow = dow[dow <= 4]

    if len(weekday_dow) >= MIN_DATA_POINTS:
        dow_counts = Counter(weekday_dow)
        result["timing_day_of_week_mode"] = int(dow_counts.most_common(1)[0][0])

        # Average daily count (across all weekdays that had trades)
        avg_daily_count = len(weekday_dow) / max(len(dow_counts), 1)

        # timing_monday_ratio
        mon_count = dow_counts.get(0, 0)
        result["timing_monday_ratio"] = round(
            safe_divide(float(mon_count), avg_daily_count) or 0.0, 4
        ) if avg_daily_count > 0 else None

        # timing_friday_ratio
        fri_count = dow_counts.get(4, 0)
        result["timing_friday_ratio"] = round(
            safe_divide(float(fri_count), avg_daily_count) or 0.0, 4
        ) if avg_daily_count > 0 else None

    # ── Activity frequency features ─────────────────────────────────────

    # Unique trading days
    trading_dates = dates.dt.normalize().unique()
    trading_dates = pd.DatetimeIndex(trading_dates).sort_values()

    if len(trading_dates) >= MIN_DATA_POINTS:
        # timing_avg_trades_per_active_day
        trades_per_day = df.groupby(dates.dt.normalize()).size()
        result["timing_avg_trades_per_active_day"] = round(
            float(trades_per_day.mean()), 4
        )

        # timing_trading_days_per_month
        # Group trading dates by year-month, count unique days per month
        months = pd.Series(trading_dates).dt.to_period("M")
        days_per_month = months.value_counts().sort_index()
        if len(days_per_month) >= 2:
            result["timing_trading_days_per_month"] = round(
                float(days_per_month.mean()), 4
            )

    # ── Gap / streak features ───────────────────────────────────────────

    if len(trading_dates) >= 2:
        # Gaps between consecutive trading days (in calendar days)
        gaps = np.diff(trading_dates.values).astype("timedelta64[D]").astype(float)
        gaps = gaps[gaps > 0]  # remove any duplicate-day artefacts

        if len(gaps) >= MIN_DATA_POINTS:
            # timing_longest_inactive_streak
            result["timing_longest_inactive_streak"] = int(gaps.max())

            # timing_avg_inactive_gap
            result["timing_avg_inactive_gap"] = round(float(gaps.mean()), 4)

            # timing_gap_volatility (CV of gaps)
            result["timing_gap_volatility"] = compute_cv(gaps)
            if result["timing_gap_volatility"] is not None:
                result["timing_gap_volatility"] = round(
                    result["timing_gap_volatility"], 4
                )

    # ── Frequency trend ─────────────────────────────────────────────────

    # Trades per month over time
    monthly_counts = df.groupby(dates.dt.to_period("M")).size()
    if len(monthly_counts) >= MIN_DATA_POINTS:
        result["timing_frequency_trend"] = compute_trend(monthly_counts.values)
        if result["timing_frequency_trend"] is not None:
            result["timing_frequency_trend"] = round(
                result["timing_frequency_trend"], 4
            )

    # ── Calendar-position features ──────────────────────────────────────

    if len(df) >= MIN_DATA_POINTS:
        # timing_first_week_bias: % of trades in days 1-7 of month
        day_of_month = dates.dt.day
        first_week_count = (day_of_month <= 7).sum()
        result["timing_first_week_bias"] = round(
            float(first_week_count / len(df)), 4
        )

    # ── Quarter-end spike ───────────────────────────────────────────────

    if len(df) >= MIN_DATA_POINTS:
        is_qend = dates.apply(_is_quarter_end_period)
        qend_count = is_qend.sum()
        non_qend_count = len(df) - qend_count

        # Expected ratio if uniform: last ~2 weeks of quarter months is
        # roughly 14/90 ~ 15.6% of all calendar days.
        # We compare actual ratio to the non-quarter-end baseline.
        if non_qend_count > 0 and qend_count > 0:
            # Proportion of calendar days that are quarter-end: ~4*14/365 = 0.153
            qend_frac = 4 * 14 / 365.0
            expected_qend = len(df) * qend_frac
            result["timing_end_of_quarter_spike"] = round(
                float(qend_count / expected_qend), 4
            ) if expected_qend > 0 else None
        elif qend_count == 0:
            result["timing_end_of_quarter_spike"] = 0.0

    # ── Monthly seasonality (December & January shifts) ─────────────────

    monthly_counts_all = df.groupby(dates.dt.month).size()
    total_months_spanned = max(
        1,
        (dates.max().year - dates.min().year) * 12
        + (dates.max().month - dates.min().month) + 1,
    )

    if len(monthly_counts_all) >= 3 and total_months_spanned >= 3:
        # Normalize counts by number of times each month appears in the data
        # to get average trades per occurrence of each month.
        month_year_counts = df.groupby([dates.dt.year, dates.dt.month]).size()
        month_occurrences = month_year_counts.groupby(level=1).count()
        month_avg = month_year_counts.groupby(level=1).mean()

        overall_avg = month_avg.mean() if len(month_avg) > 0 else None

        if overall_avg and overall_avg > 0:
            # timing_december_shift
            if 12 in month_avg.index and month_occurrences.get(12, 0) >= 1:
                result["timing_december_shift"] = round(
                    float(month_avg[12] / overall_avg), 4
                )

            # timing_january_shift
            if 1 in month_avg.index and month_occurrences.get(1, 0) >= 1:
                result["timing_january_shift"] = round(
                    float(month_avg[1] / overall_avg), 4
                )

    return result
