"""Position sizing analysis: size consistency, post-loss changes, conviction detection."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def reconstruct_portfolio(trades_df: pd.DataFrame, initial_cash: float = 100_000.0) -> pd.DataFrame:
    """Reconstruct portfolio value over time from trade sequence.

    Returns DataFrame with columns: date, cash, invested, total_value
    """
    records: list[dict[str, Any]] = []
    cash = initial_cash
    holdings: dict[str, list[dict]] = {}  # ticker -> [{"shares": n, "price": p}]

    for _, row in trades_df.iterrows():
        ticker = row["ticker"]
        action = str(row["action"]).upper()
        qty = float(row["quantity"])  # Support fractional shares
        price = float(row["price"])
        date = row["date"]
        fees = float(row.get("fees", 0))

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

        # Approximate invested value at current prices
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


def position_size_analysis(trades_df: pd.DataFrame,
                           trips: list[dict],
                           account_size: float | None = None) -> dict[str, Any]:
    """Analyze position sizing behavior."""
    buys = trades_df[trades_df["action"].str.upper() == "BUY"].copy()

    if buys.empty:
        return {
            "avg_position_pct": 0.0,
            "max_position_pct": 0.0,
            "position_size_consistency": 0.0,
            "conviction_sizing_detected": False,
            "post_loss_sizing_change": 0.0,
        }

    # Reconstruct portfolio to get value at each trade
    est_account = account_size or 100_000.0
    portfolio = reconstruct_portfolio(trades_df, initial_cash=est_account)

    position_pcts: list[float] = []
    for i, (_, row) in enumerate(buys.iterrows()):
        trade_value = float(row["quantity"]) * float(row["price"])
        # Find portfolio value at time of trade
        if i < len(portfolio):
            pv = max(portfolio.iloc[i]["total_value"], 1.0)
        else:
            pv = est_account
        position_pcts.append(trade_value / pv)

    arr = np.array(position_pcts)

    # Position size consistency (inverse of CV)
    cv = float(np.std(arr) / np.mean(arr)) if np.mean(arr) > 0 else 0.0
    consistency = max(0.0, 1.0 - cv)

    # Conviction sizing: look at variance of position sizes
    # If there's high variance but not random (correlated with something), it suggests conviction sizing
    conviction_detected = cv > 0.4 and len(arr) >= 5

    # Post-loss sizing change: compare average size after losses vs after wins
    post_loss_sizes: list[float] = []
    post_win_sizes: list[float] = []

    buy_dates = pd.to_datetime(buys["date"]).tolist()
    buy_sizes = [float(r["quantity"]) * float(r["price"]) for _, r in buys.iterrows()]

    for trip in trips:
        exit_date = trip["exit_date"]
        # Find next buy after this exit
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
    }
