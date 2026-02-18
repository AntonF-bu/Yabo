"""F14 -- Learning / skill improvement features (10 features).

Compares the first half of a trader's history to the second half to
measure whether they are adapting, improving, or repeating mistakes.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from features.utils import (
    compute_cv,
    classify_ticker_type,
    safe_divide,
)
from features.market_context import MarketContext

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 5


def _split_by_date(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a DataFrame into first-half and second-half by date."""
    sorted_df = df.sort_values("date" if "date" in df.columns else "open_date").copy()
    mid = len(sorted_df) // 2
    return sorted_df.iloc[:mid], sorted_df.iloc[mid:]


def _split_positions_by_date(
    positions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split positions into first-half and second-half by open_date
    (falling back to close_date for positions with missing open_date)."""
    pos = positions.copy()
    # Use open_date as the primary sort key, fall back to close_date
    sort_col = "open_date"
    if pos[sort_col].isna().all():
        sort_col = "close_date"
    pos = pos.dropna(subset=[sort_col]).sort_values(sort_col).reset_index(drop=True)
    mid = len(pos) // 2
    return pos.iloc[:mid], pos.iloc[mid:]


def _learning_win_rate_trend(positions: pd.DataFrame) -> float | None:
    """Win rate improvement: second-half win rate minus first-half win rate.

    Positive means improving.
    """
    closed = positions[positions["is_winner"].notna()].copy()
    if len(closed) < MIN_DATA_POINTS * 2:
        return None

    first, second = _split_positions_by_date(closed)
    if len(first) < MIN_DATA_POINTS or len(second) < MIN_DATA_POINTS:
        return None

    first_wr = first["is_winner"].mean()
    second_wr = second["is_winner"].mean()
    return float(second_wr - first_wr)


def _learning_return_trend(positions: pd.DataFrame) -> float | None:
    """Average return improvement: second-half avg return_pct minus first-half."""
    closed = positions[positions["return_pct"].notna()].copy()
    if len(closed) < MIN_DATA_POINTS * 2:
        return None

    first, second = _split_positions_by_date(closed)
    if len(first) < MIN_DATA_POINTS or len(second) < MIN_DATA_POINTS:
        return None

    return float(second["return_pct"].mean() - first["return_pct"].mean())


def _learning_risk_trend(positions: pd.DataFrame) -> float | None:
    """Average loss size change: second-half avg loss minus first-half avg loss.

    Negative means the trader is making smaller losses (improving).
    Loss values are already negative, so a *less negative* second-half
    loss means the difference is positive -- but we want the raw change
    in absolute loss magnitude.  We use absolute values so that a
    negative result always means improvement.
    """
    closed = positions[positions["return_pct"].notna()].copy()
    losers = closed[closed["return_pct"] < 0].copy()
    if len(losers) < MIN_DATA_POINTS * 2:
        return None

    first, second = _split_positions_by_date(losers)
    if len(first) < MIN_DATA_POINTS or len(second) < MIN_DATA_POINTS:
        return None

    # Use absolute values: bigger abs = worse
    first_avg_loss = first["return_pct"].abs().mean()
    second_avg_loss = second["return_pct"].abs().mean()
    # Negative means losses got smaller (improvement)
    return float(second_avg_loss - first_avg_loss)


def _learning_hold_optimization(positions: pd.DataFrame) -> float | None:
    """Hold-period CV change: second-half CV minus first-half CV.

    Negative means the trader is becoming more consistent with hold durations.
    """
    closed = positions[positions["hold_days"].notna()].copy()
    if len(closed) < MIN_DATA_POINTS * 2:
        return None

    first, second = _split_positions_by_date(closed)
    if len(first) < MIN_DATA_POINTS or len(second) < MIN_DATA_POINTS:
        return None

    cv_first = compute_cv(first["hold_days"])
    cv_second = compute_cv(second["hold_days"])
    if cv_first is None or cv_second is None:
        return None

    return float(cv_second - cv_first)


def _learning_mistake_repetition(
    trades_df: pd.DataFrame,
    positions: pd.DataFrame,
) -> float | None:
    """Percentage of losing tickers that are re-bought and lose again.

    Measures whether the trader repeats mistakes on the same ticker.
    """
    closed = positions[
        (positions["return_pct"].notna()) & (positions["is_open"] == False)  # noqa: E712
    ].copy()
    if len(closed) < MIN_DATA_POINTS:
        return None

    # Sort by date to establish chronological order
    sort_col = "close_date" if "close_date" in closed.columns else "open_date"
    closed = closed.dropna(subset=[sort_col]).sort_values(sort_col).reset_index(drop=True)

    # Track tickers that have already lost
    tickers_with_prior_loss: set[str] = set()
    rebought_losers = 0
    rebought_and_lost_again = 0

    # Group positions chronologically per ticker
    for ticker in closed["ticker"].unique():
        ticker_pos = closed[closed["ticker"] == ticker].reset_index(drop=True)
        had_loss = False
        for _, pos in ticker_pos.iterrows():
            is_loss = pos["return_pct"] < 0
            if had_loss:
                # This is a re-entry after a loss
                rebought_losers += 1
                if is_loss:
                    rebought_and_lost_again += 1
            if is_loss:
                had_loss = True

    if rebought_losers < MIN_DATA_POINTS:
        return None

    return float(rebought_and_lost_again / rebought_losers)


def _learning_sizing_improvement(trades_df: pd.DataFrame) -> float | None:
    """Sizing CV change: second-half minus first-half.

    Negative means more systematic / consistent sizing.
    """
    buys = trades_df[trades_df["action"].str.upper() == "BUY"].copy()
    if len(buys) < MIN_DATA_POINTS * 2:
        return None
    buys = buys.copy()
    buys["trade_value"] = buys["price"].astype(float) * buys["quantity"].astype(float)

    first, second = _split_by_date(buys)
    if len(first) < MIN_DATA_POINTS or len(second) < MIN_DATA_POINTS:
        return None

    cv_first = compute_cv(first["trade_value"])
    cv_second = compute_cv(second["trade_value"])
    if cv_first is None or cv_second is None:
        return None

    return float(cv_second - cv_first)


def _learning_new_strategy(trades_df: pd.DataFrame) -> float | None:
    """Change in instrument mix: ETF% in second half minus ETF% in first half.

    Positive means the trader is adding more ETFs (diversification tools).
    """
    if len(trades_df) < MIN_DATA_POINTS * 2:
        return None

    df = trades_df.copy()
    df["is_etf"] = df["ticker"].apply(
        lambda t: classify_ticker_type(t) == "etf"
    )

    first, second = _split_by_date(df)
    if len(first) < MIN_DATA_POINTS or len(second) < MIN_DATA_POINTS:
        return None

    first_etf_pct = first["is_etf"].mean()
    second_etf_pct = second["is_etf"].mean()
    return float(second_etf_pct - first_etf_pct)


def _learning_recovery_improvement() -> None:
    """Cannot compute without per-half drawdown reconstruction from
    continuous portfolio value series."""
    return None


def _learning_loss_cutting(positions: pd.DataFrame) -> float | None:
    """Change in average loss hold duration: second-half minus first-half.

    Negative means the trader is cutting losses faster (improvement).
    """
    closed = positions[
        (positions["return_pct"].notna()) & (positions["hold_days"].notna())
    ].copy()
    losers = closed[closed["return_pct"] < 0].copy()
    if len(losers) < MIN_DATA_POINTS * 2:
        return None

    first, second = _split_positions_by_date(losers)
    if len(first) < MIN_DATA_POINTS or len(second) < MIN_DATA_POINTS:
        return None

    return float(second["hold_days"].mean() - first["hold_days"].mean())


def _learning_skill_trajectory(
    win_rate_trend: float | None,
    return_trend: float | None,
    risk_trend: float | None,
    hold_optimization: float | None,
    sizing_improvement: float | None,
) -> float | None:
    """Composite learning score: mean of normalized sub-features.

    Components (sign-corrected so positive = improving):
      +win_rate_trend, +return_trend, -risk_trend,
      -hold_optimization, -sizing_improvement

    Divides by 5 and clips to [-1, 1].
    """
    components = []
    if win_rate_trend is not None:
        components.append(win_rate_trend)
    if return_trend is not None:
        # Normalize large returns: scale down percentage points
        components.append(return_trend / 100.0 if abs(return_trend) > 1 else return_trend)
    if risk_trend is not None:
        # Negative risk_trend = improvement, so negate for composite
        val = -risk_trend
        components.append(val / 100.0 if abs(val) > 1 else val)
    if hold_optimization is not None:
        # Negative hold_optimization = improvement, so negate
        components.append(-hold_optimization)
    if sizing_improvement is not None:
        # Negative sizing_improvement = improvement, so negate
        components.append(-sizing_improvement)

    if len(components) == 0:
        return None

    raw = float(np.mean(components))
    return float(np.clip(raw, -1.0, 1.0))


# ── Public API ───────────────────────────────────────────────────────────────


def extract(
    trades_df: pd.DataFrame,
    positions: pd.DataFrame,
    market_ctx: MarketContext,
) -> dict[str, Any]:
    """Extract all 10 learning / skill-improvement features.

    Features that cannot be computed are returned as None.
    """
    try:
        win_rate_trend = _learning_win_rate_trend(positions)
    except Exception:
        logger.exception("Error computing learning_win_rate_trend")
        win_rate_trend = None

    try:
        return_trend = _learning_return_trend(positions)
    except Exception:
        logger.exception("Error computing learning_return_trend")
        return_trend = None

    try:
        risk_trend = _learning_risk_trend(positions)
    except Exception:
        logger.exception("Error computing learning_risk_trend")
        risk_trend = None

    try:
        hold_optimization = _learning_hold_optimization(positions)
    except Exception:
        logger.exception("Error computing learning_hold_optimization")
        hold_optimization = None

    try:
        mistake_repetition = _learning_mistake_repetition(trades_df, positions)
    except Exception:
        logger.exception("Error computing learning_mistake_repetition")
        mistake_repetition = None

    try:
        sizing_improvement = _learning_sizing_improvement(trades_df)
    except Exception:
        logger.exception("Error computing learning_sizing_improvement")
        sizing_improvement = None

    try:
        new_strategy = _learning_new_strategy(trades_df)
    except Exception:
        logger.exception("Error computing learning_new_strategy")
        new_strategy = None

    try:
        loss_cutting = _learning_loss_cutting(positions)
    except Exception:
        logger.exception("Error computing learning_loss_cutting")
        loss_cutting = None

    try:
        skill_trajectory = _learning_skill_trajectory(
            win_rate_trend,
            return_trend,
            risk_trend,
            hold_optimization,
            sizing_improvement,
        )
    except Exception:
        logger.exception("Error computing learning_skill_trajectory")
        skill_trajectory = None

    return {
        "learning_win_rate_trend": win_rate_trend,
        "learning_return_trend": return_trend,
        "learning_risk_trend": risk_trend,
        "learning_hold_optimization": hold_optimization,
        "learning_mistake_repetition": mistake_repetition,
        "learning_sizing_improvement": sizing_improvement,
        "learning_new_strategy": new_strategy,
        "learning_recovery_improvement": _learning_recovery_improvement(),
        "learning_loss_cutting": loss_cutting,
        "learning_skill_trajectory": skill_trajectory,
    }
