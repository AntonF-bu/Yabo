"""
Instrument classifier for parsed brokerage transactions.

Classification hierarchy (highest priority first):
1. Options  - contracts, puts, calls, expirations
2. Money Market - sweep, money market, settlement fund
3. Structured Products - notes, structured, CDs with maturity
4. Municipal Bonds - muni, municipal, tax-exempt, state/city bonds
5. Corporate Bonds - bond, debenture, note (non-structured)
6. ETFs - known ETF symbols, "ETF" / "fund" in description
7. Equities - everything else with a symbol

Each classifier returns a confidence score. The highest-priority match wins.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class InstrumentClassification:
    """Result of classifying a financial instrument."""

    instrument_type: str  # options | money_market | structured | muni_bond | corp_bond | etf | equity | cash | unknown
    confidence: float  # 0.0 to 1.0
    reason: str  # why this classification was chosen
    sub_type: Optional[str] = None  # e.g. "call", "put" for options


# ---------------------------------------------------------------------------
# Known symbol sets
# ---------------------------------------------------------------------------

# Common money market / sweep symbols
_MONEY_MARKET_SYMBOLS = {
    "SWVXX", "SPAXX", "FDRXX", "FZFXX", "VMFXX", "VMMXX",
    "SPRXX", "SNVXX", "WFCXX", "WFJXX",  # Wells Fargo sweep
    "SNOXX", "SWRXX", "RJXXX",
    "SWEEP", "MMKT",
}

# Common broad-market ETFs (non-exhaustive, used as hints)
_KNOWN_ETFS = {
    # Broad market
    "SPY", "VOO", "IVV", "VTI", "QQQ", "DIA", "IWM", "IWF", "IWD",
    "VTV", "VUG", "SCHB", "SCHX", "SCHA", "SCHD",
    # International
    "EFA", "EEM", "VEA", "VWO", "IEFA", "IEMG", "VXUS",
    # Fixed income
    "AGG", "BND", "LQD", "TLT", "IEF", "SHY", "HYG", "JNK",
    "VCIT", "VCSH", "BNDX", "VTIP", "TIP",
    # Sector
    "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE",
    "VGT", "VFH", "VDE", "VHT", "VIS", "VCR", "VDC", "VPU",
    # Commodities / alternatives
    "GLD", "SLV", "IAU", "USO", "UNG", "VNQ", "VNQI",
    # Leveraged / inverse (still ETFs)
    "TQQQ", "SQQQ", "UPRO", "SPXU", "UVXY", "SVXY",
}

# ---------------------------------------------------------------------------
# Pattern matchers (compiled once)
# ---------------------------------------------------------------------------

_OPTIONS_PATTERNS = [
    re.compile(r"\b(call|put|option|contract|strike|expir|exercise|assign)\b", re.IGNORECASE),
    re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}\s+\$?\d+\.?\d*\s+(C|P)\b"),  # 01/19/24 $150 C
    re.compile(r"\b\w+\s+\d{6}[CP]\d+", re.IGNORECASE),  # AAPL 240119C00150000
]

_MONEY_MARKET_PATTERNS = [
    re.compile(r"\b(money\s*market|sweep|settlement\s*fund|mmkt)\b", re.IGNORECASE),
]

_STRUCTURED_PATTERNS = [
    re.compile(r"\b(structured\s*(note|product|investment)|CD\b.*maturity|certificate\s*of\s*deposit)", re.IGNORECASE),
    re.compile(r"\b(auto-callable|barrier|coupon\s*note|linked\s*note)\b", re.IGNORECASE),
]

_MUNI_PATTERNS = [
    re.compile(r"\b(municipal|muni|tax[- ]?exempt|tax[- ]?free)\b", re.IGNORECASE),
    re.compile(r"\b(state\s+of|city\s+of|county\s+of|port\s+auth|school\s+dist|water\s+dist)\b", re.IGNORECASE),
    re.compile(r"\bGO\s+BOND\b", re.IGNORECASE),
]

_CORP_BOND_PATTERNS = [
    re.compile(r"\b(bond|debenture|fixed\s*income|coupon|maturity|yield|par\s*value)\b", re.IGNORECASE),
    re.compile(r"\b\d+\.?\d*%\s*(sr|sub)?\s*(note|bond|deb)\b", re.IGNORECASE),
]

_ETF_PATTERNS = [
    re.compile(r"\bETF\b", re.IGNORECASE),
    re.compile(r"\b(exchange\s*traded\s*fund|index\s*fund|ishares|vanguard\s+.*\s+index|spdr)\b", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify(
    symbol: str,
    description: str = "",
    action: str = "",
) -> InstrumentClassification:
    """
    Classify a financial instrument based on symbol, description, and action.

    Args:
        symbol: Ticker symbol (e.g. "AAPL", "SPY", "SWVXX")
        description: Security description from the brokerage
        action: Transaction action (e.g. "buy", "sell", "dividend")

    Returns:
        InstrumentClassification with type, confidence, and reason
    """
    sym = symbol.strip().upper()
    desc = description.strip()
    act = action.strip().lower()
    combined = f"{sym} {desc} {act}"

    # ----- 1. Options (highest priority) -----
    if act in ("option assignment", "option exercise", "expired", "expiration", "assigned", "exercised"):
        sub = _detect_option_subtype(combined)
        return InstrumentClassification("options", 0.95, f"Action '{action}' indicates options", sub)

    for pat in _OPTIONS_PATTERNS:
        if pat.search(combined):
            sub = _detect_option_subtype(combined)
            return InstrumentClassification("options", 0.90, f"Pattern match: {pat.pattern}", sub)

    # ----- 2. Money Market -----
    if sym in _MONEY_MARKET_SYMBOLS:
        return InstrumentClassification("money_market", 0.95, f"Known money market symbol: {sym}")

    for pat in _MONEY_MARKET_PATTERNS:
        if pat.search(combined):
            return InstrumentClassification("money_market", 0.85, f"Description match: {pat.pattern}")

    # ----- 3. Structured Products -----
    for pat in _STRUCTURED_PATTERNS:
        if pat.search(combined):
            return InstrumentClassification("structured", 0.85, f"Structured product match: {pat.pattern}")

    # ----- 4. Municipal Bonds -----
    for pat in _MUNI_PATTERNS:
        if pat.search(combined):
            return InstrumentClassification("muni_bond", 0.85, f"Municipal bond match: {pat.pattern}")

    # ----- 5. Corporate Bonds -----
    for pat in _CORP_BOND_PATTERNS:
        if pat.search(combined):
            # Avoid false positives: ETFs mentioning "bond" in name
            if sym in _KNOWN_ETFS:
                return InstrumentClassification("etf", 0.90, f"Known ETF symbol despite bond keyword: {sym}")
            return InstrumentClassification("corp_bond", 0.80, f"Corporate bond match: {pat.pattern}")

    # ----- 6. ETFs -----
    if sym in _KNOWN_ETFS:
        return InstrumentClassification("etf", 0.95, f"Known ETF symbol: {sym}")

    for pat in _ETF_PATTERNS:
        if pat.search(combined):
            return InstrumentClassification("etf", 0.80, f"ETF pattern match: {pat.pattern}")

    # ----- 7. Equities (default for anything with a symbol) -----
    if sym and sym != "CASH" and sym != "N/A" and sym != "":
        return InstrumentClassification("equity", 0.70, f"Default classification for symbol: {sym}")

    # ----- Cash / Unknown -----
    if sym == "CASH" or act in ("interest", "fee", "transfer"):
        return InstrumentClassification("cash", 0.60, "Cash transaction")

    return InstrumentClassification("unknown", 0.30, "Could not classify instrument")


def _detect_option_subtype(text: str) -> Optional[str]:
    """Try to determine if an option is a call or put."""
    text_lower = text.lower()
    if "call" in text_lower or text.endswith(" C"):
        return "call"
    if "put" in text_lower or text.endswith(" P"):
        return "put"
    return None
