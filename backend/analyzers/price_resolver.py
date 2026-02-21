"""Unified price resolver for all instrument types.

Consolidates the duplicated _try_get_live_price() logic from:
- backend/analyzers/portfolio_analyzer.py
- services/behavioral-mirror/features/holdings_extractor.py
- services/behavioral-mirror/api.py (inline in upload loop)

Adds options pricing via Polygon.io API (Options Starter plan).

Usage:
    from backend.analyzers.price_resolver import resolve_price, PriceResult

    result = resolve_price("NVDA", "equity")
    result = resolve_price("TSLA2821A710", "options")
    result = resolve_price("SWVXX", "money_market")
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Cache directories
CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cache"
EQUITY_CACHE_DIR = CACHE_DIR / "prices"          # shared parquet cache (existing)
OPTIONS_CACHE_DIR = CACHE_DIR / "options"         # new JSON cache for option chains


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class PriceResult:
    """Result of a price lookup. Always returned, never None."""
    price: float
    source: str       # "live", "polygon_mid", "polygon_last", "last_transaction",
                      # "par_value", "cost_basis", "nominal", "stored"
    stale: bool = False
    bid: float | None = None
    ask: float | None = None
    timestamp: datetime | None = None


@dataclass
class OptionQuote:
    """Full option quote with Greeks from Polygon.io API."""
    occ_symbol: str           # e.g. "TSLA280221C00710000" (without O: prefix)
    underlying: str
    option_type: str          # "call" or "put"
    strike: float
    expiration: str           # YYYY-MM-DD
    last: float               # day.close
    bid: float
    ask: float
    mid: float                # last_quote.midpoint
    volume: int
    open_interest: int
    implied_volatility: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    underlying_price: float | None = None   # underlying_asset.price
    break_even_price: float | None = None
    source: str = "polygon_snapshot"
    timestamp: datetime | None = None


# ---------------------------------------------------------------------------
# OCC Symbol Conversion
# ---------------------------------------------------------------------------

def wfa_to_occ(underlying: str, expiry_year: int, expiry_month: int,
               expiry_day: int, option_type: str, strike: float) -> str:
    """Convert WFA option components to OCC format.

    OCC: {UNDERLYING}{YYMMDD}{C|P}{STRIKE*1000 zero-padded to 8}

    Examples:
        TSLA, 2028, 2, 21, "call", 710.0  -> "TSLA280221C00710000"
        AAPL, 2025, 1, 17, "put", 150.0   -> "AAPL250117P00150000"
    """
    yy = expiry_year % 100
    cp = "C" if option_type.lower() == "call" else "P"
    strike_int = int(round(strike * 1000))
    return f"{underlying}{yy:02d}{expiry_month:02d}{expiry_day:02d}{cp}{strike_int:08d}"


def occ_to_polygon(occ_symbol: str) -> str:
    """Add the O: prefix that Polygon.io uses for options tickers."""
    if occ_symbol.startswith("O:"):
        return occ_symbol
    return f"O:{occ_symbol}"


def polygon_to_occ(polygon_ticker: str) -> str:
    """Strip the O: prefix from a Polygon options ticker."""
    if polygon_ticker.startswith("O:"):
        return polygon_ticker[2:]
    return polygon_ticker


def wfa_symbol_to_occ(wfa_symbol: str) -> str | None:
    """Parse a WFA symbol (e.g. TSLA2821A710) and return OCC equivalent."""
    from backend.parsers.instrument_classifier import parse_option_symbol
    opt = parse_option_symbol(wfa_symbol)
    if not opt:
        return None
    return wfa_to_occ(
        opt.underlying, opt.expiry_year, opt.expiry_month,
        opt.expiry_day, opt.option_type, opt.strike
    )


def instrument_details_to_occ(details: dict) -> str | None:
    """Convert the instrument_details JSONB (already in holdings table) to OCC.

    The holdings table stores: {"underlying": "TSLA", "strike": 710,
    "expiry": "2028-02-21", "option_type": "call", ...}
    """
    try:
        underlying = details.get("underlying")
        option_type = details.get("option_type")
        strike = float(details.get("strike", 0))
        expiry = details.get("expiry", "")

        if not all([underlying, option_type, strike, expiry]):
            return None

        parts = expiry.split("-")
        if len(parts) != 3:
            return None
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])

        return wfa_to_occ(underlying, year, month, day, option_type, strike)
    except (ValueError, TypeError, AttributeError):
        return None


def option_details_to_occ(od: Any) -> str | None:
    """Convert an OptionDetails dataclass (from PositionRecord.instrument.option_details) to OCC.

    This is the path used by portfolio_analyzer.py which works with
    PositionRecord objects rather than Supabase row dicts.
    """
    if od is None:
        return None
    try:
        return wfa_to_occ(
            od.underlying, od.expiry_year, od.expiry_month,
            od.expiry_day, od.option_type, od.strike,
        )
    except (AttributeError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Equity / ETF Pricing (yfinance) — consolidation of duplicated logic
# ---------------------------------------------------------------------------

def get_equity_price(symbol: str) -> PriceResult | None:
    """Get latest closing price for an equity or ETF via yfinance.

    This replaces the duplicated _try_get_live_price() that existed in
    both portfolio_analyzer.py and holdings_extractor.py.

    Strategy:
    1. Check shared parquet cache (< 1 day old)
    2. Fetch last 5 days from yfinance if cache is stale/missing
    3. Fall back to stale cache if yfinance fails
    4. Return None if all fails (caller handles fallback)
    """
    symbol = symbol.upper().strip()
    if not symbol:
        return None

    EQUITY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = EQUITY_CACHE_DIR / f"{symbol}.parquet"

    stale_price = None

    # Step 1: Check parquet cache
    if cache_path.exists():
        try:
            import pandas as pd
            df = pd.read_parquet(cache_path)
            cache_age = (datetime.now(timezone.utc) - datetime.fromtimestamp(
                cache_path.stat().st_mtime, tz=timezone.utc
            ))
            if "Close" in df.columns and not df.empty:
                price = float(df["Close"].iloc[-1])
                if price > 0:
                    if cache_age < timedelta(days=1):
                        return PriceResult(price=price, source="live", stale=False)
                    else:
                        stale_price = price
        except Exception as e:
            logger.debug("Cache read failed for %s: %s", symbol, e)

    # Step 2: Try yfinance
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")

        # Handle multi-level columns from newer yfinance versions
        if hasattr(hist, 'columns') and hasattr(hist.columns, 'nlevels'):
            if hist.columns.nlevels > 1:
                hist.columns = hist.columns.get_level_values(0)

        if hist is not None and not hist.empty and "Close" in hist.columns:
            price = float(hist["Close"].iloc[-1])
            if price > 0:
                # Write to cache for shared use
                try:
                    hist.to_parquet(cache_path)
                except Exception:
                    pass
                return PriceResult(price=price, source="live", stale=False)
    except ImportError:
        logger.debug("yfinance not installed")
    except Exception as e:
        logger.debug("yfinance failed for %s: %s", symbol, e)

    # Step 3: Fall back to stale cache
    if stale_price and stale_price > 0:
        return PriceResult(price=stale_price, source="live", stale=True)

    return None


# ---------------------------------------------------------------------------
# Options Pricing (Polygon.io API — Starter plan, $29/mo)
# ---------------------------------------------------------------------------

_POLYGON_BASE_URL = "https://api.polygon.io"


def _get_polygon_key() -> str | None:
    return os.environ.get("POLYGON_API_KEY")


def get_option_quote(
    occ_symbol: str,
    underlying: str,
    expiration: str,    # YYYY-MM-DD
) -> OptionQuote | None:
    """Get a live option quote from Polygon.io snapshot API.

    Strategy:
    1. Check local JSON cache (1-hour TTL)
    2. Call chain snapshot endpoint filtered by expiration (one call gets
       ALL strikes for that underlying+expiration, cache the full chain)
    3. If chain didn't match, try individual contract endpoint as fallback

    Returns None on any failure (no API key, API error, contract not found).
    """
    # Check cache first (1-hour TTL)
    cached = _read_option_cache(underlying, expiration)
    if cached is not None:
        for contract in cached:
            if _occ_matches(contract.get("occ_symbol", ""), occ_symbol):
                return _dict_to_option_quote(contract)

    api_key = _get_polygon_key()
    if not api_key:
        logger.debug("No POLYGON_API_KEY, skipping option pricing")
        return None

    try:
        import requests
    except ImportError:
        logger.debug("requests not installed, cannot call Polygon")
        return None

    # --- Strategy 1: Chain snapshot filtered by expiration ---
    try:
        resp = requests.get(
            f"{_POLYGON_BASE_URL}/v3/snapshot/options/{underlying}",
            params={
                "expiration_date": expiration,
                "apiKey": api_key,
                "limit": 250,
            },
            timeout=15,
        )

        if resp.status_code == 429:
            logger.warning("Polygon rate limit hit for %s", underlying)
            return None

        if resp.status_code in (400, 404):
            logger.debug("No chain for %s %s (HTTP %d)", underlying, expiration, resp.status_code)
            # Don't return yet, try individual contract below
        elif resp.ok:
            data = resp.json()
            results = data.get("results", [])

            if results:
                quotes_dicts = []
                target_quote = None

                for contract in results:
                    q_dict = _parse_polygon_contract(contract, underlying, expiration)
                    quotes_dicts.append(q_dict)

                    if _occ_matches(q_dict["occ_symbol"], occ_symbol):
                        target_quote = _dict_to_option_quote(q_dict)

                # Cache the full chain
                if quotes_dicts:
                    _write_option_cache(underlying, expiration, quotes_dicts)

                if target_quote:
                    return target_quote

    except Exception as e:
        logger.warning("Polygon chain snapshot failed for %s %s: %s", underlying, expiration, e)

    # --- Strategy 2: Individual contract snapshot as fallback ---
    try:
        polygon_ticker = occ_to_polygon(occ_symbol)
        resp = requests.get(
            f"{_POLYGON_BASE_URL}/v3/snapshot/options/{underlying}/{polygon_ticker}",
            params={"apiKey": api_key},
            timeout=10,
        )

        if resp.ok:
            data = resp.json()
            result = data.get("results", {})
            if result:
                q_dict = _parse_polygon_contract(result, underlying, expiration)
                return _dict_to_option_quote(q_dict)
    except Exception as e:
        logger.warning("Polygon individual contract failed for %s: %s", occ_symbol, e)

    return None


def _parse_polygon_contract(contract: dict, underlying: str, expiration: str) -> dict:
    """Parse a single Polygon contract response into our internal dict format."""
    details = contract.get("details", {})
    greeks = contract.get("greeks") or {}
    last_quote = contract.get("last_quote") or {}
    day = contract.get("day") or {}
    ua = contract.get("underlying_asset") or {}

    bid = _safe_float(last_quote.get("bid")) or 0.0
    ask = _safe_float(last_quote.get("ask")) or 0.0
    mid = _safe_float(last_quote.get("midpoint")) or 0.0
    last = _safe_float(day.get("close")) or 0.0

    # Compute mid if Polygon didn't provide midpoint
    if mid == 0 and bid > 0 and ask > 0:
        mid = round((bid + ask) / 2, 4)

    polygon_ticker = details.get("ticker", "")
    contract_occ = polygon_to_occ(polygon_ticker)

    return {
        "occ_symbol": contract_occ,
        "polygon_ticker": polygon_ticker,
        "underlying": underlying,
        "option_type": (details.get("contract_type") or "").lower(),
        "strike": _safe_float(details.get("strike_price")) or 0.0,
        "expiration": details.get("expiration_date", expiration),
        "last": last,
        "bid": bid,
        "ask": ask,
        "mid": mid,
        "volume": int(day.get("volume") or 0),
        "open_interest": int(contract.get("open_interest") or 0),
        "implied_volatility": _safe_float(contract.get("implied_volatility")),
        "delta": _safe_float(greeks.get("delta")),
        "gamma": _safe_float(greeks.get("gamma")),
        "theta": _safe_float(greeks.get("theta")),
        "vega": _safe_float(greeks.get("vega")),
        "underlying_price": _safe_float(ua.get("price")),
        "break_even_price": _safe_float(contract.get("break_even_price")),
        "source": "polygon_snapshot",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _occ_matches(contract_occ: str, target_occ: str) -> bool:
    """Check if two OCC symbols match (both should be without O: prefix)."""
    c = contract_occ.replace("O:", "").strip().upper()
    t = target_occ.replace("O:", "").strip().upper()

    if c == t:
        return True

    # Component-level fallback: compare strike + type + date from the OCC string
    # OCC format: {UNDERLYING}{YYMMDD}{C|P}{STRIKE*1000 padded to 8}
    try:
        c_type = c[-9]
        c_strike = int(c[-8:])
        t_type = t[-9]
        t_strike = int(t[-8:])
        c_date = c[-15:-9]
        t_date = t[-15:-9]
        if c_type == t_type and c_strike == t_strike and c_date == t_date:
            return True
    except (IndexError, ValueError):
        pass

    return False


def _dict_to_option_quote(d: dict) -> OptionQuote:
    """Convert a cached dict back to an OptionQuote."""
    ts = d.get("timestamp")
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            ts = None
    return OptionQuote(
        occ_symbol=d.get("occ_symbol", ""),
        underlying=d.get("underlying", ""),
        option_type=d.get("option_type", ""),
        strike=d.get("strike", 0.0),
        expiration=d.get("expiration", ""),
        last=d.get("last", 0.0),
        bid=d.get("bid", 0.0),
        ask=d.get("ask", 0.0),
        mid=d.get("mid", 0.0),
        volume=d.get("volume", 0),
        open_interest=d.get("open_interest", 0),
        implied_volatility=d.get("implied_volatility"),
        delta=d.get("delta"),
        gamma=d.get("gamma"),
        theta=d.get("theta"),
        vega=d.get("vega"),
        underlying_price=d.get("underlying_price"),
        break_even_price=d.get("break_even_price"),
        source=d.get("source", "polygon_snapshot"),
        timestamp=ts,
    )


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return f if f == f else None  # NaN check
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Option Cache (JSON, 1-hour TTL)
# ---------------------------------------------------------------------------

def _option_cache_path(underlying: str, expiration: str) -> Path:
    OPTIONS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_exp = expiration.replace("/", "-")
    return OPTIONS_CACHE_DIR / f"{underlying}_{safe_exp}.json"


def _read_option_cache(underlying: str, expiration: str) -> list[dict] | None:
    path = _option_cache_path(underlying, expiration)
    if not path.exists():
        return None
    try:
        age = datetime.now(timezone.utc) - datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        )
        if age > timedelta(hours=1):
            return None
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _write_option_cache(underlying: str, expiration: str, quotes: list[dict]) -> None:
    path = _option_cache_path(underlying, expiration)
    try:
        with open(path, "w") as f:
            json.dump(quotes, f)
    except Exception as e:
        logger.debug("Option cache write failed: %s", e)


# ---------------------------------------------------------------------------
# Unified Resolver (main entry point)
# ---------------------------------------------------------------------------

def resolve_price(
    symbol: str,
    instrument_type: str,
    pos: Any = None,
    instrument_details: dict | None = None,
) -> PriceResult:
    """Resolve the current market price for any instrument.

    This is THE function everything calls. It ALWAYS returns a PriceResult,
    never None. Falls back through multiple strategies.

    Args:
        symbol: Ticker (can be WFA option format like TSLA2821A710)
        instrument_type: "equity", "etf", "options", "money_market",
                          "cash", "muni_bond", "corp_bond", "structured"
        pos: Optional PositionRecord (used for fallback to transaction price)
        instrument_details: Optional dict from holdings table JSONB
                            (has underlying/strike/expiry/option_type)
    """
    # --- Fixed-valuation instruments ---
    if instrument_type in ("money_market", "cash"):
        return PriceResult(price=1.0, source="nominal")

    if instrument_type in ("muni_bond", "corp_bond"):
        if pos and hasattr(pos, "face_value") and pos.face_value > 0:
            return PriceResult(price=pos.face_value, source="par_value")
        return PriceResult(price=abs(pos.quantity) if pos else 0.0, source="par_value")

    if instrument_type == "structured":
        cb = pos.cost_basis if (pos and hasattr(pos, "cost_basis")) else 0.0
        return PriceResult(price=cb if cb > 0 else 0.0, source="cost_basis")

    # --- Options: Polygon -> last_transaction fallback ---
    if instrument_type == "options":
        return _resolve_option_price(symbol, pos, instrument_details)

    # --- Equities & ETFs: yfinance -> last_transaction fallback ---
    result = get_equity_price(symbol)
    if result:
        return result

    return PriceResult(
        price=_fallback_txn_price(pos),
        source="last_transaction",
    )


def _resolve_option_price(
    symbol: str,
    pos: Any = None,
    instrument_details: dict | None = None,
) -> PriceResult:
    """Resolve option price: Polygon -> transaction fallback."""

    underlying = None
    expiration = None
    occ = None

    # Try instrument_details dict first (already parsed, stored in DB)
    if instrument_details:
        occ = instrument_details_to_occ(instrument_details)
        underlying = instrument_details.get("underlying")
        expiration = instrument_details.get("expiry")

    # Try PositionRecord.instrument.option_details (in-memory from CSV parsing)
    if not occ and pos and hasattr(pos, "instrument"):
        od = getattr(pos.instrument, "option_details", None)
        if od:
            occ = option_details_to_occ(od)
            underlying = od.underlying
            expiration = f"{od.expiry_year}-{od.expiry_month:02d}-{od.expiry_day:02d}"

    # Fall back to parsing the WFA symbol directly
    if not occ:
        from backend.parsers.instrument_classifier import parse_option_symbol
        opt = parse_option_symbol(symbol)
        if opt:
            occ = wfa_to_occ(
                opt.underlying, opt.expiry_year, opt.expiry_month,
                opt.expiry_day, opt.option_type, opt.strike
            )
            underlying = opt.underlying
            expiration = f"{opt.expiry_year}-{opt.expiry_month:02d}-{opt.expiry_day:02d}"

    if not occ or not underlying or not expiration:
        return PriceResult(price=_fallback_txn_price(pos), source="last_transaction")

    # Check if expired
    try:
        parts = expiration.split("-")
        expiry_date = datetime(int(parts[0]), int(parts[1]), int(parts[2]),
                                hour=16, tzinfo=timezone.utc)  # market close
        if expiry_date < datetime.now(timezone.utc):
            # Expired: transaction price IS the correct value
            return PriceResult(price=_fallback_txn_price(pos), source="last_transaction")
    except (ValueError, IndexError):
        pass

    # Try Polygon
    quote = get_option_quote(occ, underlying, expiration)
    if quote:
        if quote.mid > 0:
            return PriceResult(
                price=quote.mid, source="polygon_mid",
                bid=quote.bid, ask=quote.ask,
                timestamp=quote.timestamp,
            )
        elif quote.last > 0:
            return PriceResult(
                price=quote.last, source="polygon_last",
                stale=True, timestamp=quote.timestamp,
            )

    # Fallback
    return PriceResult(price=_fallback_txn_price(pos), source="last_transaction")


def _fallback_txn_price(pos: Any) -> float:
    """Extract last transaction price from a PositionRecord."""
    if pos is None:
        return 0.0
    if hasattr(pos, "transactions"):
        for txn in reversed(pos.transactions):
            if hasattr(txn, "price") and txn.price > 0:
                return txn.price
    return 0.0
