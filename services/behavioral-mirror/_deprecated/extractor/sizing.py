"""Position sizing analysis: size consistency, post-loss changes, conviction detection."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _estimate_portfolio_value(
    trades_df: pd.DataFrame,
    cash_flow_metadata: dict[str, Any] | None = None,
) -> float:
    """Estimate actual portfolio capital from trade data and cash flows.

    This avoids the $100K default that produces wrong position sizing for
    small portfolios. Uses three strategies in order of accuracy:

    1. Cash flow metadata (deposits from Trading212): actual deposited capital
    2. Cumulative trade analysis: walk trades to find min capital needed
    3. Fallback: sum of all buy-side dollar amounts / 2 (rough estimate)

    Returns estimated starting capital.
    """
    # Strategy 1: Use actual deposit data if available
    if cash_flow_metadata and cash_flow_metadata.get("total_deposited", 0) > 0:
        total_deposited = cash_flow_metadata["total_deposited"]
        logger.info("Portfolio estimate from deposits: $%.0f", total_deposited)
        return total_deposited

    # Strategy 2: Walk trades to find minimum capital required
    # Start with 0 cash, track how negative it goes = minimum capital needed
    cash = 0.0
    min_cash = 0.0
    peak_invested = 0.0
    current_invested = 0.0

    for _, row in trades_df.iterrows():
        action = str(row["action"]).upper()
        qty = float(row["quantity"])
        price = float(row["price"])
        trade_value = qty * price

        if action == "BUY":
            cash -= trade_value
            current_invested += trade_value
        elif action == "SELL":
            cash += trade_value
            current_invested = max(0, current_invested - trade_value)

        min_cash = min(min_cash, cash)
        peak_invested = max(peak_invested, current_invested)

    # The most negative cash point is the minimum capital needed
    estimated = abs(min_cash)

    if estimated > 0:
        # Add 10% buffer for fees and cash reserves
        estimated *= 1.1
        logger.info("Portfolio estimate from trade flow: $%.0f (min cash needed: $%.0f)",
                     estimated, abs(min_cash))
        return estimated

    # Strategy 3: Fallback — use total buy volume as rough upper bound
    buys = trades_df[trades_df["action"].str.upper() == "BUY"]
    total_buy_value = sum(float(r["quantity"]) * float(r["price"]) for _, r in buys.iterrows())

    if total_buy_value > 0:
        # Divide by 2 as rough estimate (assumes ~50% capital turnover)
        estimated = total_buy_value / 2
        logger.info("Portfolio estimate from buy volume: $%.0f (total buys: $%.0f)",
                     estimated, total_buy_value)
        return max(estimated, 100.0)

    return 100_000.0  # Last resort


def reconstruct_portfolio(
    trades_df: pd.DataFrame,
    initial_cash: float = 100_000.0,
    cash_flow_metadata: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Reconstruct portfolio value over time from trade sequence.

    If cash_flow_metadata is available, applies deposits/withdrawals at their
    actual dates for accurate portfolio value tracking.

    Returns DataFrame with columns: date, cash, invested, total_value
    """
    records: list[dict[str, Any]] = []
    cash = initial_cash
    holdings: dict[str, list[dict]] = {}  # ticker -> [{"shares": n, "price": p}]

    # Pre-build deposit timeline if available
    deposit_events: list[tuple[pd.Timestamp, float]] = []
    if cash_flow_metadata:
        for dep in cash_flow_metadata.get("deposits", []):
            try:
                dt = pd.Timestamp(dep["date"])
                deposit_events.append((dt, dep["amount"]))
            except Exception:
                pass
        for div in cash_flow_metadata.get("dividends", []):
            try:
                dt = pd.Timestamp(div["date"])
                deposit_events.append((dt, div["amount"]))
            except Exception:
                pass
        deposit_events.sort(key=lambda x: x[0])

    deposit_idx = 0

    for _, row in trades_df.iterrows():
        ticker = row["ticker"]
        action = str(row["action"]).upper()
        qty = float(row["quantity"])
        price = float(row["price"])
        date = pd.Timestamp(row["date"])
        fees = float(row.get("fees", 0))

        # Apply any deposits/dividends that occurred before this trade
        while deposit_idx < len(deposit_events) and deposit_events[deposit_idx][0] <= date:
            cash += deposit_events[deposit_idx][1]
            deposit_idx += 1

        if action == "BUY":
            cost = qty * price + fees
            cash -= cost
            holdings.setdefault(ticker, []).append({"shares": qty, "price": price})
        elif action == "SELL":
            proceeds = qty * price - fees
            cash += proceeds
            lots = holdings.get(ticker, [])
            remaining = qty
            while remaining > 0 and lots:
                if lots[0]["shares"] <= remaining:
                    remaining -= lots[0]["shares"]
                    lots.pop(0)
                else:
                    lots[0]["shares"] -= remaining
                    remaining = 0

        # Approximate invested value at cost basis
        invested = sum(
            lot["shares"] * lot["price"]
            for lots in holdings.values()
            for lot in lots
        )

        records.append({
            "date": date,
            "cash": round(cash, 2),
            "invested": round(invested, 2),
            "total_value": round(cash + invested, 2),
        })

    return pd.DataFrame(records)


