"""
Portfolio analyzer: compute structured metrics + Claude narrative analysis.

Takes the output of the WFA parser pipeline (HoldingsSnapshot, transactions)
and produces:
1. Locally-computed structured metrics (asset allocation, sector exposure, etc.)
2. Claude-generated narrative analysis with specific insights
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import math

from backend.parsers.instrument_classifier import parse_option_symbol
from backend.parsers.holdings_reconstructor import (
    HoldingsSnapshot,
    PositionRecord,
    AccountSummary,
)
from backend.parsers.wfa_activity import ParsedTransaction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sector mapping for known tickers
# ---------------------------------------------------------------------------

_SECTOR_MAP = {
    # Tech
    "AAPL": "Technology", "NVDA": "Technology", "MSFT": "Technology",
    "GOOG": "Technology", "GOOGL": "Technology", "TSLA": "Technology",
    "APP": "Technology", "HOOD": "Technology", "CRDO": "Technology",
    "ASML": "Technology", "TSM": "Technology", "MU": "Technology",
    "SNDK": "Technology", "INTU": "Technology", "CRM": "Technology",
    "MPWR": "Technology", "LRCX": "Technology", "APH": "Technology",
    "AMD": "Technology", "INTC": "Technology", "ENTG": "Technology",
    "ORCL": "Technology", "MRVL": "Technology",
    # Semiconductor ETFs → Technology
    "SOXX": "Technology", "SMH": "Technology",
    # Energy
    "XLE": "Energy", "CEG": "Energy", "BE": "Energy",
    # Healthcare
    "XBI": "Healthcare", "ABBV": "Healthcare", "AZN": "Healthcare",
    # Industrials
    "DE": "Industrials", "BA": "Industrials", "NOC": "Industrials",
    "KTOS": "Industrials", "VRT": "Industrials", "AMT": "Industrials",
    # Financials
    "AXP": "Financials", "MS": "Financials", "USB": "Financials",
    "PGR": "Financials",
    # Consumer
    "COST": "Consumer", "AMZN": "Consumer",
    # Broad Market
    "VOO": "Broad Market", "VTI": "Broad Market", "VWO": "Broad Market",
    "VXUS": "Broad Market", "EFA": "Broad Market", "SPY": "Broad Market",
    # Precious Metals
    "GLD": "Precious Metals", "SLV": "Precious Metals",
    # Nuclear/Uranium
    "LEU": "Nuclear/Uranium",
    # Real Estate
    "VNQ": "Real Estate", "SCHH": "Real Estate",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_portfolio(
    snapshot: HoldingsSnapshot,
    transactions: list[ParsedTransaction],
    api_key: str | None = None,
) -> dict[str, Any]:
    """
    Full portfolio analysis: compute metrics + generate Claude narrative.

    Returns dict with 'metrics' and 'analysis' keys.
    """
    metrics = compute_metrics(snapshot, transactions)
    analysis = generate_analysis(metrics, api_key=api_key)
    return {
        "metrics": metrics,
        "analysis": analysis,
    }


def compute_metrics(
    snapshot: HoldingsSnapshot,
    transactions: list[ParsedTransaction],
) -> dict[str, Any]:
    """Compute structured portfolio metrics from parsed data."""

    # Clear the session-level live price cache at the start of each analysis
    _live_price_session_cache.clear()

    asset_allocation, price_sources = _compute_asset_allocation(snapshot)
    sector_exposure = _compute_sector_exposure(snapshot)
    multi_account = _compute_multi_account(snapshot)
    income_summary = _compute_income_summary(snapshot, transactions)
    options_summary = _compute_options_summary(snapshot)
    muni_bonds = _compute_muni_bonds(snapshot)
    tax_jurisdiction = _detect_tax_jurisdiction(snapshot)

    metrics = {
        "asset_allocation": asset_allocation,
        "sector_exposure": sector_exposure,
        "multi_account_breakdown": multi_account,
        "income_summary": income_summary,
        "options_summary": options_summary,
        "muni_bond_holdings": muni_bonds,
        "detected_tax_jurisdiction": tax_jurisdiction,
    }

    # Compute flat feature vector on top of structured metrics
    features = compute_portfolio_features(snapshot, transactions, metrics)
    metrics["portfolio_features"] = features

    # Detect portfolio completeness from CSV activity window
    total_value = asset_allocation.get("_total_estimated_value", 0.0)
    metrics["portfolio_completeness"] = _compute_portfolio_completeness(
        snapshot, transactions, total_value,
    )

    # Price source metadata for data quality indicators
    metrics["_price_sources"] = price_sources
    metrics["_live_price_count"] = sum(
        1 for s in price_sources.values() if s == "live"
    )
    metrics["_stale_price_count"] = sum(
        1 for s in price_sources.values() if s == "last_transaction"
    )

    return metrics


def generate_analysis(
    metrics: dict[str, Any],
    api_key: str | None = None,
) -> dict[str, Any]:
    """Send metrics to Claude API for narrative analysis."""
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        logger.warning("No ANTHROPIC_API_KEY set; returning placeholder analysis")
        return _placeholder_analysis()

    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(metrics)

    # Call Claude API with one retry
    for attempt in range(2):
        try:
            result = _call_claude(key, system_prompt, user_prompt)
            result["_generated_by"] = "claude"
            return result
        except Exception as e:
            logger.warning("Claude API call failed (attempt %d): %s", attempt + 1, e)
            if attempt == 0:
                time.sleep(2)

    logger.error("Claude API failed after 2 attempts; returning placeholder")
    return _placeholder_analysis()


# ---------------------------------------------------------------------------
# Metric computation helpers
# ---------------------------------------------------------------------------


def _get_last_price(pos: PositionRecord) -> float:
    """Get the most recent transaction price for a position."""
    for txn in reversed(pos.transactions):
        if txn.price > 0:
            return txn.price
    return 0.0


# ---------------------------------------------------------------------------
# Live price resolution
# ---------------------------------------------------------------------------

# Cache of live prices within a single analysis run to avoid redundant lookups.
# Keys are uppercase symbols, values are (price, hit) or None.
_live_price_session_cache: dict[str, float | None] = {}


def _try_get_live_price(symbol: str) -> float | None:
    """Get latest close price via yfinance with parquet caching.

    Reads the same parquet cache written by the behavioral-mirror's
    ticker_resolver. Uses a 1-day TTL for pricing accuracy (tighter
    than the 30-day TTL used for behavioral analysis).

    Returns None on any failure so callers fall back to transaction price.
    """
    sym = symbol.upper().strip()

    # Session-level cache to avoid repeated lookups within one analysis run
    if sym in _live_price_session_cache:
        return _live_price_session_cache[sym]

    price: float | None = None

    try:
        import pandas as pd  # noqa: F811 — available in backend deps

        # Check existing parquet cache (shared with ticker_resolver)
        # Two possible cache locations: behavioral-mirror's data dir and project root
        cache_dirs = [
            Path(__file__).resolve().parent.parent.parent
            / "services" / "behavioral-mirror" / "data" / "cache" / "prices",
            Path("data") / "cache" / "prices",
        ]

        for cache_dir in cache_dirs:
            cache_path = cache_dir / f"{sym}.parquet"
            if not cache_path.exists():
                continue
            try:
                df = pd.read_parquet(cache_path)
                cache_age = (
                    datetime.now(timezone.utc)
                    - datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc)
                ).days
                if cache_age < 1 and "Close" in df.columns and not df.empty:
                    p = float(df["Close"].iloc[-1])
                    if p > 0:
                        price = p
                        break
            except Exception:
                continue

        # If cache miss/stale, try yfinance directly (minimal 5-day fetch)
        if price is None:
            try:
                import yfinance as yf

                ticker = yf.Ticker(sym)
                hist = ticker.history(period="5d")
                if hist is not None and not hist.empty and "Close" in hist.columns:
                    p = float(hist["Close"].iloc[-1])
                    if p > 0:
                        price = p

                        # Write to cache for future runs / shared with ticker_resolver
                        for cache_dir in cache_dirs:
                            try:
                                cache_dir.mkdir(parents=True, exist_ok=True)
                                hist.to_parquet(cache_dir / f"{sym}.parquet")
                                break
                            except Exception:
                                continue
            except ImportError:
                pass  # yfinance not installed — graceful fallback
            except Exception:
                pass  # network error, bad ticker, etc.

    except Exception:
        pass

    _live_price_session_cache[sym] = price
    return price


def _get_current_price(symbol: str, pos: PositionRecord) -> tuple[float, str]:
    """Get current market price for a position.

    Returns (price, source) where source is one of:
    - "live"              : yfinance/cache data (latest close price)
    - "last_transaction"  : fallback to last trade price from CSV
    - "par_value"         : bonds using face value
    - "cost_basis"        : structured products using cost basis
    - "nominal"           : cash/money market at $1.00
    """
    itype = pos.instrument.instrument_type

    # Fixed-value instrument types — no price lookup needed
    if itype == "money_market":
        return (1.0, "nominal")
    if itype == "cash":
        return (1.0, "nominal")
    if itype in ("muni_bond", "corp_bond"):
        return (0.0, "par_value")  # bonds use face_value, not per-share price
    if itype == "structured":
        return (0.0, "cost_basis")  # structured uses cost_basis directly

    # Options: always use last transaction price (option symbols aren't on yfinance)
    if itype == "options":
        return (_get_last_price(pos), "last_transaction")

    # Equity/ETF: try live price first
    live_price = _try_get_live_price(symbol)
    if live_price is not None:
        return (live_price, "live")

    # Fallback to last transaction price
    return (_get_last_price(pos), "last_transaction")


def _estimate_market_value(pos: PositionRecord) -> tuple[float, str]:
    """Estimate current market value of a position.

    Returns (market_value, price_source) where price_source indicates
    how the price was determined.
    """
    itype = pos.instrument.instrument_type

    if itype == "money_market":
        return (abs(pos.quantity) * 1.0, "nominal")
    if itype == "cash":
        return (abs(pos.quantity), "nominal")
    # Bonds: use face value (par value) as market value proxy
    if itype in ("muni_bond", "corp_bond"):
        value = pos.face_value if pos.face_value > 0 else abs(pos.quantity)
        return (value, "par_value")
    # Structured products: use cost basis (actual amount paid)
    if itype == "structured":
        value = pos.cost_basis if pos.cost_basis > 0 else 0.0
        return (value, "cost_basis")
    if pos.quantity == 0:
        return (0.0, "nominal")

    price, source = _get_current_price(pos.symbol, pos)

    if itype == "options":
        # Options prices are per-share, contracts are 100 shares
        return (abs(pos.quantity) * price * 100, source)
    return (abs(pos.quantity) * price, source)


def _compute_asset_allocation(
    snapshot: HoldingsSnapshot,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Group positions by instrument type and compute market values.

    Returns (allocation_dict, price_sources) where price_sources maps
    symbol -> source string for every valued position.
    """
    allocation: dict[str, dict] = defaultdict(
        lambda: {"market_value": 0.0, "positions": 0, "symbols": []}
    )
    total_value = 0.0
    price_sources: dict[str, str] = {}

    for key, pos in snapshot.positions.items():
        if pos.quantity == 0 and pos.instrument.instrument_type not in ("cash", "money_market"):
            continue

        mv, source = _estimate_market_value(pos)
        itype = pos.instrument.instrument_type
        allocation[itype]["market_value"] += mv
        allocation[itype]["positions"] += 1
        if pos.symbol not in allocation[itype]["symbols"]:
            allocation[itype]["symbols"].append(pos.symbol)
        total_value += mv
        price_sources[pos.symbol] = source

    result = {}
    for itype, data in allocation.items():
        pct = (data["market_value"] / total_value * 100) if total_value > 0 else 0.0
        result[itype] = {
            "market_value": round(data["market_value"], 2),
            "percentage": round(pct, 1),
            "positions": data["positions"],
            "symbols": sorted(data["symbols"]),
        }

    result["_total_estimated_value"] = round(total_value, 2)
    return result, price_sources


