"""Orchestrator — three-layer intelligent parsing pipeline.

Main entry point that wraps the existing WFA parser with:
  Layer 0: Pattern memory lookup (instant, no API call)
  Layer 1: Existing parser + confidence scoring
  Layer 2: Claude Haiku batch classification for ambiguous rows
  Layer 3: Review queue for unresolvable rows

Position tracking and strategy detection run on every transaction
BEFORE confidence scoring, so the scorer has full context.

The existing parser is NEVER replaced — it always runs first.
The intelligence layers add classification enrichment on top.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from . import pattern_memory
from .claude_classifier import classify_batch
from .completeness import assess_completeness
from .confidence import score_confidence
from .position_tracker import PositionTracker
from .review_queue import flag_for_review
from .strategy_detector import classify_option_strategy

logger = logging.getLogger(__name__)

# Thresholds
_MEMORY_MIN_CONFIDENCE = 0.90
_PARSER_HIGH_CONFIDENCE = 0.95
_CLAUDE_ACCEPT_CONFIDENCE = 0.85


async def parse_with_intelligence(
    raw_csv_rows: list[dict[str, Any]],
    brokerage: str,
    account_positions: Optional[dict[str, Any]] = None,
    trader_id: Optional[str] = None,
    import_id: Optional[str] = None,
) -> dict[str, Any]:
    """Run the three-layer intelligent parsing pipeline.

    Parameters
    ----------
    raw_csv_rows:
        List of dicts, each representing a parsed transaction from the
        existing parser.  Expected keys: ``action``, ``symbol``,
        ``description``, ``quantity``, ``price``, ``amount``,
        ``instrument_type``, ``instrument_confidence``, ``raw_text``
        (the original CSV row string or description).
    brokerage:
        Brokerage name (e.g. ``"wells_fargo"``).
    account_positions:
        ``{symbol: quantity}`` of known positions, used for sell-side
        disambiguation.
    trader_id:
        Optional trader UUID for review queue attribution.
    import_id:
        Optional import/upload UUID for review queue attribution.

    Returns
    -------
    dict with keys:
        ``transactions``: enriched transaction list
        ``stats``: resolution statistics per layer
        ``review_needed``: list of flagged review items
        ``completeness``: portfolio completeness assessment
        ``position_summary``: final position state from tracker
    """
    positions = account_positions or {}
    transactions: list[dict[str, Any]] = []
    layer2_batch: list[dict[str, Any]] = []

    stats = {
        "total": len(raw_csv_rows),
        "layer1_resolved": 0,
        "layer2_resolved": 0,
        "layer3_flagged": 0,
        "memory_hits": 0,
        "new_patterns_learned": 0,
        "strategies_detected": 0,
        "positions_tracked": 0,
    }

    # ── Initialize position tracker ────────────────────────────────────
    tracker = PositionTracker()

    # Sort rows chronologically if they have a date field
    # (rows should already be sorted from the parser, but ensure it)
    sorted_rows = _sort_chronologically(raw_csv_rows)

    # ── Pass 1: Position tracking + Memory lookup + confidence scoring ──
    for idx, row in enumerate(sorted_rows):
        raw_text = _get_raw_text(row)
        enriched = {**row, "index": idx}

        # Step A: Position tracker — run BEFORE confidence scoring
        pos_enrichment = tracker.process_transaction(row)
        enriched.update(pos_enrichment)

        # Step B: Option strategy detection (only for options)
        inst_type = (row.get("instrument_type") or "").lower()
        if inst_type == "options":
            action = (row.get("action") or "").lower()
            if action in ("buy", "sell"):
                strategy_result = classify_option_strategy(
                    row, tracker, option_details=row.get("option_details"),
                    brokerage=brokerage,
                )
                enriched["strategy"] = strategy_result.get("strategy_key")
                enriched["strategy_name"] = strategy_result.get("strategy_name")
                enriched["strategy_confidence"] = strategy_result.get("confidence")
                enriched["strategy_details"] = strategy_result.get("details")
                if strategy_result.get("strategy_key") != "unknown_option_strategy":
                    stats["strategies_detected"] += 1

        # Layer 0: Check pattern memory
        memory_hit = None
        memory_conf = None
        if raw_text:
            try:
                pattern_hash = await pattern_memory.compute_hash(raw_text, brokerage)
                memory_hit = await pattern_memory.lookup(
                    pattern_hash, brokerage, min_confidence=_MEMORY_MIN_CONFIDENCE,
                )
                enriched["_pattern_hash"] = pattern_hash
            except Exception:
                logger.debug("[ORCHESTRATOR] Memory lookup failed for row %d", idx, exc_info=True)

        if memory_hit is not None:
            # Memory resolved this row — merge and move on
            enriched.update(memory_hit)
            enriched["classified_by"] = "memory"
            memory_conf = memory_hit.get("confidence")
            stats["memory_hits"] += 1

        # Layer 1: Score confidence (parser output + position context + memory)
        # Update positions dict with live tracker data for confidence scorer
        live_positions = {
            ticker.split(":")[-1]: info["quantity"]
            for ticker, info in tracker.get_all_positions().items()
            if info["quantity"] != 0
        }
        merged_positions = {**positions, **live_positions}

        conf = score_confidence(
            enriched, raw_text, merged_positions, memory_confidence=memory_conf,
        )
        enriched["confidence"] = conf

        if conf >= _PARSER_HIGH_CONFIDENCE:
            # High confidence — accept and store pattern
            enriched.setdefault("classified_by", "parser")
            transactions.append(enriched)
            stats["layer1_resolved"] += 1

            # Store new patterns from high-confidence parser results
            if memory_hit is None and raw_text:
                try:
                    ph = enriched.get("_pattern_hash") or await pattern_memory.compute_hash(raw_text, brokerage)
                    await pattern_memory.store(
                        pattern_hash=ph,
                        raw_text=raw_text,
                        brokerage=brokerage,
                        classification=_extract_classification(enriched),
                        confidence=conf,
                        source="parser",
                    )
                    stats["new_patterns_learned"] += 1
                except Exception:
                    logger.debug("[ORCHESTRATOR] Memory store failed for row %d", idx, exc_info=True)
        else:
            # Below threshold — queue for Layer 2
            enriched["raw_text"] = raw_text
            layer2_batch.append(enriched)

    # ── Pass 2: Claude batch classification ────────────────────────────
    review_needed: list[dict[str, Any]] = []

    if layer2_batch:
        logger.info(
            "[ORCHESTRATOR] Sending %d ambiguous rows to Claude",
            len(layer2_batch),
        )
        try:
            claude_results = await classify_batch(
                layer2_batch, merged_positions, brokerage,
            )
        except Exception:
            logger.warning("[ORCHESTRATOR] Claude classification failed entirely", exc_info=True)
            claude_results = layer2_batch  # Fall back to parser guesses

        for i, result in enumerate(claude_results):
            claude_conf = result.get("confidence", 0)

            if claude_conf >= _CLAUDE_ACCEPT_CONFIDENCE:
                # Layer 2 resolved
                result.setdefault("classified_by", "claude")
                transactions.append(result)
                stats["layer2_resolved"] += 1
                stats["new_patterns_learned"] += 1
            else:
                # Layer 3: Flag for review
                original_row = layer2_batch[i] if i < len(layer2_batch) else result
                raw_text = result.get("raw_text", "")
                parser_guess = _extract_classification(original_row)
                claude_guess = _extract_classification(result) if result.get("classified_by") == "claude" else None

                review_item = flag_for_review(
                    raw_row=raw_text,
                    parser_guess=parser_guess,
                    claude_guess=claude_guess,
                    trader_id=trader_id,
                    import_id=import_id,
                    brokerage=brokerage,
                )
                review_needed.append(review_item)

                # Still include in transactions with best guess
                result.setdefault("classified_by", "review_pending")
                transactions.append(result)
                stats["layer3_flagged"] += 1

    # ── Pass 3: Completeness assessment ────────────────────────────────
    completeness_report: dict[str, Any] = {}
    try:
        # Compute reconstructed value from buy/sell amounts
        reconstructed_value = sum(
            abs(float(t.get("amount", 0) or 0))
            for t in transactions
            if (t.get("action") or "").lower() in ("buy", "sell")
        )
        all_positions = tracker.get_all_positions()

        completeness_report = assess_completeness(
            transactions=transactions,
            positions=all_positions,
            reconstructed_value=reconstructed_value,
        )
        logger.info(
            "[COMPLETENESS] %s — %d invisible holdings detected, prompt=%s",
            completeness_report.get("completeness_confidence", "unknown"),
            completeness_report.get("invisible_holdings", {}).get("count", 0),
            completeness_report.get("prompt_for_more_data", False),
        )
    except Exception:
        logger.warning("[ORCHESTRATOR] Completeness assessment failed (non-fatal)", exc_info=True)

    # ── Position tracker stats ─────────────────────────────────────────
    tracker_stats = tracker.stats
    stats["positions_tracked"] = tracker_stats["non_zero_positions"]

    logger.info(
        "[ORCHESTRATOR] Done: %d total → L1=%d, L2=%d, L3=%d, memory=%d, "
        "learned=%d, strategies=%d, positions=%d",
        stats["total"],
        stats["layer1_resolved"],
        stats["layer2_resolved"],
        stats["layer3_flagged"],
        stats["memory_hits"],
        stats["new_patterns_learned"],
        stats["strategies_detected"],
        stats["positions_tracked"],
    )

    # Log strategy breakdown
    strategy_counts: dict[str, int] = {}
    for t in transactions:
        s = t.get("strategy")
        if s and s != "unknown_option_strategy":
            strategy_counts[s] = strategy_counts.get(s, 0) + 1
    if strategy_counts:
        breakdown = ", ".join(f"{k}={v}" for k, v in sorted(strategy_counts.items()))
        logger.info("[STRATEGY DETECTOR] %s", breakdown)

    return {
        "transactions": transactions,
        "stats": stats,
        "review_needed": review_needed,
        "completeness": completeness_report,
        "position_summary": tracker_stats,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sort_chronologically(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort rows by date if available, preserving original order otherwise."""
    def _date_key(row: dict[str, Any]) -> str:
        d = row.get("date") or row.get("trade_date") or ""
        return str(d)

    has_dates = any(row.get("date") or row.get("trade_date") for row in rows)
    if not has_dates:
        return rows
    try:
        return sorted(rows, key=_date_key)
    except Exception:
        return rows


def _get_raw_text(row: dict[str, Any]) -> str:
    """Extract the best raw text representation from a parsed row."""
    # Prefer explicit raw_text, then description, then join raw_row dict
    if row.get("raw_text"):
        return row["raw_text"]
    if row.get("description"):
        desc = row["description"]
        sym = row.get("symbol", "")
        action = row.get("raw_action") or row.get("action", "")
        return f"{action} {sym} {desc}".strip()
    if row.get("raw_row"):
        raw = row["raw_row"]
        if isinstance(raw, dict):
            return " ".join(str(v) for v in raw.values() if v)
        return str(raw)
    return ""


def _extract_classification(row: dict[str, Any]) -> dict[str, Any]:
    """Extract classification-relevant fields from an enriched row."""
    keys = (
        "instrument_type", "action", "strategy", "is_closing",
        "underlying", "confidence", "sub_type",
    )
    return {k: row[k] for k in keys if k in row}
