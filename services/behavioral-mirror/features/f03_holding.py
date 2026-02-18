"""Holding-period behavioral features (14 features).

Analyzes *how long* a trader holds positions: duration distributions,
disposition effects, round-number exit thresholds, and partial-close
behaviour.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from features.utils import compute_cv, compute_trend, safe_divide

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 5

# Round gain thresholds and tolerance for exit detection
_ROUND_GAIN_THRESHOLDS = [20.0, 50.0, 100.0]  # percent
_ROUND_GAIN_TOLERANCE = 3.0  # percent

# Round loss thresholds and tolerance
_ROUND_LOSS_THRESHOLDS = [-10.0, -15.0, -20.0, -25.0]  # percent
_ROUND_LOSS_TOLERANCE = 2.0  # percent


def _near_threshold(value: float, thresholds: list[float], tolerance: float) -> bool:
    """Return True if value is within tolerance of any threshold."""
    for t in thresholds:
        if abs(value - t) <= tolerance:
            return True
    return False


def extract(trades_df: pd.DataFrame, positions: pd.DataFrame, market_ctx: Any) -> dict:
    """Extract 14 holding-period behavioral features.

    Parameters
    ----------
    trades_df : pd.DataFrame
        Trade history with columns: ticker, action, quantity, price, date, fees.
    positions : pd.DataFrame
        Position history from build_position_history().
    market_ctx : MarketContext
        Market data context (unused by this module).

    Returns
    -------
    dict
        Feature name -> value (or None if not computable).
    """
    result: dict[str, Any] = {
        "holding_median_days": None,
        "holding_avg_days": None,
        "holding_cv": None,
        "holding_pct_day_trades": None,
        "holding_pct_swing": None,
        "holding_pct_position": None,
        "holding_pct_investment": None,
        "holding_shortest_hours": None,
        "holding_longest_days": None,
        "holding_duration_trend": None,
        "holding_disposition_ratio": None,
        "holding_round_gain_exits": None,
        "holding_round_loss_exits": None,
        "holding_partial_close_rate": None,
    }

    if positions is None or len(positions) == 0:
        return result

    pos = positions.copy()

    # ── Work with closed positions that have valid hold_days ────────────

    closed = pos[pos["is_open"] == False].copy()  # noqa: E712

    if len(closed) == 0:
        # Can still compute partial_close_rate from all positions if enough data
        return result

    # Subset with valid hold durations
    has_hold = closed["hold_days"].notna()
    closed_with_hold = closed[has_hold].copy()

    hold_days = closed_with_hold["hold_days"].astype(float)

    # ── Basic duration statistics ───────────────────────────────────────

    if len(hold_days) >= MIN_DATA_POINTS:
        result["holding_median_days"] = round(float(hold_days.median()), 2)
        result["holding_avg_days"] = round(float(hold_days.mean()), 2)
        result["holding_cv"] = compute_cv(hold_days)
        if result["holding_cv"] is not None:
            result["holding_cv"] = round(result["holding_cv"], 4)

        n = len(hold_days)

        # holding_pct_day_trades: held < 1 day (hold_days == 0 means same day)
        day_trades = (hold_days < 1).sum()
        result["holding_pct_day_trades"] = round(float(day_trades / n), 4)

        # holding_pct_swing: 2-10 days
        swing = ((hold_days >= 2) & (hold_days <= 10)).sum()
        result["holding_pct_swing"] = round(float(swing / n), 4)

        # holding_pct_position: 10-60 days (exclusive of swing upper bound)
        position_trade = ((hold_days > 10) & (hold_days <= 60)).sum()
        result["holding_pct_position"] = round(float(position_trade / n), 4)

        # holding_pct_investment: 60+ days
        investment = (hold_days > 60).sum()
        result["holding_pct_investment"] = round(float(investment / n), 4)

        # holding_shortest_hours: fastest round trip (hold_days * 24 proxy)
        min_hold = float(hold_days.min())
        result["holding_shortest_hours"] = round(min_hold * 24.0, 2)

        # holding_longest_days
        result["holding_longest_days"] = round(float(hold_days.max()), 2)

    # ── Duration trend ──────────────────────────────────────────────────
    # Order closed positions by close_date and compute trend of hold durations.

    if len(closed_with_hold) >= MIN_DATA_POINTS:
        ordered = closed_with_hold.sort_values("close_date")
        durations_ordered = ordered["hold_days"].astype(float).values
        result["holding_duration_trend"] = compute_trend(durations_ordered)
        if result["holding_duration_trend"] is not None:
            result["holding_duration_trend"] = round(
                result["holding_duration_trend"], 4
            )

    # ── Disposition ratio ───────────────────────────────────────────────
    # median hold on losers / median hold on winners.
    # > 1.0 means the trader holds losers longer (classic disposition effect).

    winners = closed_with_hold[closed_with_hold["is_winner"] == True]  # noqa: E712
    losers = closed_with_hold[closed_with_hold["is_winner"] == False]  # noqa: E712

    if len(winners) >= MIN_DATA_POINTS and len(losers) >= MIN_DATA_POINTS:
        median_win_hold = float(winners["hold_days"].median())
        median_loss_hold = float(losers["hold_days"].median())
        result["holding_disposition_ratio"] = safe_divide(
            median_loss_hold, median_win_hold
        )
        if result["holding_disposition_ratio"] is not None:
            result["holding_disposition_ratio"] = round(
                result["holding_disposition_ratio"], 4
            )

    # ── Round-number exit detection ─────────────────────────────────────
    # Check what fraction of exits occur near "psychologically round" return levels.

    has_return = closed["return_pct"].notna()
    closed_with_return = closed[has_return].copy()

    if len(closed_with_return) >= MIN_DATA_POINTS:
        returns = closed_with_return["return_pct"].astype(float)

        # Round gain exits (near +20%, +50%, +100%)
        gain_exits = returns[returns > 0]
        if len(gain_exits) >= MIN_DATA_POINTS:
            near_round_gain = sum(
                1
                for r in gain_exits
                if _near_threshold(r, _ROUND_GAIN_THRESHOLDS, _ROUND_GAIN_TOLERANCE)
            )
            result["holding_round_gain_exits"] = round(
                float(near_round_gain / len(gain_exits)), 4
            )

        # Round loss exits (near -10%, -15%, -20%, -25%)
        loss_exits = returns[returns < 0]
        if len(loss_exits) >= MIN_DATA_POINTS:
            near_round_loss = sum(
                1
                for r in loss_exits
                if _near_threshold(r, _ROUND_LOSS_THRESHOLDS, _ROUND_LOSS_TOLERANCE)
            )
            result["holding_round_loss_exits"] = round(
                float(near_round_loss / len(loss_exits)), 4
            )

    # ── Partial close rate ──────────────────────────────────────────────
    # Fraction of closed positions that were partial exits vs full exits.

    if len(closed) >= MIN_DATA_POINTS:
        partial_closes = closed["is_partial_close"].sum()
        result["holding_partial_close_rate"] = round(
            float(partial_closes / len(closed)), 4
        )

    return result