def _get_sector(symbol: str, pos: PositionRecord) -> str:
    """Get sector for a symbol, checking option underlying if applicable."""
    if pos.instrument.instrument_type == "options":
        opt = parse_option_symbol(symbol)
        if opt:
            return _SECTOR_MAP.get(opt.underlying, "Unknown")
    return _SECTOR_MAP.get(symbol, "Unknown")


def _compute_sector_exposure(snapshot: HoldingsSnapshot) -> dict[str, Any]:
    """Classify positions by sector."""
    sectors: dict[str, dict] = defaultdict(
        lambda: {"market_value": 0.0, "symbols": [], "accounts": set()}
    )

    # Only compute sector exposure for equities, ETFs, and options
    _SECTOR_TYPES = {"equity", "etf", "options"}

    for key, pos in snapshot.positions.items():
        if pos.instrument.instrument_type not in _SECTOR_TYPES:
            continue
        if pos.quantity == 0:
            continue

        sector = _get_sector(pos.symbol, pos)
        mv, _source = _estimate_market_value(pos)
        sectors[sector]["market_value"] += mv
        if pos.symbol not in sectors[sector]["symbols"]:
            sectors[sector]["symbols"].append(pos.symbol)
        sectors[sector]["accounts"].add(pos.account)

    result = {}
    for sector, data in sorted(sectors.items(), key=lambda x: -x[1]["market_value"]):
        result[sector] = {
            "market_value": round(data["market_value"], 2),
            "symbols": sorted(data["symbols"]),
            "accounts": sorted(data["accounts"]),
        }
    return result


