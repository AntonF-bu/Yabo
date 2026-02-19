"""Pattern analysis: sectors, concentration, win/loss, stops, tax awareness."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from extractor.ticker_resolver import KNOWN_SECTORS, resolve_ticker

logger = logging.getLogger(__name__)

# Re-export for backward compat
TICKER_TO_SECTOR = KNOWN_SECTORS

# Module-level resolved cache for the current extraction run
_resolved_sectors: dict[str, str] = {}


def set_resolved_sectors(mapping: dict[str, str]) -> None:
    """Set pre-resolved sector mapping from batch resolution in pipeline."""
    global _resolved_sectors
    _resolved_sectors = dict(mapping)


def _get_sector(ticker: str) -> str:
    """Get sector for a ticker using resolved cache, hardcoded map, or dynamic resolution."""
    # Check pre-resolved batch first
    if ticker in _resolved_sectors:
        return _resolved_sectors[ticker]
    # Hardcoded fast path
    if ticker in KNOWN_SECTORS:
        return KNOWN_SECTORS[ticker]
    # Dynamic resolution
    info = resolve_ticker(ticker)
    sector = info.get("sector", "Unknown")
    _resolved_sectors[ticker] = sector
    return sector


def sector_analysis(trades_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute dominant sectors by trade count and value."""
    if trades_df.empty:
        return []

    buys = trades_df[trades_df["action"].str.upper() == "BUY"]
    sector_trades: dict[str, int] = {}
    sector_value: dict[str, float] = {}

    for _, row in buys.iterrows():
        sector = _get_sector(row["ticker"])
        val = float(row["quantity"]) * float(row["price"])
        sector_trades[sector] = sector_trades.get(sector, 0) + 1
        sector_value[sector] = sector_value.get(sector, 0) + val

    total_trades = sum(sector_trades.values())
    total_value = sum(sector_value.values())

    result = []
    for sector in sorted(sector_trades, key=sector_trades.get, reverse=True):  # type: ignore[arg-type]
        weight = sector_value[sector] / total_value if total_value > 0 else 0
        result.append({
            "sector": sector,
            "weight": round(weight, 4),
            "trade_count": sector_trades[sector],
        })

    return result


def ticker_concentration(trades_df: pd.DataFrame) -> dict[str, Any]:
    """Compute HHI index and top tickers."""
    buys = trades_df[trades_df["action"].str.upper() == "BUY"]
    if buys.empty:
        return {"hhi_index": 0.0, "unique_tickers": 0, "top_3_tickers": []}

    ticker_values: dict[str, float] = {}
    for _, row in buys.iterrows():
        t = row["ticker"]
        v = float(row["quantity"]) * float(row["price"])
        ticker_values[t] = ticker_values.get(t, 0) + v

    total = sum(ticker_values.values())
    if total <= 0:
        return {"hhi_index": 0.0, "unique_tickers": len(ticker_values), "top_3_tickers": []}

    shares = [(v / total) for v in ticker_values.values()]
    hhi = sum(s ** 2 for s in shares)

    sorted_tickers = sorted(ticker_values, key=ticker_values.get, reverse=True)  # type: ignore[arg-type]

    return {
        "hhi_index": round(hhi, 4),
        "unique_tickers": len(ticker_values),
        "top_3_tickers": sorted_tickers[:3],
    }


def win_loss_stats(trips: list[dict]) -> dict[str, float]:
    """Compute win rate, avg winner/loser, profit factor."""
    if not trips:
        return {
            "win_rate": 0.0, "avg_winner_pct": 0.0,
            "avg_loser_pct": 0.0, "profit_factor": 0.0,
        }

    winners = [t for t in trips if t["pnl_pct"] > 0]
    losers = [t for t in trips if t["pnl_pct"] <= 0]

    win_rate = len(winners) / len(trips) if trips else 0
    avg_winner = np.mean([t["pnl_pct"] for t in winners]) if winners else 0
    avg_loser = np.mean([t["pnl_pct"] for t in losers]) if losers else 0

    total_wins = sum(t["pnl"] for t in winners) if winners else 0
    total_losses = abs(sum(t["pnl"] for t in losers)) if losers else 0
    profit_factor = total_wins / total_losses if total_losses > 0 else (float("inf") if total_wins > 0 else 0.0)

    return {
        "win_rate": round(float(win_rate), 4),
        "avg_winner_pct": round(float(avg_winner) * 100, 2),
        "avg_loser_pct": round(float(avg_loser) * 100, 2),
        "profit_factor": round(float(min(profit_factor, 100.0)), 4),
    }