def position_size_analysis(
    trades_df: pd.DataFrame,
    trips: list[dict],
    account_size: float | None = None,
    cash_flow_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze position sizing behavior.

    If account_size is not provided, estimates it from actual trade data
    and cash flow metadata rather than defaulting to $100K.
    """
    buys = trades_df[trades_df["action"].str.upper() == "BUY"].copy()

    if buys.empty:
        return {
            "avg_position_pct": 0.0,
            "max_position_pct": 0.0,
            "position_size_consistency": 0.0,
            "conviction_sizing_detected": False,
            "post_loss_sizing_change": 0.0,
            "estimated_portfolio_value": 0.0,
            "portfolio_value_source": "none",
        }

    # Determine starting capital
    if account_size:
        est_account = account_size
        value_source = "user_provided"
    elif cash_flow_metadata and cash_flow_metadata.get("total_deposited", 0) > 0:
        est_account = cash_flow_metadata["total_deposited"]
        value_source = "cash_flow_deposits"
    else:
        est_account = _estimate_portfolio_value(trades_df, cash_flow_metadata)
        value_source = "estimated_from_trades"

    logger.info("Position sizing using portfolio value: $%.0f (source: %s)",
                est_account, value_source)

    # Reconstruct portfolio with correct starting capital
    portfolio = reconstruct_portfolio(
        trades_df,
        initial_cash=est_account,
        cash_flow_metadata=cash_flow_metadata,
    )

    # Compute position size at time of each buy
    # Use running portfolio value at the trade's position in the sequence
    position_pcts: list[float] = []
    buy_trade_indices: list[int] = []

    # Map each buy to its position in the full trades_df
    trade_idx = 0
    for i, (orig_idx, _) in enumerate(buys.iterrows()):
        # Walk forward in trades_df to find matching index
        while trade_idx < len(trades_df) and trades_df.index[trade_idx] < orig_idx:
            trade_idx += 1

        row = buys.iloc[i]
        trade_value = float(row["quantity"]) * float(row["price"])

        # Use portfolio value at this point in time
        if trade_idx < len(portfolio):
            pv = max(portfolio.iloc[trade_idx]["total_value"], 1.0)
        else:
            pv = est_account

        position_pcts.append(trade_value / pv)
        trade_idx += 1

    arr = np.array(position_pcts)

    # Position size consistency (inverse of CV)
    cv = float(np.std(arr) / np.mean(arr)) if np.mean(arr) > 0 else 0.0
    consistency = max(0.0, 1.0 - cv)

    # Conviction sizing detection
    conviction_detected = cv > 0.4 and len(arr) >= 5

    # Post-loss sizing change: compare average size after losses vs after wins
    post_loss_sizes: list[float] = []
    post_win_sizes: list[float] = []

    buy_dates = pd.to_datetime(buys["date"]).tolist()
    buy_sizes = [float(r["quantity"]) * float(r["price"]) for _, r in buys.iterrows()]

    for trip in trips:
        exit_date = trip["exit_date"]
        for j, bd in enumerate(buy_dates):
            if bd > exit_date:
                if trip["pnl"] < 0:
                    post_loss_sizes.append(buy_sizes[j])
                else:
                    post_win_sizes.append(buy_sizes[j])
                break

    avg_post_loss = np.mean(post_loss_sizes) if post_loss_sizes else 0
    avg_post_win = np.mean(post_win_sizes) if post_win_sizes else 0

    if avg_post_win > 0:
        sizing_change = float((avg_post_loss - avg_post_win) / avg_post_win)
    else:
        sizing_change = 0.0

    return {
        "avg_position_pct": round(float(np.mean(arr)) * 100, 2),
        "max_position_pct": round(float(np.max(arr)) * 100, 2),
        "position_size_consistency": round(consistency, 4),
        "conviction_sizing_detected": conviction_detected,
        "post_loss_sizing_change": round(sizing_change, 4),
        "estimated_portfolio_value": round(est_account, 2),
        "portfolio_value_source": value_source,
        "note": "Portfolio value estimated from equity/ETF trades only. Options premium tracked separately.",
    }