def _compute_multi_account(snapshot: HoldingsSnapshot) -> dict[str, Any]:
    """Per-account breakdown + cross-account exposure detection."""
    accounts = {}
    for name, acct in snapshot.accounts.items():
        # Find positions in this account with non-zero quantity
        acct_positions = [
            pos for pos in snapshot.positions.values()
            if pos.account == name
            and (pos.quantity != 0 or pos.instrument.instrument_type in ("cash", "money_market"))
        ]
        acct_positions.sort(key=lambda p: _estimate_market_value(p)[0], reverse=True)

        total_value = sum(_estimate_market_value(p)[0] for p in acct_positions)

        # Dominant asset types
        type_values: dict[str, float] = defaultdict(float)
        for p in acct_positions:
            type_values[p.instrument.instrument_type] += _estimate_market_value(p)[0]
        dominant_types = sorted(type_values.items(), key=lambda x: -x[1])[:3]

        largest = []
        for p in acct_positions[:5]:
            mv, _source = _estimate_market_value(p)
            if mv > 0:
                largest.append({
                    "symbol": p.symbol,
                    "type": p.instrument.instrument_type,
                    "quantity": round(p.quantity, 2),
                    "market_value": round(mv, 2),
                })

        accounts[name] = {
            "account_type": acct.account_type,
            "total_value": round(total_value, 2),
            "position_count": len(acct_positions),
            "dominant_types": [{"type": t, "value": round(v, 2)} for t, v in dominant_types],
            "largest_positions": largest,
            "total_bought": round(acct.total_bought, 2),
            "total_sold": round(acct.total_sold, 2),
            "dividends": round(acct.total_dividends, 2),
            "interest": round(acct.total_interest, 2),
            "fees": round(acct.total_fees, 2),
        }

    # Cross-account exposure: find symbols/underlyings in multiple accounts or types
    symbol_accounts: dict[str, dict] = defaultdict(
        lambda: {"accounts": set(), "types": set(), "total_value": 0.0}
    )
    for key, pos in snapshot.positions.items():
        symbol = pos.symbol
        if pos.instrument.instrument_type == "options":
            opt = parse_option_symbol(symbol)
            if opt:
                symbol = opt.underlying

        symbol_accounts[symbol]["accounts"].add(pos.account)
        symbol_accounts[symbol]["types"].add(pos.instrument.instrument_type)
        symbol_accounts[symbol]["total_value"] += _estimate_market_value(pos)[0]

    cross_account = {}
    for sym, data in symbol_accounts.items():
        if len(data["accounts"]) > 1 or len(data["types"]) > 1:
            cross_account[sym] = {
                "accounts": sorted(data["accounts"]),
                "instrument_types": sorted(data["types"]),
                "total_exposure": round(data["total_value"], 2),
            }

    return {
        "accounts": accounts,
        "cross_account_exposure": cross_account,
    }


def _compute_income_summary(
    snapshot: HoldingsSnapshot,
    transactions: list[ParsedTransaction],
) -> dict[str, Any]:
    """Compute income summary: dividends, interest (muni vs other), fees."""
    dividends_by_ticker: dict[str, float] = defaultdict(float)
    muni_interest = 0.0
    other_interest = 0.0
    total_fees = 0.0

    # Build a lookup for which symbols are muni bonds
    muni_symbols = set()
    for pos in snapshot.positions.values():
        if pos.instrument.instrument_type == "muni_bond":
            muni_symbols.add(pos.symbol)

    for txn in transactions:
        if txn.action == "dividend":
            dividends_by_ticker[txn.symbol] += abs(txn.amount)
        elif txn.action == "interest":
            if txn.symbol in muni_symbols:
                muni_interest += abs(txn.amount)
            else:
                other_interest += abs(txn.amount)
        elif txn.action == "fee":
            total_fees += abs(txn.amount)

    total_dividends = sum(dividends_by_ticker.values())
    interest_total = muni_interest + other_interest

    # Compute date range for annualization
    days = 0
    date_range = snapshot.date_range
    if date_range[0] and date_range[1]:
        days = (date_range[1] - date_range[0]).days
    annual_factor = (365.0 / days) if days > 0 else 1.0

    return {
        "dividends_by_ticker": {
            k: round(v, 2)
            for k, v in sorted(dividends_by_ticker.items(), key=lambda x: -x[1])
        },
        "total_dividends": round(total_dividends, 2),
        "total_interest": round(interest_total, 2),
        "muni_bond_interest": round(muni_interest, 2),
        "other_interest": round(other_interest, 2),
        "total_fees": round(total_fees, 2),
        "date_range_days": days,
        "annualized_income": round((total_dividends + interest_total) * annual_factor, 2),
        "annualized_muni_income": round(muni_interest * annual_factor, 2),
        "annualized_fees": round(total_fees * annual_factor, 2),
    }