def exit_pattern_analysis(trips: list[dict]) -> dict[str, Any]:
    """Analyze exit patterns: winner hold times, loser hold times, stop detection."""
    if not trips:
        return {
            "avg_winner_hold_days": 0.0, "avg_loser_hold_days": 0.0,
            "stop_loss_detected": False, "trailing_stop_detected": False,
            "time_based_exits_pct": 0.0,
        }

    winners = [t for t in trips if t["pnl_pct"] > 0]
    losers = [t for t in trips if t["pnl_pct"] <= 0]

    avg_winner_hold = np.mean([t["hold_days"] for t in winners]) if winners else 0
    avg_loser_hold = np.mean([t["hold_days"] for t in losers]) if losers else 0

    # Stop-loss detection: check if losing exits cluster around specific loss thresholds
    stop_detected = False
    if len(losers) >= 5:
        loss_pcts = [abs(t["pnl_pct"]) for t in losers]
        # If std of loss percentages is low relative to mean, suggests fixed stop
        std = np.std(loss_pcts)
        mean = np.mean(loss_pcts)
        if mean > 0 and std / mean < 0.4:
            stop_detected = True

    # Trailing stop detection: winners exit with some pullback from peak
    # Hard to detect without peak data, but we can check if winner exits
    # cluster at similar pnl levels
    trailing_detected = False
    if len(winners) >= 5:
        win_pcts = [t["pnl_pct"] for t in winners]
        std = np.std(win_pcts)
        mean = np.mean(win_pcts)
        if mean > 0 and std / mean < 0.5:
            trailing_detected = True

    # Time-based exits: check if hold periods cluster
    hold_days = [t["hold_days"] for t in trips]
    time_based_pct = 0.0
    if len(hold_days) >= 5:
        median_hold = np.median(hold_days)
        near_median = sum(1 for d in hold_days if abs(d - median_hold) < median_hold * 0.3)
        time_based_pct = near_median / len(hold_days)

    return {
        "avg_winner_hold_days": round(float(avg_winner_hold), 2),
        "avg_loser_hold_days": round(float(avg_loser_hold), 2),
        "stop_loss_detected": stop_detected,
        "trailing_stop_detected": trailing_detected,
        "time_based_exits_pct": round(float(time_based_pct), 4),
    }


def tax_analysis(trips: list[dict], tax_jurisdiction: str | None = None) -> dict[str, Any]:
    """Analyze tax-aware behavior."""
    from tax_data import get_combined_long_term_rate

    tax_rate = get_combined_long_term_rate(tax_jurisdiction or "")

    if not trips:
        return {
            "tax_jurisdiction": tax_jurisdiction or "unknown",
            "tax_rate": tax_rate,
            "tax_awareness_score": 0,
            "ltcg_optimization_detected": False,
            "tax_loss_harvesting_detected": False,
        }

    winners = [t for t in trips if t["pnl_pct"] > 0]
    losers = [t for t in trips if t["pnl_pct"] <= 0]

    # LTCG optimization: winners held > 365 days
    ltcg_count = sum(1 for t in winners if t["hold_days"] >= 365) if winners else 0
    ltcg_pct = ltcg_count / len(winners) if winners else 0
    ltcg_detected = ltcg_pct > 0.3 and tax_rate > 0.20

    # Tax-loss harvesting: selling losers near year-end (Nov-Dec)
    year_end_losses = 0
    for t in losers:
        if hasattr(t["exit_date"], "month"):
            if t["exit_date"].month in (11, 12):
                year_end_losses += 1
        else:
            try:
                m = pd.Timestamp(t["exit_date"]).month
                if m in (11, 12):
                    year_end_losses += 1
            except Exception:
                pass

    tlh_detected = year_end_losses >= 2 and len(losers) > 0 and year_end_losses / len(losers) > 0.3

    # Tax awareness score
    score = 0
    if ltcg_detected:
        score += 40
    if ltcg_pct > 0.1:
        score += 20
    if tlh_detected:
        score += 30
    if tax_rate > 0.25:
        score += 10  # high-tax jurisdiction awareness bonus
    score = min(score, 100)

    return {
        "tax_jurisdiction": tax_jurisdiction or "unknown",
        "tax_rate": round(tax_rate, 4),
        "tax_awareness_score": score,
        "ltcg_optimization_detected": ltcg_detected,
        "tax_loss_harvesting_detected": tlh_detected,
    }


def pdt_analysis(trades_df: pd.DataFrame, account_size: float | None = None) -> dict[str, Any]:
    """Detect PDT constraints from trade patterns."""
    if trades_df.empty:
        return {"pdt_constrained": False, "pdt_impact_score": 0}

    inferred_constrained = account_size is not None and account_size < 25_000

    # Check for day-trade frequency patterns
    buys = trades_df[trades_df["action"].str.upper() == "BUY"]
    sells = trades_df[trades_df["action"].str.upper() == "SELL"]

    day_trades = 0
    for _, sell in sells.iterrows():
        sell_date = pd.Timestamp(sell["date"])
        matching_buys = buys[
            (buys["ticker"] == sell["ticker"]) &
            (pd.to_datetime(buys["date"]) == sell_date)
        ]
        if not matching_buys.empty:
            day_trades += 1

    # If account is small and day trades are capped at ~3 per week, PDT is likely
    total_weeks = 1
    if len(trades_df) > 1:
        dates = pd.to_datetime(trades_df["date"])
        total_days = (dates.max() - dates.min()).days
        total_weeks = max(1, total_days / 7)

    day_trades_per_week = day_trades / total_weeks

    impact_score = 0
    if inferred_constrained:
        impact_score = min(100, int(day_trades_per_week * 30))
        if day_trades_per_week < 0.7:
            impact_score = max(impact_score, 50)  # avoiding day trades = high impact

    return {
        "pdt_constrained": inferred_constrained,
        "pdt_impact_score": impact_score,
    }


def sector_concentration_risk(sectors: list[dict]) -> float:
    """Compute sector concentration risk (HHI of sectors)."""
    if not sectors:
        return 0.0
    weights = [s["weight"] for s in sectors]
    return round(sum(w ** 2 for w in weights), 4)
