"""Layer 2 — Batch-classify ambiguous transactions using Claude Haiku.

When the existing parser + confidence scorer cannot resolve a transaction
with high confidence, this module sends a batch to Claude for
classification.  Results are stored back into pattern memory so future
imports of the same pattern skip the LLM call entirely.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from . import pattern_memory

logger = logging.getLogger(__name__)

# Maximum rows per single Claude API call
_BATCH_SIZE = 50

_SYSTEM_PROMPT = (
    "You are classifying financial transactions from a brokerage CSV export.\n"
    "For each transaction, determine:\n"
    "- instrument_type: equity, option, bond, etf, structured_product, "
    "mutual_fund, cash, dividend, interest, fee, transfer, unknown\n"
    "- action: buy, sell, sell_to_open, sell_to_close, buy_to_open, "
    "buy_to_close, exercise, assignment, expire, transfer\n"
    "- strategy: if options, classify strategy given account positions. "
    "Options: covered_call, cash_secured_put, protective_put, collar, "
    "call_spread, put_spread, naked_call, naked_put, long_call, long_put, "
    "straddle, strangle, standalone\n"
    "- is_closing: true if closing an existing position\n"
    "- underlying: base ticker symbol\n"
    "- confidence: your confidence 0-1\n\n"
    "Respond as a JSON array only. No explanation. One object per transaction "
    "in the same order as the input."
)


def _build_user_prompt(
    batch: list[dict[str, Any]],
    account_context: dict[str, Any],
    brokerage: str,
) -> str:
    """Build the user-message prompt for a single batch."""
    positions_json = json.dumps(account_context, default=str)

    rows_for_prompt: list[dict[str, Any]] = []
    for item in batch:
        rows_for_prompt.append({
            "index": item.get("index", 0),
            "raw_text": item.get("raw_text", ""),
            "parser_guess": {
                "action": item.get("action", ""),
                "instrument_type": item.get("instrument_type", ""),
                "symbol": item.get("symbol", ""),
            },
            "parser_confidence": item.get("confidence", 0),
        })

    return (
        f"Brokerage: {brokerage}\n"
        f"Current positions in account: {positions_json}\n\n"
        f"Classify these transactions:\n"
        f"{json.dumps(rows_for_prompt, indent=2)}"
    )


def _call_haiku(system_prompt: str, user_prompt: str, api_key: str) -> list[dict[str, Any]]:
    """Call Claude Haiku and parse the JSON array response."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text = message.content[0].text.strip()

    # Strip markdown fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1 if lines[0].startswith("```") else 0
        end = -1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end]).strip()

    return json.loads(text)


async def classify_batch(
    ambiguous_rows: list[dict[str, Any]],
    account_context: dict[str, Any],
    brokerage: str,
    *,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """Batch-classify ambiguous transactions using Claude Haiku.

    Parameters
    ----------
    ambiguous_rows:
        List of dicts, each with at least ``raw_text``, ``action``,
        ``instrument_type``, ``symbol``, ``confidence``, ``index``
        (index into the original transaction list).
    account_context:
        ``{symbol: quantity}`` of current known positions in the account.
    brokerage:
        Brokerage name for formatting context and pattern memory.
    api_key:
        Anthropic API key.  Falls back to ``ANTHROPIC_API_KEY`` env var.

    Returns
    -------
    list[dict]
        One classification dict per input row (same order), each with:
        ``instrument_type``, ``action``, ``strategy``, ``is_closing``,
        ``underlying``, ``confidence``.  On failure, returns the
        parser's original guess with confidence unchanged.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        logger.warning("[CLAUDE_CLASSIFIER] No API key; returning rows unchanged")
        return ambiguous_rows

    results: list[dict[str, Any]] = []

    # Process in batches of _BATCH_SIZE
    for start in range(0, len(ambiguous_rows), _BATCH_SIZE):
        batch = ambiguous_rows[start : start + _BATCH_SIZE]

        try:
            user_prompt = _build_user_prompt(batch, account_context, brokerage)
            classifications = _call_haiku(_SYSTEM_PROMPT, user_prompt, key)

            if not isinstance(classifications, list):
                logger.warning("[CLAUDE_CLASSIFIER] Expected list, got %s", type(classifications))
                results.extend(batch)
                continue

            # Merge Claude's classifications with original rows
            for i, item in enumerate(batch):
                if i < len(classifications):
                    claude_result = classifications[i]
                    merged = {**item, **claude_result, "classified_by": "claude"}
                    results.append(merged)

                    # Store in pattern memory
                    raw_text = item.get("raw_text", "")
                    if raw_text:
                        try:
                            pattern_hash = await pattern_memory.compute_hash(raw_text, brokerage)
                            await pattern_memory.store(
                                pattern_hash=pattern_hash,
                                raw_text=raw_text,
                                brokerage=brokerage,
                                classification=claude_result,
                                confidence=claude_result.get("confidence", 0.85),
                                source="claude",
                            )
                        except Exception:
                            logger.debug("[CLAUDE_CLASSIFIER] Memory store failed", exc_info=True)
                else:
                    results.append(item)

            logger.info(
                "[CLAUDE_CLASSIFIER] Batch %d-%d: classified %d/%d rows",
                start, start + len(batch), min(len(classifications), len(batch)), len(batch),
            )

        except Exception:
            logger.warning(
                "[CLAUDE_CLASSIFIER] Batch %d-%d failed; returning parser guesses",
                start, start + len(batch), exc_info=True,
            )
            results.extend(batch)

    return results