def _compute_options_summary(snapshot: HoldingsSnapshot) -> dict[str, Any]:
    """List all option positions with parsed details, separated into LEAPS vs short-dated."""

    # Use latest date in dataset as reference
    ref = snapshot.date_range[1] or datetime(2026, 2, 18)

    positions = []
    total_premium = 0.0
    leaps = []
    short_dated = []

    for key, pos in snapshot.positions.items():
        if pos.instrument.instrument_type != "options":
            continue

        opt = parse_option_symbol(pos.symbol)
        if not opt:
            continue

        # Days to expiration
        try:
            expiry = datetime(opt.expiry_year, opt.expiry_month, opt.expiry_day)
            dte = (expiry - ref).days
        except ValueError:
            dte = 0

        premium = pos.cost_basis
        total_premium += premium

        pos_detail = {
            "symbol": pos.symbol,
            "underlying": opt.underlying,
            "option_type": opt.option_type,
            "strike": opt.strike,
            "expiry": f"{opt.expiry_year}-{opt.expiry_month:02d}-{opt.expiry_day:02d}",
            "dte": dte,
            "quantity": round(pos.quantity, 2),
            "premium_paid": round(premium, 2),
            "realized_proceeds": round(pos.realized_proceeds, 2),
            "account": pos.account,
            "pre_existing": pos.pre_existing,
        }
        positions.append(pos_detail)

        if dte > 365:
            leaps.append(pos_detail)
        else:
            short_dated.append(pos_detail)

    return {
        "positions": sorted(positions, key=lambda x: x["dte"], reverse=True),
        "total_positions": len(positions),
        "total_premium_deployed": round(total_premium, 2),
        "leaps": leaps,
        "leaps_count": len(leaps),
        "short_dated": short_dated,
        "short_dated_count": len(short_dated),
    }


# ---------------------------------------------------------------------------
# State abbreviation patterns for muni bond jurisdiction detection
# ---------------------------------------------------------------------------

_STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}

# Patterns that identify state in muni bond descriptions
# Matches "LOS ANGELES CA", "SAN DIEGO CA", "CALIFORNIA ST", "SOUTHERN CA", etc.
_STATE_PATTERN = re.compile(
    r"\b(?:CALIFORNIA|" + "|".join(re.escape(v.upper()) for v in _STATE_NAMES.values()) + r")\b"
    r"|"
    r"\b[A-Z\s]+\s+(" + "|".join(re.escape(k) for k in _STATE_NAMES) + r")\b"
)


def _extract_state_from_description(desc: str) -> str | None:
    """Extract US state abbreviation from a muni bond description."""
    upper = desc.upper()

    # Check for full state names first (e.g. "CALIFORNIA ST")
    for abbr, name in _STATE_NAMES.items():
        if name.upper() in upper:
            return abbr

    # Check for state abbreviation after city/entity name
    # Pattern: "LOS ANGELES CA", "SAN DIEGO CA", "SOUTHERN CA", "LAKE TAHOE CA"
    m = re.search(r"\b([A-Z\s]+?)\s+(CA|NY|TX|FL|IL|PA|OH|NJ|MA|WA|VA|GA|NC|MI|MN|CT|MD|CO|OR|SC|AL|KY|LA|MO|IN|TN|WI|AZ|NV|OK|AR|UT|MS|NE|KS|NM|NH|ME|MT|RI|ID|HI|WV|ND|SD|VT|WY|DC|AK|DE|IA)\b", upper)
    if m:
        return m.group(2)

    return None


def _compute_muni_bonds(snapshot: HoldingsSnapshot) -> dict[str, Any]:
    """List all municipal bond holdings with face values and interest income."""
    bonds = []
    total_face_value = 0.0
    total_interest = 0.0

    for key, pos in snapshot.positions.items():
        if pos.instrument.instrument_type != "muni_bond":
            continue

        state = _extract_state_from_description(pos.description)
        coupon_pct = f"{pos.coupon_rate * 100:.3f}%" if pos.coupon_rate > 0 else "unknown"

        bond_info = {
            "symbol": pos.symbol,
            "issuer": _clean_issuer_name(pos.description),
            "face_value": round(pos.face_value, 2),
            "coupon_rate": coupon_pct,
            "interest_received": round(pos.interest, 2),
            "state": state,
            "account": pos.account,
        }
        bonds.append(bond_info)
        total_face_value += pos.face_value
        total_interest += pos.interest

    return {
        "positions": sorted(bonds, key=lambda x: -x["face_value"]),
        "total_face_value": round(total_face_value, 2),
        "total_interest": round(total_interest, 2),
        "count": len(bonds),
    }


def _clean_issuer_name(description: str) -> str:
    """Extract a readable issuer name from a WFA bond description."""
    # Take text before "CPN" or "G/O" or "B/E" as the issuer name
    desc = description.replace("\t", " ")
    for marker in ["CPN ", "G/O ", "B/E ", " BDS "]:
        idx = desc.find(marker)
        if idx > 0:
            issuer = desc[:idx].strip()
            # Remove trailing bond type keywords
            for suffix in ["GO", "REV", "UNLTD", "DEDICATED", "ELECTION"]:
                if issuer.endswith(suffix):
                    issuer = issuer[: -len(suffix)].strip()
            return issuer
    return desc[:60]


