"""Dynamic ticker resolution service with yfinance integration and caching.

Resolves sector, market cap category, and historical price data for ANY ticker,
not just the hardcoded 50. Uses a three-tier approach:
1. Fast path: hardcoded map for known tickers
2. Cache: JSON metadata + parquet price data (30-day TTL)
3. yfinance: live resolution for unknown tickers
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    yf = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_DIR = DATA_DIR / "cache"
METADATA_CACHE_PATH = CACHE_DIR / "ticker_metadata.json"
PRICES_CACHE_DIR = CACHE_DIR / "prices"
CACHE_TTL_DAYS = 30

# Fast path: hardcoded map for the 50 known tickers
KNOWN_SECTORS: dict[str, str] = {
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology",
    "GOOGL": "Technology", "AMZN": "Technology", "META": "Technology",
    "TSLA": "Technology", "AMD": "Technology", "INTC": "Technology",
    "AVGO": "Technology",
    "JPM": "Financials", "GS": "Financials", "BAC": "Financials",
    "MS": "Financials", "V": "Financials",
    "JNJ": "Healthcare", "UNH": "Healthcare", "PFE": "Healthcare",
    "ABBV": "Healthcare", "LLY": "Healthcare",
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy",
    "SLB": "Energy", "OXY": "Energy",
    "KO": "Consumer", "PG": "Consumer", "WMT": "Consumer",
    "COST": "Consumer", "MCD": "Consumer",
    "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities",
    "SPY": "Index", "QQQ": "Index", "IWM": "Index",
}

# yfinance sector -> our sector mapping
_SECTOR_MAP: dict[str, str] = {
    "Technology": "Technology",
    "Communication Services": "Technology",
    "Consumer Cyclical": "Consumer",
    "Consumer Defensive": "Consumer",
    "Financial Services": "Financials",
    "Healthcare": "Healthcare",
    "Energy": "Energy",
    "Utilities": "Utilities",
    "Industrials": "Industrials",
    "Basic Materials": "Materials",
    "Real Estate": "Real Estate",
}

_MARKET_CAP_CATEGORIES = [
    (200_000_000_000, "mega"),
    (10_000_000_000, "large"),
    (2_000_000_000, "mid"),
    (300_000_000, "small"),
    (0, "micro"),
]

# Module-level cache for loaded metadata
_metadata_cache: dict[str, dict[str, Any]] | None = None


def _load_metadata_cache() -> dict[str, dict[str, Any]]:
    """Load ticker metadata from disk cache."""
    global _metadata_cache
    if _metadata_cache is not None:
        return _metadata_cache

    if METADATA_CACHE_PATH.exists():
        try:
            with open(METADATA_CACHE_PATH) as f:
                _metadata_cache = json.load(f)
                return _metadata_cache
        except (json.JSONDecodeError, IOError):
            pass

    _metadata_cache = {}
    return _metadata_cache


def _save_metadata_cache(cache: dict[str, dict[str, Any]]) -> None:
    """Save ticker metadata to disk cache."""
    global _metadata_cache
    _metadata_cache = cache
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(METADATA_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2, default=str)


def _is_cache_fresh(entry: dict[str, Any]) -> bool:
    """Check if a cache entry is still within TTL."""
    cached_at = entry.get("cached_at")
    if not cached_at:
        return False
    try:
        ts = datetime.fromisoformat(cached_at)
        age_days = (datetime.now(timezone.utc) - ts).days
        return age_days < CACHE_TTL_DAYS
    except (ValueError, TypeError):
        return False


def _classify_market_cap(market_cap: float | None) -> str:
    """Classify market cap into category."""
    if not market_cap:
        return "unknown"
    for threshold, label in _MARKET_CAP_CATEGORIES:
        if market_cap >= threshold:
            return label
    return "micro"


def _fetch_ticker_info(symbol: str) -> dict[str, Any] | None:
    """Fetch ticker info from yfinance."""
    if yf is None:
        return None
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        if not info or info.get("regularMarketPrice") is None:
            return None

        yf_sector = info.get("sector", "")
        sector = _SECTOR_MAP.get(yf_sector, yf_sector or "Unknown")
        market_cap = info.get("marketCap")

        return {
            "symbol": symbol.upper(),
            "sector": sector,
            "industry": info.get("industry", "Unknown"),
            "market_cap": market_cap,
            "market_cap_category": _classify_market_cap(market_cap),
            "name": info.get("shortName", symbol),
            "exchange": info.get("exchange", "Unknown"),
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.warning("Failed to fetch info for %s: %s", symbol, e)
        return None


def resolve_ticker(symbol: str) -> dict[str, Any]:
    """Resolve a single ticker to sector, market cap, etc.

    Returns dict with keys: symbol, sector, industry, market_cap,
    market_cap_category, name, exchange, source.
    """
    symbol = symbol.upper().strip()

    # Tier 1: Hardcoded fast path
    if symbol in KNOWN_SECTORS:
        return {
            "symbol": symbol,
            "sector": KNOWN_SECTORS[symbol],
            "industry": "Known",
            "market_cap": None,
            "market_cap_category": "known",
            "name": symbol,
            "exchange": "Known",
            "source": "hardcoded",
        }

    # Tier 2: Cache
    cache = _load_metadata_cache()
    if symbol in cache and _is_cache_fresh(cache[symbol]):
        result = dict(cache[symbol])
        result["source"] = "cache"
        return result

    # Tier 3: yfinance
    info = _fetch_ticker_info(symbol)
    if info:
        cache[symbol] = info
        _save_metadata_cache(cache)
        info["source"] = "yfinance"
        return info

    # Fallback: return Unknown (never "Other")
    fallback = {
        "symbol": symbol,
        "sector": "Unknown",
        "industry": "Unknown",
        "market_cap": None,
        "market_cap_category": "unknown",
        "name": symbol,
        "exchange": "Unknown",
        "source": "fallback",
    }
    cache[symbol] = {**fallback, "cached_at": datetime.now(timezone.utc).isoformat()}
    _save_metadata_cache(cache)
    return fallback


def resolve_batch(symbols: list[str]) -> dict[str, dict[str, Any]]:
    """Resolve a batch of tickers efficiently.

    Uses hardcoded map and cache first, then fetches remaining from yfinance.
    Logs timing: "Resolved 8 tickers (3 cached, 5 fetched) in 4.2s".
    """
    start = time.time()
    results: dict[str, dict[str, Any]] = {}
    to_fetch: list[str] = []
    n_cached = 0
    n_hardcoded = 0

    unique_symbols = list(set(s.upper().strip() for s in symbols))

    for sym in unique_symbols:
        if sym in KNOWN_SECTORS:
            results[sym] = resolve_ticker(sym)
            n_hardcoded += 1
        else:
            cache = _load_metadata_cache()
            if sym in cache and _is_cache_fresh(cache[sym]):
                result = dict(cache[sym])
                result["source"] = "cache"
                results[sym] = result
                n_cached += 1
            else:
                to_fetch.append(sym)

    # Fetch remaining from yfinance
    n_fetched = 0
    for sym in to_fetch:
        info = resolve_ticker(sym)  # This handles the yfinance call + caching
        results[sym] = info
        if info.get("source") == "yfinance":
            n_fetched += 1

    elapsed = time.time() - start
    logger.info(
        "Resolved %d tickers (%d hardcoded, %d cached, %d fetched) in %.1fs",
        len(unique_symbols), n_hardcoded, n_cached, n_fetched, elapsed,
    )
    return results


def get_historical_data(
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame | None:
    """Get historical OHLCV data with computed indicators for a ticker.

    Checks price cache first. Downloads via yfinance if needed.
    Returns DataFrame with columns: Open, High, Low, Close, Volume,
    MA20, MA50, RSI, VolRatio, Return, High10.
    """
    symbol = symbol.upper().strip()
    PRICES_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = PRICES_CACHE_DIR / f"{symbol}.parquet"

    # Check cache
    if cache_path.exists():
        try:
            df = pd.read_parquet(cache_path)
            cache_age_days = (datetime.now(timezone.utc) - datetime.fromtimestamp(
                cache_path.stat().st_mtime, tz=timezone.utc
            )).days
            if cache_age_days < CACHE_TTL_DAYS:
                return df
        except Exception:
            pass

    if yf is None:
        logger.warning("yfinance not installed — cannot fetch %s", symbol)
        return None

    start = start_date or "2024-01-01"
    end = end_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        df = yf.download(symbol, start=start, end=end, progress=False, auto_adjust=True)
        if df.empty:
            logger.warning("No historical data for %s", symbol)
            return None

        # yfinance may return MultiIndex columns for single ticker
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Compute indicators
        close = df["Close"]
        volume = df["Volume"]

        df["MA20"] = close.rolling(20).mean()
        df["MA50"] = close.rolling(50).mean()
        df["RSI"] = _compute_rsi(close)
        vol_ma20 = volume.rolling(20).mean()
        df["VolRatio"] = volume / vol_ma20.replace(0, np.nan)
        df["Return"] = close.pct_change()
        df["High10"] = close.rolling(10).max()

        # Ensure UTC index
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")

        df.to_parquet(cache_path)
        logger.info("Cached price data for %s (%d rows)", symbol, len(df))
        return df
    except Exception as e:
        logger.warning("Failed to download %s: %s", symbol, e)
        return None


def get_earnings_dates(symbol: str) -> list[pd.Timestamp]:
    """Get approximate earnings dates for a ticker.

    Uses yfinance calendar if available, falls back to quarterly approximation.
    """
    # Default quarterly pattern (3rd week of reporting month)
    _DEFAULT_MONTHS = [1, 4, 7, 10]

    try:
        if yf is not None:
            ticker = yf.Ticker(symbol)
            cal = ticker.calendar
            if cal is not None and not (isinstance(cal, pd.DataFrame) and cal.empty):
                # yfinance calendar returns upcoming earnings
                if isinstance(cal, dict) and "Earnings Date" in cal:
                    dates = cal["Earnings Date"]
                    if isinstance(dates, list):
                        return [pd.Timestamp(d, tz="UTC") for d in dates]
    except Exception:
        pass

    # Fallback: approximate quarterly dates
    dates: list[pd.Timestamp] = []
    for year in range(2024, 2027):
        for month in _DEFAULT_MONTHS:
            dates.append(pd.Timestamp(year=year, month=month, day=20, tz="UTC"))
    return dates


def enrich_market_data(
    existing_market_data: pd.DataFrame | None,
    symbols: list[str],
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame | None:
    """Enrich existing market data with additional tickers.

    For tickers already in market_data, skip. For new tickers,
    fetch historical data and merge into the existing DataFrame.
    Returns the enriched DataFrame.
    """
    if existing_market_data is None:
        return None

    missing = []
    for sym in set(s.upper().strip() for s in symbols):
        if f"{sym}_Close" not in existing_market_data.columns:
            missing.append(sym)

    if not missing:
        return existing_market_data

    logger.info("Enriching market data with %d new tickers: %s", len(missing), missing)
    enriched = existing_market_data.copy()
    base_index = enriched.index

    for sym in missing:
        hist = get_historical_data(sym, start_date, end_date)
        if hist is None or hist.empty:
            continue

        # Reindex to match existing market data, forward-fill small gaps
        hist = hist.reindex(base_index).ffill(limit=3)

        enriched[f"{sym}_Open"] = hist.get("Open")
        enriched[f"{sym}_High"] = hist.get("High")
        enriched[f"{sym}_Low"] = hist.get("Low")
        enriched[f"{sym}_Close"] = hist.get("Close")
        enriched[f"{sym}_Volume"] = hist.get("Volume")
        enriched[f"{sym}_MA20"] = hist.get("MA20")
        enriched[f"{sym}_MA50"] = hist.get("MA50")
        enriched[f"{sym}_RSI"] = hist.get("RSI")
        enriched[f"{sym}_VolRatio"] = hist.get("VolRatio")
        enriched[f"{sym}_Return"] = hist.get("Return")
        enriched[f"{sym}_High10"] = hist.get("High10")

    return enriched


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Compute RSI indicator."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))
