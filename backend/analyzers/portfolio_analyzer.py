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
from datetime import datetime
from typing import Any, Optional

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

    asset_allocation = _compute_asset_allocation(snapshot)
    sector_exposure = _compute_sector_exposure(snapshot)
    multi_account = _compute_multi_account(snapshot)
    income_summary = _compute_income_summary(snapshot, transactions)
    options_summary = _compute_options_summary(snapshot)
    muni_bonds = _compute_muni_bonds(snapshot)
    tax_jurisdiction = _detect_tax_jurisdiction(snapshot)

    return {
        "asset_allocation": asset_allocation,
        "sector_exposure": sector_exposure,
        "multi_account_breakdown": multi_account,
        "income_summary": income_summary,
        "options_summary": options_summary,
        "muni_bond_holdings": muni_bonds,
        "detected_tax_jurisdiction": tax_jurisdiction,
    }


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


def _estimate_market_value(pos: PositionRecord) -> float:
    """Estimate current market value of a position."""
    if pos.instrument.instrument_type == "money_market":
        return abs(pos.quantity) * 1.0
    if pos.instrument.instrument_type == "cash":
        return abs(pos.quantity)
    # Bonds: use face value (par value) as market value proxy
    if pos.instrument.instrument_type in ("muni_bond", "corp_bond"):
        return pos.face_value if pos.face_value > 0 else abs(pos.quantity)
    # Structured products: use cost basis (actual amount paid)
    if pos.instrument.instrument_type == "structured":
        return pos.cost_basis if pos.cost_basis > 0 else 0.0
    if pos.quantity == 0:
        return 0.0
    last_price = _get_last_price(pos)
    if pos.instrument.instrument_type == "options":
        # Options prices are per-share, contracts are 100 shares
        return abs(pos.quantity) * last_price * 100
    return abs(pos.quantity) * last_price


def _compute_asset_allocation(snapshot: HoldingsSnapshot) -> dict[str, Any]:
    """Group positions by instrument type and compute market values."""
    allocation: dict[str, dict] = defaultdict(
        lambda: {"market_value": 0.0, "positions": 0, "symbols": []}
    )
    total_value = 0.0

    for key, pos in snapshot.positions.items():
        if pos.quantity == 0 and pos.instrument.instrument_type not in ("cash", "money_market"):
            continue

        mv = _estimate_market_value(pos)
        itype = pos.instrument.instrument_type
        allocation[itype]["market_value"] += mv
        allocation[itype]["positions"] += 1
        if pos.symbol not in allocation[itype]["symbols"]:
            allocation[itype]["symbols"].append(pos.symbol)
        total_value += mv

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
    return result


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
        mv = _estimate_market_value(pos)
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
        acct_positions.sort(key=lambda p: _estimate_market_value(p), reverse=True)

        total_value = sum(_estimate_market_value(p) for p in acct_positions)

        # Dominant asset types
        type_values: dict[str, float] = defaultdict(float)
        for p in acct_positions:
            type_values[p.instrument.instrument_type] += _estimate_market_value(p)
        dominant_types = sorted(type_values.items(), key=lambda x: -x[1])[:3]

        largest = []
        for p in acct_positions[:5]:
            mv = _estimate_market_value(p)
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
        symbol_accounts[symbol]["total_value"] += _estimate_market_value(pos)

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
        "- If you see evidence of a California nexus (LA Water & Power, San Diego schools, Southern CA utilities), note it\n\n"
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