def _detect_tax_jurisdiction(snapshot: HoldingsSnapshot) -> dict[str, Any]:
    """Detect tax jurisdiction from municipal bond state concentrations."""
    state_face_values: dict[str, float] = defaultdict(float)
    state_issuers: dict[str, list[str]] = defaultdict(list)
    total_muni_face = 0.0

    for pos in snapshot.positions.values():
        if pos.instrument.instrument_type != "muni_bond":
            continue
        state = _extract_state_from_description(pos.description)
        if state:
            state_face_values[state] += pos.face_value
            issuer = _clean_issuer_name(pos.description)
            if issuer not in state_issuers[state]:
                state_issuers[state].append(issuer)
            total_muni_face += pos.face_value

    if not state_face_values:
        return {"jurisdiction": None, "confidence": "none", "evidence": "No municipal bonds detected"}

    # Find dominant state
    dominant = max(state_face_values, key=lambda s: state_face_values[s])
    dominant_pct = state_face_values[dominant] / total_muni_face if total_muni_face > 0 else 0

    if dominant_pct >= 0.80:
        confidence = "high"
    elif dominant_pct >= 0.50:
        confidence = "moderate"
    else:
        confidence = "low"

    return {
        "jurisdiction": _STATE_NAMES.get(dominant, dominant),
        "state_code": dominant,
        "confidence": confidence,
        "dominant_percentage": round(dominant_pct * 100, 1),
        "total_muni_face_value": round(total_muni_face, 2),
        "evidence": f"{len(state_issuers[dominant])} {dominant} issuers: {', '.join(state_issuers[dominant][:5])}",
        "state_breakdown": {
            st: {
                "face_value": round(fv, 2),
                "percentage": round(fv / total_muni_face * 100, 1) if total_muni_face > 0 else 0,
                "issuers": state_issuers[st],
            }
            for st, fv in sorted(state_face_values.items(), key=lambda x: -x[1])
        },
    }


# ---------------------------------------------------------------------------
# Portfolio Features (flat dict of ~33 computed features)
# ---------------------------------------------------------------------------

# Approximate beta values for sector-level drawdown estimation
_SECTOR_BETA = {
    "Technology": 1.25,
    "Consumer": 1.05,
    "Financials": 1.15,
    "Healthcare": 0.85,
    "Energy": 1.10,
    "Industrials": 1.05,
    "Broad Market": 1.00,
    "Precious Metals": 0.30,
    "Nuclear/Uranium": 1.40,
    "Real Estate": 0.95,
    "Unknown": 1.00,
}

# Known international ETFs for domestic vs. international estimation
_INTERNATIONAL_ETFS = {
    "VWO", "VXUS", "EFA", "EEM", "IEFA", "IEMG", "VEA", "BNDX", "VNQI",
}


