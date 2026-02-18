"""Feature group 10 – Market Awareness (14 features).

Measures how a trader responds to macro conditions: SPY moves, VIX,
FOMC/CPI event days, earnings season cadence, and retail herding.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from features.utils import safe_divide, TOP_RETAIL_STOCKS
from features.market_context import MarketContext

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 5

# ── Hard-coded macro event calendars (decision dates) ──────────────────────

FOMC_DATES: set[str] = {
    # 2023
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14",
    "2023-07-26", "2023-09-20", "2023-11-01", "2023-12-13",
    # 2024
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12",
    "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
}

CPI_DATES: set[str] = {
    # 2023
    "2023-01-12", "2023-02-14", "2023-03-14", "2023-04-12",
    "2023-05-10", "2023-06-13", "2023-07-12", "2023-08-10",
    "2023-09-13", "2023-10-12", "2023-11-14", "2023-12-12",
    # 2024
    "2024-01-11", "2024-02-13", "2024-03-12", "2024-04-10",
    "2024-05-15", "2024-06-12", "2024-07-11", "2024-08-14",
    "2024-09-11", "2024-10-10", "2024-11-13", "2024-12-11",
}

# Earnings season months (Jan, Apr, Jul, Oct).
_EARNINGS_MONTHS = {1, 4, 7, 10}


# ── Helpers ────────────────────────────────────────────────────────────────

def _daily_trade_counts(trades_df: pd.DataFrame) -> pd.Series:
    """Return a Series indexed by date with the number of trades that day."""
    dates = pd.to_datetime(trades_df["date"])
    return dates.dt.date.value_counts().sort_index()


def _event_activity_ratio(
    trades_df: pd.DataFrame,
    event_dates: set[str],
) -> float | None:
    """Compute average daily trades on event dates / average on non-event dates.

    Returns None if there are fewer than MIN_DATA_POINTS event-day observations
    or fewer than MIN_DATA_POINTS non-event-day observations.
    """
    dates = pd.to_datetime(trades_df["date"]).dt.date
    daily_counts = dates.value_counts().sort_index()

    event_set = {pd.Timestamp(d).date() for d in event_dates}
    on_event = daily_counts[daily_counts.index.isin(event_set)]
    off_event = daily_counts[~daily_counts.index.isin(event_set)]

    # We relax the threshold for event days (they are rare) – but we still
    # need at least 2 event-day trading observations and MIN_DATA_POINTS
    # normal-day observations to produce a meaningful ratio.
    if len(on_event) < 2 or len(off_event) < MIN_DATA_POINTS:
        return None

    avg_off = off_event.mean()
    if avg_off == 0:
        return None
    return float(on_event.mean() / avg_off)


# ── Main extractor ─────────────────────────────────────────────────────────

def extract(
    trades_df: pd.DataFrame,
    positions: pd.DataFrame,
    market_ctx: MarketContext,
) -> dict[str, Any]:
    """Return a dict of 14 market-awareness features."""

    out: dict[str, Any] = {
        "market_spy_trade_correlation": None,
        "market_buys_on_dips": None,
        "market_sells_on_dips": None,
        "market_contrarian_score": None,
        "market_herd_score": None,
        "market_vix_sensitivity": None,
        "market_regime_adaptation": None,
        "market_fed_day_activity": None,
        "market_cpi_day_activity": None,
        "market_earnings_season": None,
        "market_sector_momentum": None,
        "market_relative_strength": None,
        "market_timing_success": None,
        "market_retail_correlation": None,
    }

    if trades_df is None or len(trades_df) < MIN_DATA_POINTS:
        return out

    # Defensive copy with normalised dates
    df = trades_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["date_only"] = df["date"].dt.date
    df["action_upper"] = df["action"].astype(str).str.upper()

    total_trades = len(df)
    if total_trades < MIN_DATA_POINTS:
        return out

    # Pre-compute daily trade counts
    daily_counts = df.groupby("date_only").size()

    # ── Per-trade SPY return lookup ────────────────────────────────────────
    spy_returns: dict[Any, float | None] = {}
    for d in daily_counts.index:
        spy_returns[d] = market_ctx.get_spy_returns(pd.Timestamp(d))

    spy_return_series = pd.Series(
        {d: r for d, r in spy_returns.items() if r is not None}, dtype=float,
    )

    # ── 1. market_spy_trade_correlation ────────────────────────────────────
    if len(spy_return_series) >= MIN_DATA_POINTS:
        aligned_counts = daily_counts.reindex(spy_return_series.index).dropna()
        spy_abs = spy_return_series.reindex(aligned_counts.index).abs()
        if len(aligned_counts) >= MIN_DATA_POINTS:
            try:
                corr = float(np.corrcoef(spy_abs.values, aligned_counts.values)[0, 1])
                if not np.isnan(corr):
                    out["market_spy_trade_correlation"] = round(corr, 4)
            except Exception:
                pass

    # ── Dip / rally classification (SPY down/up >= 1%) ─────────────────────
    dip_dates = set(spy_return_series[spy_return_series <= -0.01].index)
    rally_dates = set(spy_return_series[spy_return_series >= 0.01].index)

    buys = df[df["action_upper"] == "BUY"].copy()
    sells = df[df["action_upper"] == "SELL"].copy()

    buys_on_dips = buys[buys["date_only"].isin(dip_dates)]
    sells_on_dips = sells[sells["date_only"].isin(dip_dates)]
    buys_on_rallies = buys[buys["date_only"].isin(rally_dates)]
    sells_on_rallies = sells[sells["date_only"].isin(rally_dates)]

    # ── 2. market_buys_on_dips ─────────────────────────────────────────────
    if len(buys) >= MIN_DATA_POINTS:
        out["market_buys_on_dips"] = round(
            len(buys_on_dips) / len(buys), 4,
        )

    # ── 3. market_sells_on_dips ────────────────────────────────────────────
    if len(sells) >= MIN_DATA_POINTS:
        out["market_sells_on_dips"] = round(
            len(sells_on_dips) / len(sells), 4,
        )

    # ── 4. market_contrarian_score ─────────────────────────────────────────
    if total_trades >= MIN_DATA_POINTS and len(dip_dates) > 0:
        out["market_contrarian_score"] = round(
            (len(buys_on_dips) - len(sells_on_dips)) / total_trades, 4,
        )

    # ── 5. market_herd_score ───────────────────────────────────────────────
    if total_trades >= MIN_DATA_POINTS and len(rally_dates) > 0:
        out["market_herd_score"] = round(
            (len(buys_on_rallies) - len(sells_on_rallies)) / total_trades, 4,
        )

    # ── 6. market_vix_sensitivity ──────────────────────────────────────────
    vix_values: dict[Any, float] = {}
    for d in daily_counts.index:
        v = market_ctx.get_vix_close(pd.Timestamp(d))
        if v is not None:
            vix_values[d] = v

    if len(vix_values) >= MIN_DATA_POINTS:
        vix_series = pd.Series(vix_values, dtype=float)
        aligned_counts_vix = daily_counts.reindex(vix_series.index).dropna()
        vix_aligned = vix_series.reindex(aligned_counts_vix.index)
        if len(aligned_counts_vix) >= MIN_DATA_POINTS:
            try:
                corr = float(
                    np.corrcoef(vix_aligned.values, aligned_counts_vix.values)[0, 1],
                )
                if not np.isnan(corr):
                    out["market_vix_sensitivity"] = round(corr, 4)
            except Exception:
                pass

    # ── 7. market_regime_adaptation ────────────────────────────────────────
    spy_20d: dict[Any, float] = {}
    for d in daily_counts.index:
        r = market_ctx.get_spy_20d_return(pd.Timestamp(d))
        if r is not None:
            spy_20d[d] = r

    if len(spy_20d) >= MIN_DATA_POINTS:
        spy_20d_series = pd.Series(spy_20d, dtype=float)
        bull_dates = spy_20d_series[spy_20d_series > 0.05].index
        bear_dates = spy_20d_series[spy_20d_series < -0.05].index

        bull_counts = daily_counts.reindex(bull_dates).dropna()
        bear_counts = daily_counts.reindex(bear_dates).dropna()

        # Need at least a few observations in each regime
        if len(bull_counts) >= 2 and len(bear_counts) >= 2:
            out["market_regime_adaptation"] = round(
                float(bull_counts.mean() - bear_counts.mean()), 4,
            )

    # ── 8. market_fed_day_activity ─────────────────────────────────────────
    out["market_fed_day_activity"] = _event_activity_ratio(df, FOMC_DATES)
    if out["market_fed_day_activity"] is not None:
        out["market_fed_day_activity"] = round(out["market_fed_day_activity"], 4)

    # ── 9. market_cpi_day_activity ─────────────────────────────────────────
    out["market_cpi_day_activity"] = _event_activity_ratio(df, CPI_DATES)
    if out["market_cpi_day_activity"] is not None:
        out["market_cpi_day_activity"] = round(out["market_cpi_day_activity"], 4)

    # ── 10. market_earnings_season ─────────────────────────────────────────
    df["month"] = df["date"].dt.month
    daily_with_month = df.groupby("date_only").agg(
        count=("ticker", "size"),
        month=("month", "first"),
    )
    earnings_days = daily_with_month[daily_with_month["month"].isin(_EARNINGS_MONTHS)]
    other_days = daily_with_month[~daily_with_month["month"].isin(_EARNINGS_MONTHS)]

    if len(earnings_days) >= MIN_DATA_POINTS and len(other_days) >= MIN_DATA_POINTS:
        avg_earnings = earnings_days["count"].mean()
        avg_other = other_days["count"].mean()
        ratio = safe_divide(avg_earnings, avg_other)
        if ratio is not None:
            out["market_earnings_season"] = round(ratio, 4)

    # ── 11. market_sector_momentum ─────────────────────────────────────────
    # Hard to compute reliably without full sector ETF return data – set None.
    out["market_sector_momentum"] = None

    # ── 12. market_relative_strength ───────────────────────────────────────
    # Requires per-stock vs per-sector performance decomposition – set None.
    out["market_relative_strength"] = None

    # ── 13. market_timing_success ──────────────────────────────────────────
    # For each buy date, compute SPY close percentile rank over trailing 252
    # trading days.  Low percentile = buying when SPY is cheap = good timing.
    buy_dates_unique = sorted(buys["date_only"].unique())
    if len(buy_dates_unique) >= MIN_DATA_POINTS:
        spy_df = market_ctx._get_df("SPY")  # noqa: SLF001
        if spy_df is not None and "Close" in spy_df.columns:
            spy_close = spy_df["Close"].sort_index()
            pct_ranks: list[float] = []
            for d in buy_dates_unique:
                ts = pd.Timestamp(d)
                mask = spy_close.index <= ts
                window = spy_close.loc[mask].tail(252)
                if len(window) < 50:
                    continue
                current = window.iloc[-1]
                rank = float((window < current).sum() / len(window))
                pct_ranks.append(rank)
            if len(pct_ranks) >= MIN_DATA_POINTS:
                out["market_timing_success"] = round(float(np.mean(pct_ranks)), 4)

    # ── 14. market_retail_correlation ──────────────────────────────────────
    # Jaccard similarity: |A ∩ B| / |A ∪ B|
    user_tickers = set(df["ticker"].astype(str).str.upper().unique())
    if len(user_tickers) > 0:
        intersection = user_tickers & TOP_RETAIL_STOCKS
        union = user_tickers | TOP_RETAIL_STOCKS
        if len(union) > 0:
            out["market_retail_correlation"] = round(
                len(intersection) / len(union), 4,
            )

    return out
