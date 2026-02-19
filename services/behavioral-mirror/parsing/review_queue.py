"""Layer 3 — Review queue for low-confidence transactions.

When neither the parser nor Claude can classify a transaction with
sufficient confidence, it gets flagged here for eventual human review.
When a user confirms or corrects, the resolution feeds back into
pattern memory with ``source='user_confirmed'`` and ``confidence=1.0``.

Supabase table: ``parsing_review_queue``
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from . import pattern_memory

logger = logging.getLogger(__name__)


def flag_for_review(
    raw_row: str,
    parser_guess: dict[str, Any],
    claude_guess: Optional[dict[str, Any]] = None,
    trader_id: Optional[str] = None,
    import_id: Optional[str] = None,
    *,
    brokerage: str = "",
) -> dict[str, Any]:
    """Flag a transaction for human review.

    Returns a review dict suitable for display (question + alternatives).
    Also inserts a row into the ``parsing_review_queue`` Supabase table
    if available.
    """
    our_best = claude_guess if claude_guess else parser_guess
    confidence = our_best.get("confidence", 0)

    # Build human-readable interpretation
    interpretation = _describe_interpretation(our_best)
    alternative = _describe_alternative(our_best, parser_guess)
    question = _build_question(our_best)

    review = {
        "raw_text": raw_row,
        "our_interpretation": interpretation,
        "alternative": alternative,
        "confidence": confidence,
        "question": question,
        "parser_guess": parser_guess,
        "claude_guess": claude_guess,
    }

    # Persist to Supabase
    client = _get_supabase()
    if client:
        try:
            row = {
                "raw_text": raw_row,
                "our_interpretation": our_best,
                "alternatives": {
                    "parser": parser_guess,
                    "claude": claude_guess,
                } if claude_guess else {"parser": parser_guess},
                "confidence": confidence,
                "user_response": None,
                "user_correction": None,
            }
            if trader_id:
                row["trader_id"] = trader_id
            if import_id:
                row["import_id"] = import_id

            resp = client.table("parsing_review_queue").insert(row).execute()
            if resp.data:
                review["review_id"] = resp.data[0].get("id")
                logger.info("[REVIEW] Flagged for review: %s…", raw_row[:60])
        except Exception:
            logger.debug("[REVIEW] Supabase insert failed", exc_info=True)

    return review


async def resolve_review(
    review_id: str,
    response: str,
    correction: Optional[dict[str, Any]] = None,
    *,
    brokerage: str = "",
) -> None:
    """Resolve a review queue item with user feedback.

    Parameters
    ----------
    review_id:
        UUID of the ``parsing_review_queue`` row.
    response:
        One of ``"confirmed"``, ``"corrected"``, ``"skipped"``.
    correction:
        If ``response == "corrected"``, the user's classification dict.
    brokerage:
        Brokerage name for pattern memory storage.
    """
    client = _get_supabase()
    if not client:
        return

    try:
        # Read the original review
        resp = (
            client.table("parsing_review_queue")
            .select("raw_text, our_interpretation, confidence")
            .eq("id", review_id)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            logger.warning("[REVIEW] Review %s not found", review_id)
            return

        row = rows[0]
        raw_text = row["raw_text"]
        original = row["our_interpretation"]

        # Update the review row
        client.table("parsing_review_queue").update({
            "user_response": response,
            "user_correction": correction,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", review_id).execute()

        # Store resolved classification in pattern memory
        if response == "confirmed":
            final_classification = original
        elif response == "corrected" and correction:
            final_classification = correction
        else:
            return  # skipped — nothing to store

        if raw_text and brokerage:
            pattern_hash = await pattern_memory.compute_hash(raw_text, brokerage)
            await pattern_memory.store(
                pattern_hash=pattern_hash,
                raw_text=raw_text,
                brokerage=brokerage,
                classification=final_classification,
                confidence=1.0,
                source="user_confirmed",
            )
            logger.info("[REVIEW] Resolved %s (%s) → stored with confidence 1.0", review_id, response)

    except Exception:
        logger.warning("[REVIEW] Failed to resolve %s", review_id, exc_info=True)


# ---------------------------------------------------------------------------
# Human-readable description builders
# ---------------------------------------------------------------------------


def _describe_interpretation(guess: dict[str, Any]) -> str:
    """Build a human-readable string from a classification dict."""
    inst = guess.get("instrument_type", "unknown")
    action = guess.get("action", "unknown")
    strategy = guess.get("strategy")
    underlying = guess.get("underlying", "")

    parts = []
    if strategy and strategy != "standalone":
        parts.append(f"{strategy.replace('_', ' ').title()}")
    else:
        parts.append(f"{action.replace('_', ' ').title()}")

    if underlying:
        parts.append(f"on {underlying}")

    if inst not in ("unknown", ""):
        parts.append(f"({inst.replace('_', ' ')})")

    return " ".join(parts)


def _describe_alternative(best: dict[str, Any], parser: dict[str, Any]) -> str:
    """Describe the alternative interpretation."""
    best_action = best.get("action", "")
    parser_action = parser.get("action", "")

    # If they agree, there's no meaningful alternative
    if best_action == parser_action:
        return ""

    return _describe_interpretation(parser)


def _build_question(guess: dict[str, Any]) -> str:
    """Build a yes/no question for the user."""
    strategy = guess.get("strategy", "")
    action = guess.get("action", "")
    underlying = guess.get("underlying", "")

    if strategy == "covered_call" and underlying:
        return f"Is this a covered call against your {underlying} shares?"
    if action in ("sell_to_open", "sell_to_close"):
        return f"Is this opening a new short position or closing an existing one?"
    if action == "assignment":
        return "Were you assigned on this option position?"

    return "Does this classification look correct?"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_supabase():
    """Get the Supabase client."""
    try:
        from storage.supabase_client import _get_client
        return _get_client()
    except Exception:
        return None
