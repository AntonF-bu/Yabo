"""Feature group 08 -- Sector allocation & ticker loyalty metrics.

Extracts 18 features describing *where* a trader concentrates capital:
sector dominance, rotation cadence, meme / mega-cap / small-cap exposure,
ticker loyalty, churn, and the core-vs-explore split.

All features are prefixed ``sector_``.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

from features.utils import safe_divide

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trade_value(row: pd.Series) -> float:
    return abs(float(row["price"]) * float(row["quantity"]))


def _hhi(weights: np.ndarray) -> float:
    """Herfindahl-Hirschman Index from an array of fractional weights."""
    w = np.asarray(weights, dtype=float)
    w = w[w > 0]
    if len(w) == 0:
        return 0.0
    w = w / w.sum()  # normalise just in case
    return float(np.sum(w ** 2))


def _jaccard_distance(a: set, b: set) -> float:
    """1 - Jaccard similarity.  Returns 1.0 if both sets are empty."""
    if not a and not b:
        return 0.0
    union = a | b
    if len(union) == 0:
        return 0.0
    return 1.0 - len(a & b) / len(union)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract(
    trades_df: pd.DataFrame,
    positions: pd.DataFrame,
    market_ctx: Any,
) -> dict[str, Any]:
    """Return 18 sector / ticker-loyalty features.

    Parameters
    ----------
    trades_df : DataFrame
        Columns: ticker, action, quantity, price, date, fees.
    positions : DataFrame
        Columns: ticker, open_date, close_date, shares, avg_cost,
        close_price, hold_days, return_pct, pnl_usd, is_winner,
        is_partial_close, is_open.
    market_ctx : MarketContext
        (Not heavily used in this module but accepted for API consistency.)

    Returns
    -------
    dict -- keys are ``sector_*`` feature names.
    """
    result: dict[str, Any] = {
        "sector_dominant": None,
        "sector_count": None,
        "sector_hhi": None,
        "sector_rotation_frequency": None,
        "sector_tech_overweight": None,
        "sector_healthcare_pct": None,
        "sector_energy_pct": None,
        "sector_financial_pct": None,
        "sector_meme_exposure": None,
        "sector_mega_cap_pct": None,
        "sector_small_cap_score": None,
        "sector_ipo_chaser": None,
        "sector_familiar_loyalty": None,
        "sector_ticker_loyalty": None,
        "sector_one_and_done_rate": None,
        "sector_core_vs_explore": None,
        "sector_new_ticker_monthly_rate": None,
        "sector_ticker_churn": None,
    }

    if trades_df is None or trades_df.empty or len(trades_df) < MIN_DATA_POINTS:
        return result

    df = trades_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    if len(df) < MIN_DATA_POINTS:
        return result

    df["_value"] = df.apply(_trade_value, axis=1)
    total_value = df["_value"].sum()
    if total_value <= 0:
        return result

    # Map each ticker to a sector string
    df["_sector"] = df["ticker"].apply(market_ctx.get_sector)

    # Sector dollar volumes
    sector_values = df.groupby("_sector")["_value"].sum().sort_values(ascending=False)
    sector_weights = sector_values / total_value

    # ------------------------------------------------------------------
    # 1. sector_dominant  (encoded as int)
    # ------------------------------------------------------------------
    dominant_sector = sector_values.index[0]
    result["sector_dominant"] = market_ctx.get_sector_int(dominant_sector) if dominant_sector != "unknown" else market_ctx.get_sector_int("unknown")

    # ------------------------------------------------------------------
    # 2. sector_count
    # ------------------------------------------------------------------
    # Exclude "unknown" from meaningful sector count
    known_sectors = [s for s in sector_values.index if s != "unknown"]
    result["sector_count"] = len(known_sectors) if known_sectors else int(len(sector_values))

    # ------------------------------------------------------------------
    # 3. sector_hhi
    # ------------------------------------------------------------------
    result["sector_hhi"] = float(round(_hhi(sector_weights.values), 4))

    # ------------------------------------------------------------------
    # 4. sector_rotation_frequency  (dominant sector changes per quarter)
    # ------------------------------------------------------------------
    df["_quarter"] = df["date"].dt.to_period("Q")
    quarters = sorted(df["_quarter"].unique())
    if len(quarters) >= 2:
        dominant_per_q: list[str] = []
        for q in quarters:
            q_df = df.loc[df["_quarter"] == q]
            q_sectors = q_df.groupby("_sector")["_value"].sum()
            dominant_per_q.append(q_sectors.idxmax())
        changes = sum(
            1 for i in range(1, len(dominant_per_q))
            if dominant_per_q[i] != dominant_per_q[i - 1]
        )
        result["sector_rotation_frequency"] = float(
            round(changes / len(quarters), 4)
        )

    # ------------------------------------------------------------------
    # 5-8. sector weight features
    # ------------------------------------------------------------------
    tech_weight = float(sector_weights.get("Technology", 0.0))
    result["sector_tech_overweight"] = float(round(tech_weight - 0.30, 4))
    result["sector_healthcare_pct"] = float(round(sector_weights.get("Healthcare", 0.0), 4))
    result["sector_energy_pct"] = float(round(sector_weights.get("Energy", 0.0), 4))
    result["sector_financial_pct"] = float(round(sector_weights.get("Financials", 0.0), 4))

    # ------------------------------------------------------------------
    # 9. sector_meme_exposure  (% of trade value in meme stocks)
    # ------------------------------------------------------------------
    meme_mask = df["ticker"].apply(market_ctx.is_meme_stock)
    meme_value = df.loc[meme_mask, "_value"].sum()
    result["sector_meme_exposure"] = float(round(meme_value / total_value, 4))

    # ------------------------------------------------------------------
    # 10. sector_mega_cap_pct
    # ------------------------------------------------------------------
    mega_mask = df["ticker"].apply(market_ctx.is_mega_cap)
    mega_value = df.loc[mega_mask, "_value"].sum()
    result["sector_mega_cap_pct"] = float(round(mega_value / total_value, 4))

    # ------------------------------------------------------------------
    # 11. sector_small_cap_score
    # ------------------------------------------------------------------
    small_mask = df["ticker"].apply(market_ctx.is_small_cap)
    small_value = df.loc[small_mask, "_value"].sum()
    result["sector_small_cap_score"] = float(round(small_value / total_value, 4))

    # ------------------------------------------------------------------
    # 12. sector_ipo_chaser  (1/0)
    # ------------------------------------------------------------------
    ipo_mask = df["ticker"].apply(market_ctx.is_recent_ipo)
    result["sector_ipo_chaser"] = 1 if ipo_mask.any() else 0

    # ------------------------------------------------------------------
    # 13. sector_familiar_loyalty  (sum of top-2 sector weights)
    # ------------------------------------------------------------------
    top2_weight = float(sector_weights.iloc[:2].sum()) if len(sector_weights) >= 2 else float(sector_weights.sum())
    result["sector_familiar_loyalty"] = float(round(top2_weight, 4))

    # ------------------------------------------------------------------
    # 14. sector_ticker_loyalty  (avg times a ticker is traded)
    # ------------------------------------------------------------------
    ticker_trade_counts = df.groupby("ticker").size()
    if len(ticker_trade_counts) >= 1:
        result["sector_ticker_loyalty"] = float(round(ticker_trade_counts.mean(), 4))

    # ------------------------------------------------------------------
    # 15. sector_one_and_done_rate  (% of tickers traded exactly once)
    # ------------------------------------------------------------------
    if len(ticker_trade_counts) >= MIN_DATA_POINTS:
        one_timers = (ticker_trade_counts == 1).sum()
        result["sector_one_and_done_rate"] = float(
            round(one_timers / len(ticker_trade_counts), 4)
        )

    # ------------------------------------------------------------------
    # 16. sector_core_vs_explore  (top-5 tickers as % of all trades)
    # ------------------------------------------------------------------
    ticker_sorted = ticker_trade_counts.sort_values(ascending=False)
    top5_trades = ticker_sorted.iloc[:5].sum()
    result["sector_core_vs_explore"] = float(
        round(top5_trades / len(df), 4)
    )

    # ------------------------------------------------------------------
    # 17. sector_new_ticker_monthly_rate
    # ------------------------------------------------------------------
    df["_month"] = df["date"].dt.to_period("M")
    months = sorted(df["_month"].unique())
    if len(months) >= 1:
        seen: set[str] = set()
        new_per_month: list[int] = []
        for month in months:
            month_tickers = set(df.loc[df["_month"] == month, "ticker"].unique())
            new_count = len(month_tickers - seen)
            new_per_month.append(new_count)
            seen |= month_tickers
        result["sector_new_ticker_monthly_rate"] = float(
            round(np.mean(new_per_month), 4)
        )

    # ------------------------------------------------------------------
    # 18. sector_ticker_churn  (avg month-over-month Jaccard distance)
    # ------------------------------------------------------------------
    if len(months) >= 3:
        monthly_sets: list[set[str]] = []
        for month in months:
            tickers_in_month = set(df.loc[df["_month"] == month, "ticker"].unique())
            monthly_sets.append(tickers_in_month)

        distances: list[float] = []
        for i in range(1, len(monthly_sets)):
            distances.append(_jaccard_distance(monthly_sets[i - 1], monthly_sets[i]))

        if len(distances) >= 2:
            result["sector_ticker_churn"] = float(round(np.mean(distances), 4))

    return result