def compute_portfolio_features(
    snapshot: HoldingsSnapshot,
    transactions: list[ParsedTransaction],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """Compute ~33 flat portfolio features across 5 groups.

    Returns a single flat dict. These complement the structured metrics
    and are passed to Claude for narrative analysis.
    """
    alloc = metrics["asset_allocation"]
    total_value = alloc.get("_total_estimated_value", 0.0)
    income = metrics["income_summary"]
    opts = metrics["options_summary"]
    tax = metrics["detected_tax_jurisdiction"]
    sectors = metrics["sector_exposure"]

    features: dict[str, Any] = {}

    # ---- Concentration Features (8) ----
    _compute_concentration_features(features, snapshot, metrics, total_value)

    # ---- Portfolio Structure Features (8) ----
    _compute_structure_features(features, alloc, snapshot, total_value)

    # ---- Income & Cost Features (7) ----
    _compute_income_features(features, income, total_value)

    # ---- Tax Features (4) ----
    _compute_tax_features(features, snapshot, metrics, tax, total_value)

    # ---- Risk Features (6) ----
    _compute_risk_features(features, snapshot, opts, sectors, total_value)

    return features


def _compute_concentration_features(
    features: dict[str, Any],
    snapshot: HoldingsSnapshot,
    metrics: dict[str, Any],
    total_value: float,
) -> None:
    """Concentration Features: HHI, top-N, single name vs ETF, cross-account."""
    # Build per-underlying market values (aggregate options into underlying)
    underlying_values: dict[str, float] = defaultdict(float)
    for pos in snapshot.positions.values():
        mv, _source = _estimate_market_value(pos)
        if mv == 0:
            continue
        sym = pos.symbol
        if pos.instrument.instrument_type == "options":
            opt = parse_option_symbol(sym)
            if opt:
                sym = opt.underlying
        underlying_values[sym] += mv

    sorted_values = sorted(underlying_values.values(), reverse=True)

    # ticker_hhi: Herfindahl-Hirschman Index across tickers
    if total_value > 0:
        shares = [v / total_value for v in sorted_values]
        features["ticker_hhi"] = round(sum(s ** 2 for s in shares), 4)
    else:
        features["ticker_hhi"] = 0.0

    # sector_hhi: HHI across sectors (using sector exposure data)
    sector_values = [s["market_value"] for s in metrics["sector_exposure"].values()]
    sector_total = sum(sector_values)
    if sector_total > 0:
        sector_shares = [v / sector_total for v in sector_values]
        features["sector_hhi"] = round(sum(s ** 2 for s in sector_shares), 4)
    else:
        features["sector_hhi"] = 0.0

    # top1/3/5 concentration
    if total_value > 0:
        features["top1_concentration"] = round(sum(sorted_values[:1]) / total_value * 100, 1)
        features["top3_concentration"] = round(sum(sorted_values[:3]) / total_value * 100, 1)
        features["top5_concentration"] = round(sum(sorted_values[:5]) / total_value * 100, 1)
    else:
        features["top1_concentration"] = 0.0
        features["top3_concentration"] = 0.0
        features["top5_concentration"] = 0.0

    # single_name_vs_etf_ratio
    single_name_value = 0.0
    etf_value = 0.0
    for pos in snapshot.positions.values():
        mv, _source = _estimate_market_value(pos)
        if pos.instrument.instrument_type == "equity":
            single_name_value += mv
        elif pos.instrument.instrument_type == "etf":
            etf_value += mv
    features["single_name_vs_etf_ratio"] = (
        round(single_name_value / etf_value, 2) if etf_value > 0 else None if single_name_value > 0 else 0.0
    )

    # max_cross_account_exposure: largest cross-account exposure as % of portfolio
    cross = metrics["multi_account_breakdown"]["cross_account_exposure"]
    max_cross = max((d["total_exposure"] for d in cross.values()), default=0.0)
    features["max_cross_account_exposure"] = round(max_cross / total_value * 100, 1) if total_value > 0 else 0.0

    # sector_max_pct: largest sector allocation %
    if sector_total > 0 and sector_values:
        features["sector_max_pct"] = round(max(sector_values) / sector_total * 100, 1)
    else:
        features["sector_max_pct"] = 0.0


def _compute_structure_features(
    features: dict[str, Any],
    alloc: dict[str, Any],
    snapshot: HoldingsSnapshot,
    total_value: float,
) -> None:
    """Portfolio Structure Features: asset type percentages, domestic/intl, active/passive."""
    def _pct(itype: str) -> float:
        data = alloc.get(itype)
        if data and isinstance(data, dict):
            return round(data.get("percentage", 0.0), 1)
        return 0.0

    features["equity_pct"] = _pct("equity")
    features["etf_pct"] = _pct("etf")
    features["options_pct"] = _pct("options")
    features["fixed_income_pct"] = round(_pct("muni_bond") + _pct("corp_bond"), 1)
    features["structured_pct"] = _pct("structured")
    features["cash_pct"] = round(_pct("cash") + _pct("money_market"), 1)

    # domestic_vs_international: ratio based on known international ETFs
    intl_value = 0.0
    domestic_value = 0.0
    for pos in snapshot.positions.values():
        mv, _source = _estimate_market_value(pos)
        if mv == 0:
            continue
        if pos.instrument.instrument_type in ("equity", "etf"):
            if pos.symbol in _INTERNATIONAL_ETFS:
                intl_value += mv
            else:
                domestic_value += mv
    features["domestic_vs_international"] = (
        round(domestic_value / intl_value, 2) if intl_value > 0 else None if domestic_value > 0 else 0.0
    )

    # active_vs_passive: single stocks + options = active; ETFs = passive
    active_value = 0.0
    passive_value = 0.0
    for pos in snapshot.positions.values():
        mv, _source = _estimate_market_value(pos)
        if pos.instrument.instrument_type in ("equity", "options"):
            active_value += mv
        elif pos.instrument.instrument_type == "etf":
            passive_value += mv
    features["active_vs_passive"] = (
        round(active_value / passive_value, 2) if passive_value > 0 else None if active_value > 0 else 0.0
    )


def _compute_income_features(
    features: dict[str, Any],
    income: dict[str, Any],
    total_value: float,
) -> None:
    """Income & Cost Features: gross income, fees, yield, concentration."""
    features["gross_dividend_income"] = income["total_dividends"]
    features["gross_interest_income"] = income["total_interest"]
    features["total_fees"] = income["total_fees"]

    # fee_drag_pct: annualized fees as % of portfolio value
    features["fee_drag_pct"] = (
        round(income["annualized_fees"] / total_value * 100, 3) if total_value > 0 else 0.0
    )

    features["net_income_after_fees"] = round(
        income["total_dividends"] + income["total_interest"] - income["total_fees"], 2
    )

    # income_concentration_top3: % of dividend income from top 3 payers
    divs = income.get("dividends_by_ticker", {})
    sorted_divs = sorted(divs.values(), reverse=True)
    total_divs = sum(sorted_divs)
    if total_divs > 0:
        features["income_concentration_top3"] = round(sum(sorted_divs[:3]) / total_divs * 100, 1)
    else:
        features["income_concentration_top3"] = 0.0

    # estimated_portfolio_yield: annualized income / portfolio value
    features["estimated_portfolio_yield"] = (
        round(income["annualized_income"] / total_value * 100, 2) if total_value > 0 else 0.0
    )


def _compute_tax_features(
    features: dict[str, Any],
    snapshot: HoldingsSnapshot,
    metrics: dict[str, Any],
    tax: dict[str, Any],
    total_value: float,
) -> None:
    """Tax Features: jurisdiction, muni values, tax placement score."""
    features["tax_jurisdiction"] = tax.get("jurisdiction")
    munis = metrics.get("muni_bond_holdings", {})
    features["muni_face_value"] = munis.get("total_face_value", 0.0)

    income = metrics["income_summary"]
    features["muni_annual_income"] = income.get("annualized_muni_income", 0.0)

    # tax_placement_score: 0-100 measuring how well income-producing assets
    # are placed in tax-advantaged accounts
    # Logic: income assets (bonds, dividend stocks, interest) should be in IRA/401k;
    # growth/muni bonds can be in taxable.
    score_points = 0.0
    score_total = 0.0

    for pos in snapshot.positions.values():
        mv, _source = _estimate_market_value(pos)
        if mv == 0:
            continue

        itype = pos.instrument.instrument_type
        acct_type = pos.account_type

        # Muni bonds: GOOD in taxable (tax-exempt), BAD in IRA (wasted exemption)
        if itype == "muni_bond":
            weight = mv
            score_total += weight
            if acct_type == "taxable":
                score_points += weight  # Correct placement
            # In IRA/401k → waste of tax-exempt status → 0 points

        # Corporate bonds / interest-producing: GOOD in IRA, BAD in taxable
        elif itype in ("corp_bond", "structured", "money_market"):
            weight = mv
            score_total += weight
            if acct_type in ("ira", "roth_ira", "401k"):
                score_points += weight  # Correct: shield interest from tax

        # High-dividend equities: slightly better in IRA
        elif itype == "equity" and pos.dividends > 0:
            div_yield_est = pos.dividends / mv if mv > 0 else 0
            if div_yield_est > 0.02:  # >2% yield = income-oriented
                weight = mv * 0.5  # Partial weight
                score_total += weight
                if acct_type in ("ira", "roth_ira", "401k"):
                    score_points += weight

        # Growth equities: slightly better in taxable (lower cap gains rate)
        elif itype == "equity" and pos.dividends == 0:
            weight = mv * 0.3  # Low weight
            score_total += weight
            if acct_type == "taxable":
                score_points += weight

    features["tax_placement_score"] = (
        round(score_points / score_total * 100, 0) if score_total > 0 else 50.0
    )


def _compute_risk_features(
    features: dict[str, Any],
    snapshot: HoldingsSnapshot,
    opts: dict[str, Any],
    sectors: dict[str, Any],
    total_value: float,
) -> None:
    """Risk Features: options exposure, structured risk, correlation, drawdown."""
    # options_premium_at_risk: total premium deployed on options
    features["options_premium_at_risk"] = opts["total_premium_deployed"]

    # options_notional_exposure: strike * quantity * 100
    notional = 0.0
    for p in opts["positions"]:
        notional += p["strike"] * abs(p["quantity"]) * 100
    features["options_notional_exposure"] = round(notional, 2)

    # structured_product_exposure: total structured product value
    structured_mv = 0.0
    for pos in snapshot.positions.values():
        if pos.instrument.instrument_type == "structured":
            structured_mv += _estimate_market_value(pos)[0]
    features["structured_product_exposure"] = round(structured_mv, 2)

    # correlation_estimate: rough portfolio correlation estimate
    # Higher tech/single-sector concentration → higher correlation
    sector_values = {s: d["market_value"] for s, d in sectors.items()}
    equity_etf_total = sum(sector_values.values())
    if equity_etf_total > 0:
        # Use sector HHI as a proxy for correlation
        sector_shares = [v / equity_etf_total for v in sector_values.values()]
        hhi = sum(s ** 2 for s in sector_shares)
        # Map HHI to approximate correlation: HHI=0.1 → corr=0.3, HHI=1.0 → corr=0.95
        features["correlation_estimate"] = round(min(0.3 + 0.65 * hhi, 0.95), 2)
    else:
        features["correlation_estimate"] = 0.5

    # largest_loss_potential: largest single position's market value
    max_position_mv = 0.0
    for pos in snapshot.positions.values():
        mv, _source = _estimate_market_value(pos)
        if mv > max_position_mv:
            max_position_mv = mv
    features["largest_loss_potential"] = round(max_position_mv, 2)

    # drawdown_sensitivity: beta-weighted estimate of loss in a 20% market decline
    # Sum of (position_value * sector_beta * 0.20) across all equity/ETF/options
    drawdown = 0.0
    for pos in snapshot.positions.values():
        if pos.instrument.instrument_type not in ("equity", "etf", "options"):
            continue
        mv, _source = _estimate_market_value(pos)
        sector = _get_sector(pos.symbol, pos)
        beta = _SECTOR_BETA.get(sector, 1.0)
        drawdown += mv * beta * 0.20
    features["drawdown_sensitivity"] = round(drawdown, 2)

    return


# ---------------------------------------------------------------------------
# Portfolio completeness detection
# ---------------------------------------------------------------------------


def _compute_portfolio_completeness(
    snapshot: HoldingsSnapshot,
    transactions: list[ParsedTransaction],
    total_value: float,
) -> dict[str, Any]:
    """Detect whether the CSV activity window captures the full portfolio.

    Looks for signals that the actual portfolio is larger than what's
    reconstructed from buy/sell activity alone.
    """
    signals: list[str] = []

    # 1. Bond positions receiving interest with no purchase activity
    pre_existing_bonds = [
        p for p in snapshot.positions.values()
        if p.pre_existing and p.instrument.instrument_type in ("muni_bond", "corp_bond")
    ]
    if pre_existing_bonds:
        signals.append(
            f"Interest income from {len(pre_existing_bonds)} "
            f"bond{'s' if len(pre_existing_bonds) != 1 else ''} "
            f"with no purchase activity"
        )

    # 2. Options on underlyings not held as equity in the visible window
    equity_symbols: set[str] = set()
    for p in snapshot.positions.values():
        if p.instrument.instrument_type in ("equity", "etf") and p.quantity > 0:
            equity_symbols.add(p.symbol)

    option_underlyings_without_equity: set[str] = set()
    for p in snapshot.positions.values():
        if p.instrument.instrument_type != "options":
            continue
        opt = parse_option_symbol(p.symbol)
        if opt and opt.underlying not in equity_symbols:
            option_underlyings_without_equity.add(opt.underlying)

    if option_underlyings_without_equity:
        signals.append(
            f"Covered calls on {len(option_underlyings_without_equity)} "
            f"position{'s' if len(option_underlyings_without_equity) != 1 else ''} "
            f"not visible in activity window"
        )

    # 3. Pre-existing equity/ETF positions (dividends or sells without prior buy)
    pre_existing_equities = [
        p for p in snapshot.positions.values()
        if p.pre_existing and p.instrument.instrument_type in ("equity", "etf")
    ]
    if pre_existing_equities:
        signals.append(
            f"Dividend or sell activity on {len(pre_existing_equities)} "
            f"position{'s' if len(pre_existing_equities) != 1 else ''} "
            f"opened before the data window"
        )

    # 4. Multiple active accounts suggest a broader portfolio
    active_accounts = [
        name for name, acct in snapshot.accounts.items()
        if acct.transaction_count >= 2
    ]
    if len(active_accounts) >= 3:
        signals.append(
            f"{len(active_accounts)} active accounts suggest broader portfolio"
        )

    prompt_for_more_data = len(signals) > 0
    confidence = "partial" if prompt_for_more_data else "complete"

    return {
        "reconstructed_value": round(total_value, 0),
        "completeness_confidence": confidence,
        "signals_of_additional_holdings": signals,
        "prompt_for_more_data": prompt_for_more_data,
    }


# ---------------------------------------------------------------------------
# Claude API integration
# ---------------------------------------------------------------------------


def _call_claude(api_key: str, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Make the actual API call to Claude."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text = message.content[0].text.strip()

    # Handle markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1 if lines[0].startswith("```") else 0
        end = -1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end]).strip()

    analysis = json.loads(text)
    return analysis


