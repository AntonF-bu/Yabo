"""Pattern memory: normalize, hash, store, and recall transaction patterns.

Transactions from different users with the same structure (e.g. selling a
call at any strike on any ticker through the same brokerage) produce the
same pattern hash.  This lets us build a shared memory of how to classify
ambiguous descriptions — the more users we see, the better we get.

Supabase table: ``parsing_memory``
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Normalization regexes
# ---------------------------------------------------------------------------

# Dates in many formats: 2026-05-16, 05/16/2026, MAY 16 2026, 051626, etc.
_DATE_PATTERNS = re.compile(
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"   # MM/DD/YYYY or similar
    r"|\b\d{4}-\d{2}-\d{2}\b"               # ISO 2026-05-16
    r"|\b(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d{1,2}\s+\d{4}\b"
    r"|\b\d{6}\b",                           # compact MMDDYY (WFA bonds)
    re.IGNORECASE,
)

# Dollar amounts: $12.50, 1,000.00, -500, etc.
_AMOUNT_RE = re.compile(r"-?\$?[\d,]+\.?\d*")

# Tickers: 1-5 uppercase letters that look like symbols (standalone words)
_TICKER_RE = re.compile(r"\b[A-Z]{1,5}\b")

# Strikes: numbers that look like option strikes (near a CALL/PUT keyword)
_STRIKE_RE = re.compile(r"\b\d{1,6}(?:\.\d{1,2})?\b")

# Account numbers / IDs: sequences of digits 4+ chars
_ACCT_RE = re.compile(r"\b\d{4,}\b")

# Quantities: "5 ", "100 ", leading integers
_QTY_RE = re.compile(r"^\d+\s+")

# Known action verbs to preserve
_ACTION_VERBS = {
    "BOUGHT", "SOLD", "BUY", "SELL",
    "REINVEST", "DIVIDEND", "INTEREST",
    "TRANSFER", "FEE", "WITHHOLDING",
    "ASSIGNED", "EXERCISED", "EXPIRED",
}

# Instrument keywords to preserve
_INSTRUMENT_WORDS = {
    "CALL", "PUT", "OPTION", "BOND", "NOTE", "COUPON",
    "MUNI", "MUNICIPAL", "STRUCTURED", "ETF",
    "MONEY", "MARKET", "SWEEP",
}


def _normalize(raw_text: str) -> str:
    """Normalize a transaction description for hashing.

    1. Strip account numbers, dates, amounts, quantities
    2. Keep: activity type, instrument description structure, brokerage
    3. Replace specific tickers with TICKER placeholder
    4. Replace specific strikes/dates with STRIKE/DATE placeholders
    """
    text = raw_text.upper().strip()

    # Replace dates before other numbers
    text = _DATE_PATTERNS.sub("DATE", text)

    # Replace dollar amounts
    text = _AMOUNT_RE.sub("AMT", text)

    # Replace account numbers (4+ digit sequences)
    text = _ACCT_RE.sub("ACCT", text)

    # Now tokenize and selectively replace
    tokens = text.split()
    normalized: list[str] = []

    for tok in tokens:
        clean = tok.strip(".,;:()")
        if clean in _ACTION_VERBS or clean in _INSTRUMENT_WORDS:
            normalized.append(clean)
        elif clean in ("DATE", "AMT", "ACCT"):
            normalized.append(clean)
        elif _TICKER_RE.fullmatch(clean) and clean not in _INSTRUMENT_WORDS:
            normalized.append("TICKER")
        elif _STRIKE_RE.fullmatch(clean):
            normalized.append("STRIKE")
        elif clean:
            # Keep structural words (prepositions, etc.) for pattern shape
            if len(clean) <= 3 and clean.isalpha():
                normalized.append(clean)
            else:
                normalized.append("X")

    return " ".join(normalized)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def compute_hash(raw_text: str, brokerage: str) -> str:
    """Normalize and hash a transaction description.

    Returns a hex SHA-256 digest of the normalized pattern + brokerage.
    """
    norm = _normalize(raw_text)
    payload = f"{brokerage.lower().strip()}|{norm}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def lookup(
    pattern_hash: str,
    brokerage: str,
    *,
    min_confidence: float = 0.85,
) -> Optional[dict[str, Any]]:
    """Check if we've seen this pattern before.

    Returns the stored classification dict if found with sufficient
    confidence, otherwise ``None``.  Side-effect: increments
    ``times_matched`` and updates ``last_matched_at``.
    """
    client = _get_supabase()
    if client is None:
        return None

    try:
        resp = (
            client.table("parsing_memory")
            .select("id, classification, confidence, source, times_matched")
            .eq("pattern_hash", pattern_hash)
            .eq("brokerage", brokerage.lower().strip())
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            return None

        row = rows[0]
        if row["confidence"] < min_confidence:
            logger.debug(
                "[MEMORY] Pattern %s… found but low confidence (%.2f < %.2f)",
                pattern_hash[:12], row["confidence"], min_confidence,
            )
            return None

        # Bump match counter
        client.table("parsing_memory").update({
            "times_matched": (row["times_matched"] or 0) + 1,
            "last_matched_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", row["id"]).execute()

        return row["classification"]

    except Exception:
        logger.warning("[MEMORY] Lookup failed for %s…", pattern_hash[:12], exc_info=True)
        return None


# Source authority ranking — higher beats lower on upsert
_SOURCE_RANK = {
    "parser": 0,
    "claude": 1,
    "user_confirmed": 2,
}


async def store(
    pattern_hash: str,
    raw_text: str,
    brokerage: str,
    classification: dict[str, Any],
    confidence: float,
    source: str,
) -> None:
    """Store a new pattern or update an existing one.

    Upsert logic: if the pattern already exists, only overwrite if the
    new ``source`` has higher authority (user_confirmed > claude > parser).
    """
    client = _get_supabase()
    if client is None:
        return

    brokerage_clean = brokerage.lower().strip()

    try:
        # Check if pattern exists
        resp = (
            client.table("parsing_memory")
            .select("id, source, confidence")
            .eq("pattern_hash", pattern_hash)
            .eq("brokerage", brokerage_clean)
            .limit(1)
            .execute()
        )
        existing = (resp.data or [None])[0]

        if existing is None:
            # Insert new
            client.table("parsing_memory").insert({
                "pattern_hash": pattern_hash,
                "raw_text": raw_text,
                "brokerage": brokerage_clean,
                "classification": classification,
                "confidence": confidence,
                "source": source,
            }).execute()
            logger.info("[MEMORY] Stored new pattern %s… (source=%s)", pattern_hash[:12], source)
        else:
            # Update only if new source outranks existing
            existing_rank = _SOURCE_RANK.get(existing["source"], -1)
            new_rank = _SOURCE_RANK.get(source, -1)
            if new_rank > existing_rank or (
                new_rank == existing_rank and confidence > existing["confidence"]
            ):
                client.table("parsing_memory").update({
                    "classification": classification,
                    "confidence": confidence,
                    "source": source,
                    "last_matched_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", existing["id"]).execute()
                logger.info(
                    "[MEMORY] Updated pattern %s… (%s→%s)",
                    pattern_hash[:12], existing["source"], source,
                )

    except Exception:
        logger.warning("[MEMORY] Store failed for %s…", pattern_hash[:12], exc_info=True)


async def get_memory_stats() -> dict[str, Any]:
    """Return aggregate stats on the pattern memory table."""
    client = _get_supabase()
    if client is None:
        return {"available": False}

    try:
        resp = (
            client.table("parsing_memory")
            .select("brokerage, source, times_matched, confidence")
            .execute()
        )
        rows = resp.data or []
        if not rows:
            return {"total_patterns": 0, "by_brokerage": {}, "by_source": {}, "avg_times_matched": 0}

        by_brokerage: dict[str, int] = {}
        by_source: dict[str, int] = {}
        total_matched = 0

        for r in rows:
            b = r.get("brokerage", "unknown")
            s = r.get("source", "unknown")
            by_brokerage[b] = by_brokerage.get(b, 0) + 1
            by_source[s] = by_source.get(s, 0) + 1
            total_matched += r.get("times_matched", 0)

        return {
            "total_patterns": len(rows),
            "by_brokerage": by_brokerage,
            "by_source": by_source,
            "avg_times_matched": round(total_matched / len(rows), 1) if rows else 0,
        }

    except Exception:
        logger.warning("[MEMORY] Stats query failed", exc_info=True)
        return {"available": False, "error": "query_failed"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_supabase():
    """Get the Supabase client, matching the existing project pattern."""
    try:
        from storage.supabase_client import _get_client
        return _get_client()
    except Exception:
        return None
