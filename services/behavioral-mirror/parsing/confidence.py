"""Confidence scoring for parsed transactions.

Assigns a 0.0–1.0 confidence score to each parsed transaction based on:
- How unambiguous the action/instrument classification is
- Whether account context resolves ambiguity (e.g. short vs closing-long)
- Whether a pattern memory match corroborates the parser's output

This module does NOT call the memory layer itself — the caller should
pass in a ``memory_confidence`` value from a prior lookup.
"""

from __future__ import annotations

import re
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Known high-confidence patterns
# ---------------------------------------------------------------------------

_SIMPLE_ACTIONS = {"buy", "sell", "dividend", "interest", "fee", "transfer"}

_HIGH_CONF_INSTRUMENT_TYPES = {"equity", "etf", "money_market", "cash"}

_MEDIUM_CONF_INSTRUMENT_TYPES = {"muni_bond", "corp_bond", "structured"}

_AMBIGUOUS_KEYWORDS = re.compile(
    r"spinoff|merger|reorg|reverse\s*split|tender|exchange\s*offer"
    r"|corporate\s*action|mandatory|voluntary|adjustment",
    re.IGNORECASE,
)

_MULTI_LEG_KEYWORDS = re.compile(
    r"spread|straddle|strangle|collar|condor|butterfly|iron|combo|leg",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_confidence(
    parsed_transaction: dict[str, Any],
    raw_row: str,
    account_positions: Optional[dict[str, Any]] = None,
    *,
    memory_confidence: Optional[float] = None,
) -> float:
    """Score how confident we are in a parsed transaction's classification.

    Parameters
    ----------
    parsed_transaction:
        Dict with at least ``action``, ``symbol``, ``quantity``, ``price``,
        ``amount``, ``description``, and optionally ``instrument_type``,
        ``instrument_confidence``.
    raw_row:
        The original CSV row text before parsing.
    account_positions:
        Optional dict of ``{symbol: quantity}`` representing the account's
        known positions at the time of this transaction.  Used to resolve
        sell-side ambiguity (closing long vs opening short).
    memory_confidence:
        If a pattern memory lookup matched, pass its confidence here.
        A match ≥ 0.90 boosts the final score to at least 0.95.

    Returns
    -------
    float
        Confidence between 0.0 and 1.0.
    """
    score = _base_score(parsed_transaction, raw_row)

    # Contextual adjustments
    score = _adjust_for_sell_ambiguity(score, parsed_transaction, account_positions)
    score = _adjust_for_description_complexity(score, parsed_transaction, raw_row)

    # Memory boost: corroboration from past patterns
    if memory_confidence is not None and memory_confidence >= 0.90:
        score = max(score, 0.95)

    return round(min(max(score, 0.0), 1.0), 3)


# ---------------------------------------------------------------------------
# Internal scoring functions
# ---------------------------------------------------------------------------


def _base_score(txn: dict[str, Any], raw_row: str) -> float:
    """Compute the initial confidence from action + instrument type."""
    action = (txn.get("action") or "").lower()
    inst_type = (txn.get("instrument_type") or "").lower()
    inst_conf = txn.get("instrument_confidence", 0.8)
    description = (txn.get("description") or "").lower()
    symbol = txn.get("symbol") or ""
    quantity = txn.get("quantity", 0)
    price = txn.get("price", 0)

    # Corporate actions / spinoffs — always low
    if _AMBIGUOUS_KEYWORDS.search(description) or _AMBIGUOUS_KEYWORDS.search(raw_row):
        return 0.45

    # Multi-leg option strategies — low
    if _MULTI_LEG_KEYWORDS.search(description) or _MULTI_LEG_KEYWORDS.search(raw_row):
        return 0.50

    # Simple equity / ETF buy or sell with clear data
    if action in ("buy", "sell") and inst_type in _HIGH_CONF_INSTRUMENT_TYPES:
        if symbol and quantity and price:
            return 0.97
        return 0.90

    # Dividends and interest — straightforward
    if action in ("dividend", "interest"):
        return 0.96

    # Fees and transfers
    if action in ("fee", "transfer", "withholding"):
        return 0.94

    # Options — medium unless strategy is clear
    if inst_type == "options":
        if action in ("buy", "sell") and symbol and quantity:
            return 0.80
        return 0.65

    # Bonds / structured products — medium
    if inst_type in _MEDIUM_CONF_INSTRUMENT_TYPES:
        if action in _SIMPLE_ACTIONS:
            return 0.78
        return 0.65

    # Unknown instrument type
    if inst_type in ("unknown", ""):
        return 0.40

    # Fallback: use whatever the instrument classifier reported
    return float(inst_conf) * 0.9


def _adjust_for_sell_ambiguity(
    score: float,
    txn: dict[str, Any],
    positions: Optional[dict[str, Any]],
) -> float:
    """Penalize sells where we can't tell if it's closing-long or opening-short."""
    action = (txn.get("action") or "").lower()
    if action != "sell":
        return score

    symbol = txn.get("symbol", "")
    inst_type = (txn.get("instrument_type") or "").lower()

    if positions is None:
        # No position context — slight penalty for options (short vs close)
        if inst_type == "options":
            return score - 0.12
        return score - 0.03

    held_qty = positions.get(symbol, 0)
    sell_qty = abs(txn.get("quantity", 0))

    if held_qty > 0 and sell_qty <= held_qty:
        # Clearly closing a long position — confidence boost
        return min(score + 0.05, 1.0)

    if held_qty == 0 and inst_type == "options":
        # Selling options with no position — ambiguous (STO vs STC on a
        # position we can't see).  Moderate penalty.
        return score - 0.10

    return score


def _adjust_for_description_complexity(
    score: float,
    txn: dict[str, Any],
    raw_row: str,
) -> float:
    """Penalize transactions with complex or unusual descriptions."""
    desc = (txn.get("description") or "") + " " + raw_row

    # Very long descriptions often indicate complex instruments
    if len(desc) > 200:
        score -= 0.05

    # Multiple parentheticals suggest structured products
    if desc.count("(") >= 2:
        score -= 0.03

    # Action classified as 'other' by the parser
    if (txn.get("action") or "").lower() == "other":
        score = min(score, 0.50)

    return score
