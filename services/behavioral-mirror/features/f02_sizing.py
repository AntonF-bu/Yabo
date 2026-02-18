"""Position-sizing behavioral features (16 features).

Analyzes *how much* a trader puts into each trade: absolute and relative
sizes, round-number biases, DCA patterns, conviction scaling, and cash
redeployment cadence.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from features.utils import (
    compute_cv,
    compute_trend,
    estimate_portfolio_value,
    safe_divide,
)

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 5

# Share counts considered "round numbers"
_ROUND_LOTS = {10, 25, 50, 100, 200, 500}


def _is_round_lot(qty: float) -> bool:
    """Return True if the share quantity is a recognised round number."""
    # Accept exact matches and integer equivalents (e.g. 100.0)
    if qty != qty:  # NaN guard
        return False
    int_qty = int(round(qty))
    if abs(qty - int_qty) > 1e-6:
        return False
    return int_qty in _ROUND_LOTS


def _is_fractional(qty: float) -> bool:
    """Return True if the quantity has a meaningful fractional component."""
    if qty != qty:  # NaN guard
        return False
    return abs(qty - round(qty)) > 1e-4


def extract(trades_df: pd.DataFrame, positions: pd.DataFrame, market_ctx: Any) -> dict:
    """Extract 16 sizing-related behavioral features.

    Parameters
    ----------
    trades_df : pd.DataFrame
        Trade history with columns: ticker, action, quantity, price, date, fees.
    positions : pd.DataFrame
        Position history from build_position_history().
    market_ctx : MarketContext
        Market data context.

    Returns
    -------
    dict
        Feature name -> value (or None if not computable).
    """
    result: dict[str, Any] = {
        "sizing_avg_position_pct": None,
        "sizing_median_usd": None,
        "sizing_cv": None,
        "sizing_max_pct": None,
        "sizing_min_usd": None,
        "sizing_round_number_bias": None,
        "sizing_fractional_usage": None,
        "sizing_trend": None,
        "sizing_after_wins": None,
        "sizing_after_losses": None,
        "sizing_largest_relative": None,
        "sizing_dca_score": None,
        "sizing_conviction_ratio": None,
        "sizing_new_ticker_ratio": None,
        "sizing_cash_redeployment_days": None,
        "sizing_peak_exposure_pct": None,
    }

    if trades_df is None or len(trades_df) < MIN_DATA_POINTS:
        return result

    df = trades_df.copy()

    # Ensure date is datetime
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        try:
            df["date"] = pd.to_datetime(df["date"])
        except Exception:
            logger.warning("Could not parse date column; returning all None.")
            return result

    df = df.sort_values("date").reset_index(drop=True)

    # Pre-compute trade dollar values
    df["trade_value"] = (df["price"] * df["quantity"]).abs()
    trade_values = df["trade_value"].dropna()
    trade_values = trade_values[trade_values > 0]

    if len(trade_values) < MIN_DATA_POINTS:
        return result

    # ── Portfolio value estimation ──────────────────────────────────────

    try:
        portfolio_series = estimate_portfolio_value(df)
    except Exception:
        portfolio_series = pd.Series(dtype=float)

    # Use median portfolio value as representative (avoids early/late extremes)
    portfolio_val = float(portfolio_series.median()) if len(portfolio_series) > 0 else None
    if portfolio_val is not None and portfolio_val <= 0:
        portfolio_val = None

    # ── Basic size statistics ───────────────────────────────────────────

    # sizing_median_usd
    result["sizing_median_usd"] = round(float(trade_values.median()), 2)

    # sizing_min_usd
    result["sizing_min_usd"] = round(float(trade_values.min()), 2)

    # sizing_cv
    result["sizing_cv"] = compute_cv(trade_values)
    if result["sizing_cv"] is not None:
        result["sizing_cv"] = round(result["sizing_cv"], 4)

    # sizing_avg_position_pct
    if portfolio_val is not None:
        avg_val = float(trade_values.mean())
        result["sizing_avg_position_pct"] = round(
            safe_divide(avg_val, portfolio_val) or 0.0, 4
        )

    # sizing_max_pct
    if portfolio_val is not None:
        max_val = float(trade_values.max())
        result["sizing_max_pct"] = round(
            safe_divide(max_val, portfolio_val) or 0.0, 4
        )

    # sizing_largest_relative
    median_val = float(trade_values.median())
    if median_val > 0:
        result["sizing_largest_relative"] = round(
            float(trade_values.max() / median_val), 4
        )

    # ── Round-number / fractional biases ────────────────────────────────

    quantities = df["quantity"].dropna()
    if len(quantities) >= MIN_DATA_POINTS:
        round_count = sum(1 for q in quantities if _is_round_lot(q))
        result["sizing_round_number_bias"] = round(
            float(round_count / len(quantities)), 4
        )

        frac_count = sum(1 for q in quantities if _is_fractional(q))
        result["sizing_fractional_usage"] = round(
            float(frac_count / len(quantities)), 4
        )

    # ── Size trend over time ────────────────────────────────────────────

    if len(trade_values) >= MIN_DATA_POINTS:
        result["sizing_trend"] = compute_trend(trade_values.values)
        if result["sizing_trend"] is not None:
            result["sizing_trend"] = round(result["sizing_trend"], 4)

    # ── Sizing after wins / losses ──────────────────────────────────────
    # Look at closed positions.  After a close, find the *next* trade and
    # compare its size to the overall average.

    if positions is not None and len(positions) > 0:
        closed = positions[
            (positions["is_open"] == False)  # noqa: E712
            & positions["return_pct"].notna()
            & positions["close_date"].notna()
        ].copy()

        if len(closed) >= MIN_DATA_POINTS:
            overall_avg = float(trade_values.mean())
            sizes_after_win: list[float] = []
            sizes_after_loss: list[float] = []

            for _, pos in closed.iterrows():
                close_dt = pd.Timestamp(pos["close_date"])
                is_win = pos["is_winner"]
                # Find the next trade after this close
                later_trades = df[df["date"] > close_dt]
                if len(later_trades) == 0:
                    continue
                next_trade = later_trades.iloc[0]
                next_value = float(next_trade["trade_value"])
                if next_value <= 0:
                    continue

                if is_win is True:
                    sizes_after_win.append(next_value)
                elif is_win is False:
                    sizes_after_loss.append(next_value)

            if len(sizes_after_win) >= MIN_DATA_POINTS and overall_avg > 0:
                result["sizing_after_wins"] = round(
                    float(np.mean(sizes_after_win) / overall_avg), 4
                )

            if len(sizes_after_loss) >= MIN_DATA_POINTS and overall_avg > 0:
                result["sizing_after_losses"] = round(
                    float(np.mean(sizes_after_loss) / overall_avg), 4
                )

    # ── DCA score ───────────────────────────────────────────────────────
    # For tickers with multiple BUY trades, compute CV of buy amounts.
    # Low CV => consistent dollar-cost-averaging behaviour.

    buys = df[df["action"].str.upper() == "BUY"].copy()
    if len(buys) >= MIN_DATA_POINTS:
        ticker_buy_groups = buys.groupby("ticker")["trade_value"]
        dca_cvs: list[float] = []
        for ticker, group in ticker_buy_groups:
            if len(group) >= 3:  # need at least 3 buys for meaningful CV
                cv = compute_cv(group)
                if cv is not None:
                    dca_cvs.append(cv)

        if len(dca_cvs) >= 2:
            # Average CV across multi-buy tickers (lower = more DCA-like)
            result["sizing_dca_score"] = round(float(np.mean(dca_cvs)), 4)

    # ── Conviction ratio ────────────────────────────────────────────────
    # For tickers bought more than once: max buy value / min buy value.

    if len(buys) >= MIN_DATA_POINTS:
        conviction_ratios: list[float] = []
        for ticker, group in buys.groupby("ticker")["trade_value"]:
            if len(group) >= 2:
                mn = group.min()
                if mn > 0:
                    conviction_ratios.append(float(group.max() / mn))

        if len(conviction_ratios) >= MIN_DATA_POINTS:
            result["sizing_conviction_ratio"] = round(
                float(np.median(conviction_ratios)), 4
            )

    # ── New-ticker ratio ────────────────────────────────────────────────
    # Average size on the first buy of a ticker vs overall average.

    if len(buys) >= MIN_DATA_POINTS:
        overall_avg = float(trade_values.mean())
        first_buy_values: list[float] = []
        seen_tickers: set[str] = set()

        for _, row in buys.iterrows():
            ticker = row["ticker"]
            if ticker not in seen_tickers:
                seen_tickers.add(ticker)
                first_buy_values.append(float(row["trade_value"]))

        if len(first_buy_values) >= MIN_DATA_POINTS and overall_avg > 0:
            result["sizing_new_ticker_ratio"] = round(
                float(np.mean(first_buy_values) / overall_avg), 4
            )

    # ── Cash redeployment days ──────────────────────────────────────────
    # Median days between a SELL and the next BUY.

    sells = df[df["action"].str.upper() == "SELL"].copy()
    buys_sorted = buys.sort_values("date")
    if len(sells) >= MIN_DATA_POINTS and len(buys_sorted) > 0:
        redeploy_gaps: list[float] = []
        buy_dates = buys_sorted["date"].values

        for _, sell_row in sells.iterrows():
            sell_dt = sell_row["date"]
            # Find the first buy after this sell
            later_buys = buy_dates[buy_dates > sell_dt]
            if len(later_buys) > 0:
                gap_days = (
                    pd.Timestamp(later_buys[0]) - pd.Timestamp(sell_dt)
                ).days
                if gap_days >= 0:
                    redeploy_gaps.append(float(gap_days))

        if len(redeploy_gaps) >= MIN_DATA_POINTS:
            result["sizing_cash_redeployment_days"] = round(
                float(np.median(redeploy_gaps)), 2
            )

    # ── Peak exposure percentage ────────────────────────────────────────
    # Estimate maximum percentage of account "at risk" simultaneously
    # by finding the peak total open-position value relative to portfolio.

    if portfolio_val is not None and portfolio_val > 0 and len(portfolio_series) > 0:
        try:
            max_exposure_pct = float(portfolio_series.max() / portfolio_val)
            result["sizing_peak_exposure_pct"] = round(max_exposure_pct, 4)
        except Exception:
            pass

    return result