def _build_system_prompt() -> str:
    return (
        "You are a senior portfolio analyst producing a comprehensive portfolio analysis report.\n\n"
        "Your audience is an experienced wealth manager or sophisticated investor managing millions of dollars. "
        "Do NOT explain basic concepts (what an ETF is, what diversification means, etc.). "
        "Be direct and insightful — highlight things the portfolio owner might not realize.\n\n"
        "RULES:\n"
        "- Reference SPECIFIC positions by ticker, quantity, and dollar amount\n"
        "- Identify cross-account exposures (same underlying across equity + options + structured notes)\n"
        "- Detect tax jurisdiction from municipal bond issuers, corporate bond issuers, or other clues\n"
        "- Note large wire transfers or capital movements and how capital is being redeployed\n"
        "- Separate LEAPS (>1yr) from short-dated options and comment on the strategy difference\n"
        "- Be honest about concentration risk and hidden correlations\n"
        "- Point out things the trader might not realize about their own portfolio\n"
        "- When describing portfolio composition, reference the analyzed portion naturally "
        "(e.g. 'across the analyzed positions') without disclaiming or apologizing about "
        "data limitations. Never use words like 'only' or 'incomplete'.\n"
        "- If you see evidence of a California nexus (LA Water & Power, San Diego schools, Southern CA utilities), note it\n\n"
        "QUANTITATIVE FEATURE REFERENCES — cite specific values from portfolio_features:\n"
        "- Use ticker_hhi and sector_hhi to quantify concentration (>0.25 = highly concentrated)\n"
        "- Reference top1_concentration to flag single-name risk\n"
        "- Use tax_placement_score (0-100) to assess tax efficiency of asset placement\n"
        "- Cite options_notional_exposure for total options risk exposure\n"
        "- Use drawdown_sensitivity to estimate portfolio loss in a 20% market decline\n"
        "- Reference fee_drag_pct to quantify annual cost impact\n"
        "- Use estimated_portfolio_yield for income analysis\n"
        "- Cite single_name_vs_etf_ratio and active_vs_passive for structure commentary\n"
        "- Reference correlation_estimate for hidden risk from sector concentration\n\n"
        "You MUST respond with valid JSON matching the exact schema provided. No markdown, no extra text."
    )


