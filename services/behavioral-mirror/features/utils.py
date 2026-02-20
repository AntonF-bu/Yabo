"""Shared utility functions for the 212-feature extraction engine.

All hardcoded ticker lists and classification functions have been moved
to ``services.market_data.MarketDataService`` (backed by Supabase).
This module retains only pure, stateless helpers.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_cv(series: pd.Series | np.ndarray) -> float | None:
    """Coefficient of variation. Returns None if insufficient data."""
    arr = np.asarray(series, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) < 2:
        return None
    mean = np.mean(arr)
    if mean == 0:
        return None
    return float(np.std(arr, ddof=1) / abs(mean))


def safe_divide(a: float | None, b: float | None) -> float | None:
    """Safe division returning None if b is 0 or either is None."""
    if a is None or b is None or b == 0:
        return None
    return float(a / b)


def estimate_portfolio_value(trades_df: pd.DataFrame) -> pd.Series:
    """Reconstruct approximate portfolio value over time from cumulative trades.

    Returns a Series indexed by date with estimated total portfolio value.
    """
    df = trades_df.sort_values("date").copy()
    if "value" not in df.columns:
        df["value"] = df["price"] * df["quantity"]

    # Walk through trades accumulating cash and holdings
    holdings: dict[str, float] = {}  # ticker -> shares
    dates = sorted(df["date"].unique())
    portfolio_vals: dict[Any, float] = {}

    # Rough estimate: track cumulative investment
    cum_invested = 0.0
    for date in dates:
        day_trades = df[df["date"] == date]
        for _, row in day_trades.iterrows():
            ticker = row["ticker"]
            qty = float(row["quantity"])
            price = float(row["price"])
            action = str(row["action"]).upper()

            if action == "BUY":
                holdings[ticker] = holdings.get(ticker, 0) + qty
                cum_invested += qty * price
            elif action == "SELL":
                holdings[ticker] = holdings.get(ticker, 0) - qty
                cum_invested -= qty * price  # approximate

        # Mark-to-market with last known prices
        total = 0.0
        for ticker, shares in holdings.items():
            if shares > 0:
                # Use the last price we saw for this ticker
                ticker_trades = df[(df["ticker"] == ticker) & (df["date"] <= date)]
                if len(ticker_trades) > 0:
                    last_price = float(ticker_trades.iloc[-1]["price"])
                    total += shares * last_price
        portfolio_vals[date] = max(total, 0)

    if not portfolio_vals:
        return pd.Series(dtype=float)
    return pd.Series(portfolio_vals).sort_index()


def compute_trend(series: pd.Series | np.ndarray) -> float | None:
    """Return slope of linear regression. Positive = increasing, negative = decreasing.

    Returns None if fewer than 3 data points.
    """
    arr = np.asarray(series, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) < 3:
        return None
    x = np.arange(len(arr), dtype=float)
    # Normalize x to [0, 1] to get interpretable slope
    if x[-1] > 0:
        x = x / x[-1]
    try:
        coeffs = np.polyfit(x, arr, 1)
        return float(coeffs[0])
    except (np.linalg.LinAlgError, ValueError):
        return None


def build_position_history(trades_df: pd.DataFrame) -> pd.DataFrame:
    """Reconstruct position-level data from trade history.

    For each ticker, tracks open date, shares accumulated, average cost,
    close date, close price, hold duration, return %. Handles partial closes.

    Returns DataFrame with columns:
        ticker, open_date, close_date, shares, avg_cost, close_price,
        hold_days, return_pct, pnl_usd, is_winner, is_partial_close, is_open
    """
    df = trades_df.sort_values("date").copy()
    positions: list[dict[str, Any]] = []

    # Per-ticker FIFO inventory
    inventory: dict[str, list[dict]] = {}  # ticker -> list of {date, qty, price}

    for _, row in df.iterrows():
        ticker = str(row["ticker"])
        action = str(row["action"]).upper()
        qty = float(row["quantity"])
        price = float(row["price"])
        date = row["date"]

        if action == "BUY":
            if ticker not in inventory:
                inventory[ticker] = []
            inventory[ticker].append({"date": date, "qty": qty, "price": price})

        elif action == "SELL":
            if ticker not in inventory or not inventory[ticker]:
                # Inherited exit - no matching buy
                positions.append({
                    "ticker": ticker,
                    "open_date": pd.NaT,
                    "close_date": date,
                    "shares": qty,
                    "avg_cost": None,
                    "close_price": price,
                    "hold_days": None,
                    "return_pct": None,
                    "pnl_usd": None,
                    "is_winner": None,
                    "is_partial_close": False,
                    "is_open": False,
                })
                continue

            remaining_sell = qty
            lots = inventory[ticker]

            while remaining_sell > 0 and lots:
                lot = lots[0]
                matched = min(remaining_sell, lot["qty"])
                is_partial = lot["qty"] > matched

                open_date = lot["date"]
                if pd.notna(open_date) and pd.notna(date):
                    try:
                        hold = (pd.Timestamp(date) - pd.Timestamp(open_date)).days
                    except Exception:
                        hold = None
                else:
                    hold = None

                cost = lot["price"]
                ret_pct = ((price - cost) / cost * 100) if cost and cost > 0 else None
                pnl = (price - cost) * matched if cost else None

                positions.append({
                    "ticker": ticker,
                    "open_date": open_date,
                    "close_date": date,
                    "shares": matched,
                    "avg_cost": cost,
                    "close_price": price,
                    "hold_days": hold,
                    "return_pct": ret_pct,
                    "pnl_usd": pnl,
                    "is_winner": ret_pct > 0 if ret_pct is not None else None,
                    "is_partial_close": is_partial,
                    "is_open": False,
                })

                lot["qty"] -= matched
                remaining_sell -= matched
                if lot["qty"] <= 0:
                    lots.pop(0)

    # Mark remaining inventory as open positions
    for ticker, lots in inventory.items():
        for lot in lots:
            if lot["qty"] > 0:
                positions.append({
                    "ticker": ticker,
                    "open_date": lot["date"],
                    "close_date": pd.NaT,
                    "shares": lot["qty"],
                    "avg_cost": lot["price"],
                    "close_price": None,
                    "hold_days": None,
                    "return_pct": None,
                    "pnl_usd": None,
                    "is_winner": None,
                    "is_partial_close": False,
                    "is_open": True,
                })

    if not positions:
        return pd.DataFrame(columns=[
            "ticker", "open_date", "close_date", "shares", "avg_cost",
            "close_price", "hold_days", "return_pct", "pnl_usd",
            "is_winner", "is_partial_close", "is_open",
        ])

    result = pd.DataFrame(positions)
    return result
