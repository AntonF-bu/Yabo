"""Feature group 11 – Risk Management (14 features).

Assesses how the trader manages downside: stop-loss discipline, position
sizing consistency, hedging, diversification, and behavioural response to
drawdowns.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import numpy as np
import pandas as pd

from features.utils import (
    compute_cv,
    compute_trend,
    safe_divide,
)

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 5


def _sector_hhi(tickers: pd.Series, market_ctx: Any) -> float | None:
    """Compute Herfindahl-Hirschman Index across sectors from a ticker Series.

    Returns a value in [0, 1] where 1 = completely concentrated.
    """
    if tickers is None or len(tickers) < MIN_DATA_POINTS:
        return None
    sectors = tickers.apply(market_ctx.get_sector)
    counts = sectors.value_counts(normalize=True)
    hhi = float((counts ** 2).sum())
    return hhi


def extract(
    trades_df: pd.DataFrame,
    positions: pd.DataFrame,
    market_ctx: MarketContext,
) -> dict[str, Any]:
    """Return a dict of 14 risk-management features."""

    out: dict[str, Any] = {
        "risk_has_stops": None,
        "risk_avg_stop_distance": None,
        "risk_max_loss_pct": None,
        "risk_max_position_risk": None,
        "risk_per_trade_consistency": None,
        "risk_hedge_ratio": None,
        "risk_sector_diversification": None,
        "risk_trim_winners": None,
        "risk_increase_trend": None,
        "risk_adjusted_return": None,
        "risk_worst_week": None,
        "risk_recovery_after_worst": None,
        "risk_max_leverage": None,
        "risk_evolution": None,
    }

    if trades_df is None or len(trades_df) < MIN_DATA_POINTS:
        return out

    df = trades_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["action_upper"] = df["action"].astype(str).str.upper()
    df["trade_value"] = (df["price"] * df["quantity"]).abs()

    pos = positions
    if pos is not None and len(pos) > 0:
        pos = pos.copy()
        # Ensure numeric columns
        for col in ("return_pct", "pnl_usd", "hold_days"):
            if col in pos.columns:
                pos[col] = pd.to_numeric(pos[col], errors="coerce")

    # ── Closed positions and winners / losers ──────────────────────────────
    closed = (
        pos[(pos["is_open"] == False) & pos["return_pct"].notna()]  # noqa: E712
        if pos is not None and len(pos) > 0
        else pd.DataFrame()
    )
    losers = closed[closed["return_pct"] < 0] if len(closed) > 0 else pd.DataFrame()
    winners = closed[closed["return_pct"] > 0] if len(closed) > 0 else pd.DataFrame()

    # ── 1. risk_has_stops ──────────────────────────────────────────────────
    # Proxy: if the std dev of loss percentages on losers is tight (< 5%),
    # the trader likely uses a consistent stop-loss level.
    if len(losers) >= MIN_DATA_POINTS:
        loss_std = losers["return_pct"].std()
        out["risk_has_stops"] = 1 if (loss_std is not None and loss_std < 5.0) else 0

    # ── 2. risk_avg_stop_distance ──────────────────────────────────────────
    if len(losers) >= MIN_DATA_POINTS:
        out["risk_avg_stop_distance"] = round(
            float(losers["return_pct"].abs().median()), 4,
        )

    # ── 3. risk_max_loss_pct ───────────────────────────────────────────────
    if len(closed) >= MIN_DATA_POINTS:
        out["risk_max_loss_pct"] = round(float(closed["return_pct"].min()), 4)

    # ── 4. risk_max_position_risk ──────────────────────────────────────────
    # largest (position_value * typical_stop) / portfolio_value
    # We approximate portfolio value as the median total daily traded value
    # across all active trading days.
    if len(losers) >= MIN_DATA_POINTS and len(df) >= MIN_DATA_POINTS:
        try:
            median_loss_pct = losers["return_pct"].abs().median() / 100.0
            # Daily total traded value as a rough portfolio proxy
            daily_value = df.groupby(df["date"].dt.date)["trade_value"].sum()
            portfolio_proxy = daily_value.median()
            if portfolio_proxy and portfolio_proxy > 0:
                max_trade_value = df["trade_value"].max()
                risk = max_trade_value * median_loss_pct / portfolio_proxy
                out["risk_max_position_risk"] = round(float(risk), 4)
        except Exception:
            pass

    # ── 5. risk_per_trade_consistency ──────────────────────────────────────
    # CV of dollar risk per trade (trade_value * median_loss_pct)
    if len(losers) >= MIN_DATA_POINTS and len(df) >= MIN_DATA_POINTS:
        median_loss_pct = losers["return_pct"].abs().median() / 100.0
        dollar_risk = df["trade_value"] * median_loss_pct
        cv = compute_cv(dollar_risk)
        if cv is not None:
            out["risk_per_trade_consistency"] = round(cv, 4)

    # ── 6. risk_hedge_ratio ────────────────────────────────────────────────
    # % of total traded value that is in inverse ETFs
    if len(df) >= MIN_DATA_POINTS:
        total_value = df["trade_value"].sum()
        if total_value > 0:
            inverse_mask = df["ticker"].apply(
                lambda t: market_ctx.classify_ticker_type(str(t)) == "inverse_etf"
            )
            inverse_value = df.loc[inverse_mask, "trade_value"].sum()
            out["risk_hedge_ratio"] = round(float(inverse_value / total_value), 4)

    # ── 7. risk_sector_diversification ─────────────────────────────────────
    # 1 - HHI (higher = more diversified)
    if len(df) >= MIN_DATA_POINTS:
        hhi = _sector_hhi(df["ticker"], market_ctx)
        if hhi is not None:
            out["risk_sector_diversification"] = round(1.0 - hhi, 4)

    # ── 8. risk_trim_winners ───────────────────────────────────────────────
    # % of partial closes on winning positions
    if pos is not None and len(pos) > 0:
        winning_pos = pos[pos["is_winner"] == True]  # noqa: E712
        if len(winning_pos) >= MIN_DATA_POINTS:
            partial_wins = winning_pos[winning_pos["is_partial_close"] == True]  # noqa: E712
            out["risk_trim_winners"] = round(
                float(len(partial_wins) / len(winning_pos)), 4,
            )

    # ── 9. risk_increase_trend ─────────────────────────────────────────────
    # Slope of average trade value over time (chronological order)
    if len(df) >= MIN_DATA_POINTS:
        daily_avg_value = (
            df.sort_values("date")
            .groupby(df["date"].dt.date)["trade_value"]
            .mean()
            .sort_index()
        )
        if len(daily_avg_value) >= MIN_DATA_POINTS:
            trend = compute_trend(daily_avg_value.values)
            if trend is not None:
                out["risk_increase_trend"] = round(trend, 4)

    # ── 10. risk_adjusted_return ───────────────────────────────────────────
    # total return / stdev of individual trade returns
    if len(closed) >= MIN_DATA_POINTS:
        total_pnl = closed["pnl_usd"].sum()
        ret_std = closed["return_pct"].std()
        ratio = safe_divide(total_pnl, ret_std)
        if ratio is not None:
            out["risk_adjusted_return"] = round(ratio, 4)

    # ── 11. risk_worst_week ────────────────────────────────────────────────
    # Sum of pnl_usd in the worst rolling 7-calendar-day window
    if len(closed) >= MIN_DATA_POINTS:
        try:
            closed_sorted = closed.copy()
            closed_sorted["close_date"] = pd.to_datetime(closed_sorted["close_date"])
            closed_sorted = closed_sorted.dropna(subset=["close_date", "pnl_usd"])
            if len(closed_sorted) >= MIN_DATA_POINTS:
                daily_pnl = (
                    closed_sorted.groupby(closed_sorted["close_date"].dt.date)["pnl_usd"]
                    .sum()
                    .sort_index()
                )
                daily_pnl.index = pd.to_datetime(daily_pnl.index)
                # Rolling 7-calendar-day sum
                if len(daily_pnl) >= 2:
                    rolling_sum = daily_pnl.rolling("7D", min_periods=1).sum()
                    out["risk_worst_week"] = round(float(rolling_sum.min()), 2)
        except Exception:
            pass

    # ── 12. risk_recovery_after_worst ──────────────────────────────────────
    # Sizing change after worst week vs normal
    if out["risk_worst_week"] is not None and len(df) >= MIN_DATA_POINTS:
        try:
            daily_pnl = (
                df.groupby(df["date"].dt.date)["trade_value"]
                .sum()
                .sort_index()
            )
            daily_pnl.index = pd.to_datetime(daily_pnl.index)

            # Find the end date of the worst week from closed positions
            closed_sorted = closed.copy()
            closed_sorted["close_date"] = pd.to_datetime(closed_sorted["close_date"])
            closed_sorted = closed_sorted.dropna(subset=["close_date", "pnl_usd"])
            pnl_by_day = (
                closed_sorted.groupby(closed_sorted["close_date"].dt.date)["pnl_usd"]
                .sum()
                .sort_index()
            )
            pnl_by_day.index = pd.to_datetime(pnl_by_day.index)
            if len(pnl_by_day) >= 2:
                rolling_pnl = pnl_by_day.rolling("7D", min_periods=1).sum()
                worst_end = rolling_pnl.idxmin()

                # Average trade value in 14 calendar days after worst week end
                recovery_start = worst_end + pd.Timedelta(days=1)
                recovery_end = worst_end + pd.Timedelta(days=14)
                recovery_mask = (df["date"] >= recovery_start) & (df["date"] <= recovery_end)
                recovery_trades = df.loc[recovery_mask]
                overall_avg = df["trade_value"].mean()

                if len(recovery_trades) >= 2 and overall_avg > 0:
                    recovery_avg = recovery_trades["trade_value"].mean()
                    out["risk_recovery_after_worst"] = round(
                        float(recovery_avg / overall_avg), 4,
                    )
        except Exception:
            pass

    # ── 13. risk_max_leverage ──────────────────────────────────────────────
    # Maximum leverage multiplier used (3 for 3x ETFs, 2 for 2x, 1 if none)
    if len(df) >= 1:
        max_lev = 1
        for ticker in df["ticker"].unique():
            lev = market_ctx.get_leverage_factor(str(ticker)) if hasattr(market_ctx, "get_leverage_factor") else 1
            if lev is not None and lev > max_lev:
                max_lev = lev
        out["risk_max_leverage"] = max_lev

    # ── 14. risk_evolution ─────────────────────────────────────────────────
    # Is risk management improving?  Compare average loss % in the first
    # half of closed positions (chronologically) vs the second half.
    # Negative value = losses are getting smaller = improving.
    if len(losers) >= MIN_DATA_POINTS:
        try:
            losers_sorted = losers.copy()
            losers_sorted["close_date"] = pd.to_datetime(losers_sorted["close_date"])
            losers_sorted = losers_sorted.sort_values("close_date")
            n = len(losers_sorted)
            first_half = losers_sorted.iloc[: n // 2]
            second_half = losers_sorted.iloc[n // 2 :]
            if len(first_half) >= 2 and len(second_half) >= 2:
                avg_first = first_half["return_pct"].mean()
                avg_second = second_half["return_pct"].mean()
                # Both are negative; second - first: negative means second half
                # losses are larger in magnitude (worse).  We want
                # avg_loss_second - avg_loss_first where more negative = worse.
                # Since return_pct is negative for losers, a more negative
                # second half means avg_second < avg_first → diff < 0 → worse.
                # We report second - first so that negative = improving
                # (second half losses are smaller in absolute value).
                out["risk_evolution"] = round(float(avg_second - avg_first), 4)
        except Exception:
            pass

    return out
