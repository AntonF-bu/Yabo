"""Feature group 12 – Cognitive Biases (12 features).

Detects well-known behavioural finance biases from trade and position data:
disposition effect, anchoring, recency, familiarity, action bias,
round-number preference, confirmation (escalation), endowment effect,
availability heuristic, and overconfidence.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from features.utils import (
    compute_cv,
    safe_divide,
)

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 5


def _sector_hhi(tickers: pd.Series, market_ctx: Any) -> float | None:
    """Herfindahl-Hirschman Index across sectors.  1 = fully concentrated."""
    if tickers is None or len(tickers) < MIN_DATA_POINTS:
        return None
    sectors = tickers.apply(market_ctx.get_sector)
    counts = sectors.value_counts(normalize=True)
    return float((counts ** 2).sum())


def _is_round_price(price: float, tolerance: float = 0.50) -> bool:
    """Return True if *price* is within *tolerance* of a $X0 or $X5 level."""
    if price <= 0 or np.isnan(price):
        return False
    mod = price % 10.0
    # Close to $X0.00 or $X5.00
    return min(mod, 10.0 - mod) <= tolerance or abs(mod - 5.0) <= tolerance


def extract(
    trades_df: pd.DataFrame,
    positions: pd.DataFrame,
    market_ctx: MarketContext,
) -> dict[str, Any]:
    """Return a dict of 12 cognitive-bias features."""

    out: dict[str, Any] = {
        "bias_disposition": None,
        "bias_anchoring": None,
        "bias_recency": None,
        "bias_familiarity": None,
        "bias_action": None,
        "bias_status_quo": None,
        "bias_denomination": None,
        "bias_round_number": None,
        "bias_confirmation": None,
        "bias_endowment": None,
        "bias_availability": None,
        "bias_overconfidence": None,
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
        for col in ("return_pct", "pnl_usd", "hold_days"):
            if col in pos.columns:
                pos[col] = pd.to_numeric(pos[col], errors="coerce")

    closed = (
        pos[(pos["is_open"] == False) & pos["return_pct"].notna()]  # noqa: E712
        if pos is not None and len(pos) > 0
        else pd.DataFrame()
    )
    losers = closed[closed["return_pct"] < 0] if len(closed) > 0 else pd.DataFrame()
    winners = closed[closed["return_pct"] > 0] if len(closed) > 0 else pd.DataFrame()

    # ── 1. bias_disposition ────────────────────────────────────────────────
    # Disposition effect: median hold time on losers / median hold time on winners.
    # >1 means holding losers longer (classic disposition effect).
    if (
        len(losers) >= MIN_DATA_POINTS
        and len(winners) >= MIN_DATA_POINTS
        and "hold_days" in closed.columns
    ):
        loser_hold = losers["hold_days"].dropna()
        winner_hold = winners["hold_days"].dropna()
        if len(loser_hold) >= MIN_DATA_POINTS and len(winner_hold) >= MIN_DATA_POINTS:
            med_loser = loser_hold.median()
            med_winner = winner_hold.median()
            ratio = safe_divide(med_loser, med_winner)
            if ratio is not None:
                out["bias_disposition"] = round(ratio, 4)

    # ── 2. bias_anchoring ─────────────────────────────────────────────────
    # % of re-buys within 3% of a previous buy price for the same ticker.
    buys = df[df["action_upper"] == "BUY"].sort_values("date").copy()
    if len(buys) >= MIN_DATA_POINTS:
        anchored_count = 0
        rebuy_count = 0
        for ticker, group in buys.groupby("ticker"):
            if len(group) < 2:
                continue
            prices = group["price"].values
            for i in range(1, len(prices)):
                rebuy_count += 1
                # Check if the new buy is within 3% of *any* previous buy
                prev_prices = prices[:i]
                current = prices[i]
                if current <= 0:
                    continue
                pct_diffs = np.abs((prev_prices - current) / current)
                if np.any(pct_diffs <= 0.03):
                    anchored_count += 1

        if rebuy_count >= MIN_DATA_POINTS:
            out["bias_anchoring"] = round(anchored_count / rebuy_count, 4)

    # ── 3. bias_recency ───────────────────────────────────────────────────
    # Correlation between most-recent return on a ticker and rebuy
    # probability.  Positive correlation = recency bias (chasing recent
    # winners / avoiding recent losers).
    if pos is not None and len(closed) >= MIN_DATA_POINTS and len(buys) >= MIN_DATA_POINTS:
        try:
            # For each closed position, record its return and whether the
            # trader bought the same ticker again within 30 days.
            closed_with_dates = closed.copy()
            closed_with_dates["close_date"] = pd.to_datetime(closed_with_dates["close_date"])
            closed_with_dates = closed_with_dates.dropna(subset=["close_date", "return_pct"])

            if len(closed_with_dates) >= MIN_DATA_POINTS:
                rebuy_flags: list[int] = []
                returns: list[float] = []

                buy_lookup: dict[str, list[pd.Timestamp]] = {}
                for _, row in buys.iterrows():
                    t = str(row["ticker"]).upper()
                    buy_lookup.setdefault(t, []).append(pd.Timestamp(row["date"]))

                for _, row in closed_with_dates.iterrows():
                    t = str(row["ticker"]).upper()
                    close_dt = pd.Timestamp(row["close_date"])
                    ret = float(row["return_pct"])
                    future_buys = buy_lookup.get(t, [])
                    rebought = any(
                        0 < (b - close_dt).days <= 30 for b in future_buys
                    )
                    rebuy_flags.append(int(rebought))
                    returns.append(ret)

                if len(returns) >= MIN_DATA_POINTS and np.std(returns) > 0 and np.std(rebuy_flags) > 0:
                    corr = float(np.corrcoef(returns, rebuy_flags)[0, 1])
                    if not np.isnan(corr):
                        out["bias_recency"] = round(corr, 4)
        except Exception:
            pass

    # ── 4. bias_familiarity ───────────────────────────────────────────────
    # Sector HHI – high concentration implies familiarity bias.
    if len(df) >= MIN_DATA_POINTS:
        hhi = _sector_hhi(df["ticker"], market_ctx)
        if hhi is not None:
            out["bias_familiarity"] = round(hhi, 4)

    # ── 5. bias_action ────────────────────────────────────────────────────
    # Total trades per month – high values imply action bias / overtrading.
    if len(df) >= MIN_DATA_POINTS:
        first_date = df["date"].min()
        last_date = df["date"].max()
        span_days = (last_date - first_date).days
        if span_days >= 28:
            months = max(span_days / 30.44, 1.0)
            out["bias_action"] = round(float(len(df) / months), 4)

    # ── 6. bias_status_quo ────────────────────────────────────────────────
    # 1 - monthly turnover rate.  Turnover = sells-value / average portfolio
    # value.  High status_quo = low turnover = reluctance to change.
    if len(df) >= MIN_DATA_POINTS:
        try:
            sells = df[df["action_upper"] == "SELL"]
            if len(sells) >= 2:
                first_date = df["date"].min()
                last_date = df["date"].max()
                span_days = (last_date - first_date).days
                if span_days >= 28:
                    months = max(span_days / 30.44, 1.0)
                    sell_value_monthly = sells["trade_value"].sum() / months
                    # Portfolio proxy: median daily total traded value
                    daily_value = df.groupby(df["date"].dt.date)["trade_value"].sum()
                    portfolio_proxy = daily_value.median()
                    if portfolio_proxy > 0:
                        turnover = sell_value_monthly / portfolio_proxy
                        # Clamp to [0, 1] range
                        status_quo = max(0.0, min(1.0, 1.0 - turnover))
                        out["bias_status_quo"] = round(status_quo, 4)
        except Exception:
            pass

    # ── 7. bias_denomination ──────────────────────────────────────────────
    # Average stock price traded (preference for nominally cheap stocks).
    if len(df) >= MIN_DATA_POINTS:
        avg_price = df["price"].median()
        if avg_price is not None and not np.isnan(avg_price):
            out["bias_denomination"] = round(float(avg_price), 2)

    # ── 8. bias_round_number ──────────────────────────────────────────────
    # % of entries / exits at round-dollar prices ($X0, $X5 within $0.50).
    if len(df) >= MIN_DATA_POINTS:
        round_count = df["price"].apply(_is_round_price).sum()
        out["bias_round_number"] = round(float(round_count / len(df)), 4)

    # ── 9. bias_confirmation (escalation of commitment) ───────────────────
    # % of losing positions where the trader bought *more* of the same
    # ticker while the position was losing.
    if pos is not None and len(closed) >= MIN_DATA_POINTS and len(buys) >= MIN_DATA_POINTS:
        try:
            losing_positions = closed[closed["return_pct"] < 0].copy()
            losing_positions["open_date"] = pd.to_datetime(losing_positions["open_date"])
            losing_positions["close_date"] = pd.to_datetime(losing_positions["close_date"])
            losing_positions = losing_positions.dropna(subset=["open_date", "close_date"])

            if len(losing_positions) >= MIN_DATA_POINTS:
                escalated = 0
                for _, lp in losing_positions.iterrows():
                    ticker = str(lp["ticker"]).upper()
                    open_dt = pd.Timestamp(lp["open_date"])
                    close_dt = pd.Timestamp(lp["close_date"])
                    # Did they buy more of this ticker while the position was open?
                    additional_buys = buys[
                        (buys["ticker"].str.upper() == ticker)
                        & (buys["date"] > open_dt)
                        & (buys["date"] <= close_dt)
                    ]
                    if len(additional_buys) > 0:
                        escalated += 1
                out["bias_confirmation"] = round(
                    float(escalated / len(losing_positions)), 4,
                )
        except Exception:
            pass

    # ── 10. bias_endowment ────────────────────────────────────────────────
    # Avg hold duration on losers vs "optimal" (avg hold on winners).
    # Ratio > 1 means endowment effect – overvaluing what you own.
    if (
        len(losers) >= MIN_DATA_POINTS
        and len(winners) >= MIN_DATA_POINTS
        and "hold_days" in closed.columns
    ):
        loser_hold = losers["hold_days"].dropna()
        winner_hold = winners["hold_days"].dropna()
        if len(loser_hold) >= MIN_DATA_POINTS and len(winner_hold) >= MIN_DATA_POINTS:
            avg_loser_hold = loser_hold.mean()
            avg_winner_hold = winner_hold.mean()
            ratio = safe_divide(avg_loser_hold, avg_winner_hold)
            if ratio is not None:
                out["bias_endowment"] = round(ratio, 4)

    # ── 11. bias_availability ─────────────────────────────────────────────
    # % of trades in the top-20 most-traded retail stocks.
    if len(df) >= MIN_DATA_POINTS:
        top_retail = market_ctx.get_top_retail_stocks() if hasattr(market_ctx, "get_top_retail_stocks") else set()
        in_top = df["ticker"].astype(str).str.upper().isin(top_retail)
        out["bias_availability"] = round(float(in_top.sum() / len(df)), 4)

    # ── 12. bias_overconfidence ───────────────────────────────────────────
    # Composite: (sizing_after_wins_ratio + new_ticker_rate_after_wins) / 2
    # sizing_after_wins_ratio = avg trade value after a win / avg trade value
    #     after a loss
    # new_ticker_rate_after_wins = fraction of trades that are *new* tickers
    #     in the 7 days after a win vs overall new-ticker rate
    if pos is not None and len(closed) >= MIN_DATA_POINTS and len(df) >= MIN_DATA_POINTS:
        try:
            closed_dated = closed.copy()
            closed_dated["close_date"] = pd.to_datetime(closed_dated["close_date"])
            closed_dated = closed_dated.dropna(subset=["close_date"])

            win_dates = set(
                closed_dated[closed_dated["is_winner"] == True]["close_date"].dt.date  # noqa: E712
            )
            loss_dates = set(
                closed_dated[closed_dated["is_winner"] == False]["close_date"].dt.date  # noqa: E712
            )

            if len(win_dates) >= 3 and len(loss_dates) >= 3:
                # Component 1: sizing after wins vs after losses
                # Trades in the 7 days after a win date
                after_win_values: list[float] = []
                after_loss_values: list[float] = []

                for _, trade in df.iterrows():
                    trade_date = trade["date"].date()
                    for wd in win_dates:
                        diff = (trade_date - wd).days
                        if 1 <= diff <= 7:
                            after_win_values.append(float(trade["trade_value"]))
                            break
                    for ld in loss_dates:
                        diff = (trade_date - ld).days
                        if 1 <= diff <= 7:
                            after_loss_values.append(float(trade["trade_value"]))
                            break

                sizing_ratio = None
                if (
                    len(after_win_values) >= MIN_DATA_POINTS
                    and len(after_loss_values) >= MIN_DATA_POINTS
                ):
                    sizing_ratio = safe_divide(
                        np.mean(after_win_values),
                        np.mean(after_loss_values),
                    )

                # Component 2: new-ticker rate after wins vs overall
                all_tickers_seen: set[str] = set()
                df_sorted = df.sort_values("date")
                new_ticker_flags: list[bool] = []
                for _, trade in df_sorted.iterrows():
                    t = str(trade["ticker"]).upper()
                    new_ticker_flags.append(t not in all_tickers_seen)
                    all_tickers_seen.add(t)

                df_sorted = df_sorted.copy()
                df_sorted["is_new_ticker"] = new_ticker_flags

                after_win_new: list[bool] = []
                for _, trade in df_sorted.iterrows():
                    trade_date = trade["date"].date()
                    for wd in win_dates:
                        diff = (trade_date - wd).days
                        if 1 <= diff <= 7:
                            after_win_new.append(bool(trade["is_new_ticker"]))
                            break

                overall_new_rate = sum(new_ticker_flags) / len(new_ticker_flags) if new_ticker_flags else 0
                new_ticker_ratio = None
                if len(after_win_new) >= MIN_DATA_POINTS and overall_new_rate > 0:
                    after_win_new_rate = sum(after_win_new) / len(after_win_new)
                    new_ticker_ratio = after_win_new_rate / overall_new_rate

                # Combine into composite
                if sizing_ratio is not None and new_ticker_ratio is not None:
                    composite = (sizing_ratio + new_ticker_ratio) / 2.0
                    out["bias_overconfidence"] = round(float(composite), 4)
                elif sizing_ratio is not None:
                    out["bias_overconfidence"] = round(float(sizing_ratio), 4)
                elif new_ticker_ratio is not None:
                    out["bias_overconfidence"] = round(float(new_ticker_ratio), 4)
        except Exception:
            pass

    return out