def _build_user_prompt(metrics: dict[str, Any]) -> str:
    metrics_json = json.dumps(metrics, indent=2, default=str)

    return (
        "Analyze this portfolio and return a JSON object with the following exact structure:\n\n"
        "{\n"
        '  "portfolio_structure": {\n'
        '    "headline": "one compelling sentence about the overall portfolio",\n'
        '    "account_purposes": [\n'
        '      {\n'
        '        "account_id": "the account name",\n'
        '        "account_type": "ira|taxable|business",\n'
        '        "purpose": "inferred purpose of this account",\n'
        '        "strategy": "dominant strategy",\n'
        '        "estimated_value": "estimated current value"\n'
        '      }\n'
        '    ],\n'
        '    "narrative": "2-3 paragraphs about portfolio structure"\n'
        '  },\n'
        '  "concentration_analysis": {\n'
        '    "headline": "one sentence about concentration",\n'
        '    "top_exposures": [\n'
        '      {\n'
        '        "name": "ticker or sector name",\n'
        '        "total_exposure": "dollar amount or percentage",\n'
        '        "across_accounts": "which accounts hold this",\n'
        '        "includes": "what instrument types (equity, options, etc.)"\n'
        '      }\n'
        '    ],\n'
        '    "narrative": "1-2 paragraphs about concentration risks"\n'
        '  },\n'
        '  "income_analysis": {\n'
        '    "headline": "one sentence about income",\n'
        '    "annual_estimate": "estimated annual income",\n'
        '    "by_source": {\n'
        '      "dividends": "total dividend income",\n'
        '      "muni_interest": "municipal bond interest or N/A",\n'
        '      "corporate_coupons": "corporate bond coupons or N/A"\n'
        '    },\n'
        '    "tax_efficiency": "are income sources in the right account types?",\n'
        '    "narrative": "1-2 paragraphs about income"\n'
        '  },\n'
        '  "options_strategy": {\n'
        '    "headline": "one sentence about options usage",\n'
        '    "positions_summary": "count of positions, premium deployed, LEAPS vs short-dated",\n'
        '    "narrative": "1-2 paragraphs about options strategy"\n'
        '  },\n'
        '  "risk_assessment": {\n'
        '    "headline": "one sentence about risk",\n'
        '    "key_risks": [\n'
        '      {\n'
        '        "risk": "risk name",\n'
        '        "severity": "high|moderate|low",\n'
        '        "detail": "specific detail about this risk"\n'
        '      }\n'
        '    ],\n'
        '    "narrative": "1-2 paragraphs about risk"\n'
        '  },\n'
        '  "tax_context": {\n'
        '    "detected_jurisdiction": "state/country or null",\n'
        '    "evidence": "what clues point to this jurisdiction",\n'
        '    "narrative": "1 paragraph about tax implications"\n'
        '  },\n'
        '  "key_recommendation": "one specific, actionable recommendation"\n'
        "}\n\n"
        f"PORTFOLIO METRICS:\n{metrics_json}"
    )


def _placeholder_analysis() -> dict[str, Any]:
    """Return a minimal placeholder when Claude API is unavailable."""
    return {
        "portfolio_structure": {
            "headline": "Portfolio analysis requires Claude API key",
            "account_purposes": [],
            "narrative": "Set ANTHROPIC_API_KEY to generate a full portfolio analysis narrative.",
        },
        "concentration_analysis": {
            "headline": "N/A", "top_exposures": [], "narrative": "",
        },
        "income_analysis": {
            "headline": "N/A", "annual_estimate": "N/A",
            "by_source": {}, "tax_efficiency": "", "narrative": "",
        },
        "options_strategy": {
            "headline": "N/A", "positions_summary": "", "narrative": "",
        },
        "risk_assessment": {
            "headline": "N/A", "key_risks": [], "narrative": "",
        },
        "tax_context": {
            "detected_jurisdiction": None, "evidence": "", "narrative": "",
        },
        "key_recommendation": "Set ANTHROPIC_API_KEY environment variable for full analysis.",
        "_generated_by": "placeholder",
    }
