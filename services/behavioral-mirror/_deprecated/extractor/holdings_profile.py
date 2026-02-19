"""Holdings-based feature extraction: market cap profile, risk scoring, speculative ratio.

These features capture WHAT the trader buys, not just HOW they trade.
A portfolio of IONQ + INMB + SOUN is fundamentally different from JNJ + PG + KO,
even if holding periods are identical.

ETF-aware: ETFs are resolved by category (Broad Market, Technology, etc.) rather
than treated as unknown equities.  Index ETFs lower risk; leveraged/inverse ETFs
raise it.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Sector -> volatility tier mapping
_SECTOR_VOLATILITY: dict[str, str] = {
    "Technology": "high",
    "Industrials": "medium",
    "Financials": "medium",
    "Energy": "medium",
    "Healthcare": "high",      # Biotech drives this up
    "Consumer": "low",
    "Utilities": "low",
    "Materials": "medium",
    "Real Estate": "medium",
    "Index": "low",
    "Broad Market": "low",     # Broad market index ETFs
    "Commodities": "high",
    "Fixed Income": "low",
    "Other ETF": "medium",
    "Unknown": "high",         # Unknown tickers are likely speculative
}

# Market cap category -> risk score component (higher = riskier)
_MCAP_RISK_SCORE: dict[str, int] = {
    "mega": 5,
    "large": 15,
    "mid": 35,
    "small": 60,
    "micro": 85,
    "known": 10,    # Hardcoded tickers are mostly mega/large
    "unknown": 65,  # Unknown tickers are likely smaller/speculative
}

# Sector -> risk score component (higher = riskier)
_SECTOR_RISK_SCORE: dict[str, int] = {
    "Technology": 40,
    "Healthcare": 45,    # biotech exposure
    "Energy": 35,
    "Financials": 30,
    "Industrials": 25,
    "Materials": 30,
    "Real Estate": 25,
    "Consumer": 15,
    "Utilities": 10,
    "Index": 5,
    "Broad Market": 5,
    "Commodities": 40,
    "Fixed Income": 5,
    "Other ETF": 25,
    "Unknown": 55,
}

# ETF risk_tier -> risk score override (replaces the mcap * 0.6 + sector * 0.4 formula)
_ETF_RISK_OVERRIDE: dict[str, int] = {
    "low": 8,
    "medium": 25,
    "high": 50,
    "very_high": 85,
}


def compute_holdings_profile(
    trades_df: pd.DataFrame,
    resolved_tickers: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compute holdings-based features from the trader's portfolio.

    Args:
        trades_df: Normalized trades DataFrame with ticker, action, quantity, price columns.
        resolved_tickers: Dict from resolve_batch() with ticker info including
            market_cap, market_cap_category, sector, and optionally instrument_type.

    Returns:
        Dict with:
            market_cap_distribution: {mega: %, large: %, ...}
            holdings_risk_score: 0-100
            sector_volatility_exposure: {high: %, medium: %, low: %}
            speculative_holdings_ratio: float
            weighted_avg_market_cap_category: str
            index_etf_pct: float  (fraction of portfolio in passive index ETFs)
    """
    buys = trades_df[trades_df["action"].str.upper() == "BUY"]
    if buys.empty:
        return _empty_holdings_profile()

    # Compute dollar-weighted exposure per ticker
    ticker_values: dict[str, float] = {}
    for _, row in buys.iterrows():
        t = str(row["ticker"]).upper().strip()
        v = float(row["quantity"]) * float(row["price"])
        ticker_values[t] = ticker_values.get(t, 0) + v

    total_value = sum(ticker_values.values())
    if total_value <= 0:
        return _empty_holdings_profile()

    # Compute dollar weights per ticker
    ticker_weights: dict[str, float] = {
        t: v / total_value for t, v in ticker_values.items()
    }

    # 1. Market cap distribution (dollar-weighted)
    mcap_dist: dict[str, float] = {
        "mega": 0.0, "large": 0.0, "mid": 0.0,
        "small": 0.0, "micro": 0.0, "unknown": 0.0,
    }
    for ticker, weight in ticker_weights.items():
        info = resolved_tickers.get(ticker, {})
        cat = info.get("market_cap_category", "unknown")
        # Map "known" (hardcoded without explicit mcap) to a reasonable bucket
        if cat == "known":
            cat = _infer_hardcoded_mcap_category(ticker)
        if cat not in mcap_dist:
            cat = "unknown"
        mcap_dist[cat] += weight

    # Round for readability
    mcap_dist = {k: round(v, 4) for k, v in mcap_dist.items()}

    # 2. Weighted average market cap category
    # Numeric scale: mega=5, large=4, mid=3, small=2, micro=1, unknown=2 (assume small-ish)
    _mcap_numeric = {"mega": 5, "large": 4, "mid": 3, "small": 2, "micro": 1, "unknown": 2}
    weighted_score = sum(
        _mcap_numeric.get(
            _normalize_mcap_cat(resolved_tickers.get(t, {}).get("market_cap_category", "unknown"), t),
            2,
        ) * w
        for t, w in ticker_weights.items()
    )
    if weighted_score >= 4.5:
        avg_cat = "mega"
    elif weighted_score >= 3.5:
        avg_cat = "large"
    elif weighted_score >= 2.5:
        avg_cat = "mid"
    elif weighted_score >= 1.5:
        avg_cat = "small"
    else:
        avg_cat = "micro"

    # 3. Holdings risk score (0-100, higher = riskier)
    # ETFs use risk_tier override; equities use mcap + sector formula.
    risk_scores: list[float] = []
    for ticker, weight in ticker_weights.items():
        info = resolved_tickers.get(ticker, {})
        instrument = info.get("instrument_type", "equity")

        if instrument == "ETF":
            risk_tier = info.get("risk_tier", "medium")
            combined = _ETF_RISK_OVERRIDE.get(risk_tier, 25)
        else:
            cat = _normalize_mcap_cat(info.get("market_cap_category", "unknown"), ticker)
            sector = info.get("sector", "Unknown")
            mcap_risk = _MCAP_RISK_SCORE.get(cat, 65)
            sector_risk = _SECTOR_RISK_SCORE.get(sector, 55)
            combined = mcap_risk * 0.6 + sector_risk * 0.4

        risk_scores.append(combined * weight)

    holdings_risk = min(100, max(0, round(sum(risk_scores))))

    # 4. Sector volatility exposure (dollar-weighted)
    vol_exposure: dict[str, float] = {"high": 0.0, "medium": 0.0, "low": 0.0}
    for ticker, weight in ticker_weights.items():
        info = resolved_tickers.get(ticker, {})
        sector = info.get("sector", "Unknown")
        tier = _SECTOR_VOLATILITY.get(sector, "high")
        vol_exposure[tier] += weight

    vol_exposure = {k: round(v, 4) for k, v in vol_exposure.items()}

    # 5. Speculative holdings ratio
    # Equities: market cap < $2B or category small/micro/unknown.
    # ETFs: only leveraged/inverse ETFs are speculative. Index ETFs are NOT.
    speculative_ratio = 0.0
    for ticker, weight in ticker_weights.items():
        info = resolved_tickers.get(ticker, {})
        instrument = info.get("instrument_type", "equity")

        if instrument == "ETF":
            # Only leveraged/inverse ETFs count as speculative
            if info.get("is_leveraged") or info.get("is_inverse"):
                speculative_ratio += weight
            # Regular ETFs (including sector ETFs) are NOT speculative
        else:
            # Equity: original logic using market cap
            cat = _normalize_mcap_cat(info.get("market_cap_category", "unknown"), ticker)
            market_cap = info.get("market_cap")

            if market_cap is not None:
                if market_cap < 2_000_000_000:
                    speculative_ratio += weight
            elif cat in ("small", "micro", "unknown"):
                speculative_ratio += weight

    speculative_ratio = round(speculative_ratio, 4)

    # 6. Index ETF percentage (for archetype scoring — strong passive/DCA signal)
    index_etf_pct = 0.0
    for ticker, weight in ticker_weights.items():
        info = resolved_tickers.get(ticker, {})
        if info.get("instrument_type") == "ETF" and info.get("is_index_fund"):
            index_etf_pct += weight
    index_etf_pct = round(index_etf_pct, 4)

    logger.info(
        "Holdings profile: risk=%d, avg_mcap=%s, speculative=%.0f%%, index_etf=%.0f%%, "
        "volatility={high:%.0f%%, med:%.0f%%, low:%.0f%%}",
        holdings_risk, avg_cat, speculative_ratio * 100, index_etf_pct * 100,
        vol_exposure["high"] * 100, vol_exposure["medium"] * 100,
        vol_exposure["low"] * 100,
    )

    return {
        "market_cap_distribution": mcap_dist,
        "weighted_avg_market_cap_category": avg_cat,
        "holdings_risk_score": holdings_risk,
        "sector_volatility_exposure": vol_exposure,
        "speculative_holdings_ratio": speculative_ratio,
        "index_etf_pct": index_etf_pct,
    }


def _normalize_mcap_cat(cat: str, ticker: str) -> str:
    """Normalize market cap category, inferring for hardcoded 'known' tickers."""
    if cat == "known":
        return _infer_hardcoded_mcap_category(ticker)
    return cat


def _infer_hardcoded_mcap_category(ticker: str) -> str:
    """Infer market cap category for hardcoded tickers (all are mega or large)."""
    # The hardcoded 36 tickers are mostly mega/large cap blue chips
    _HARDCODED_MCAP: dict[str, str] = {
        # Mega cap (>$200B)
        "AAPL": "mega", "MSFT": "mega", "NVDA": "mega", "GOOGL": "mega",
        "AMZN": "mega", "META": "mega", "TSLA": "mega", "AVGO": "mega",
        "JPM": "mega", "V": "mega", "UNH": "mega", "LLY": "mega",
        "WMT": "mega", "COST": "mega",
        # Large cap ($10-200B)
        "AMD": "large", "INTC": "large",
        "GS": "large", "BAC": "large", "MS": "large",
        "JNJ": "large", "PFE": "large", "ABBV": "large",
        "XOM": "large", "CVX": "large", "COP": "large", "SLB": "large", "OXY": "large",
        "KO": "large", "PG": "large", "MCD": "large",
        "NEE": "large", "DUK": "large", "SO": "large",
        # ETFs
        "SPY": "mega", "QQQ": "mega", "IWM": "large",
    }
    return _HARDCODED_MCAP.get(ticker, "large")  # default to large for hardcoded


def _empty_holdings_profile() -> dict[str, Any]:
    return {
        "market_cap_distribution": {
            "mega": 0.0, "large": 0.0, "mid": 0.0,
            "small": 0.0, "micro": 0.0, "unknown": 0.0,
        },
        "weighted_avg_market_cap_category": "unknown",
        "holdings_risk_score": 50,
        "sector_volatility_exposure": {"high": 0.0, "medium": 0.0, "low": 0.0},
        "speculative_holdings_ratio": 0.0,
        "index_etf_pct": 0.0,
    }
