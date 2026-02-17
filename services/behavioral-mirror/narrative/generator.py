"""Generate Trading DNA narrative profiles using Claude API."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)


def generate_narrative(
    extracted_profile: dict[str, Any],
    classification: dict[str, Any],
    api_key: str | None = None,
) -> dict[str, Any]:
    """Generate a Trading DNA narrative from extracted features + classification.

    Args:
        extracted_profile: Full extracted feature JSON.
        classification: GMM classification result (archetype_probabilities, etc.).
        api_key: Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.

    Returns:
        Narrative dict with headline, archetype_summary, behavioral_deep_dive, etc.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        logger.warning("No ANTHROPIC_API_KEY set; returning placeholder narrative")
        return _placeholder_narrative(extracted_profile, classification)

    from narrative.prompts import SYSTEM_PROMPT, build_analysis_prompt

    user_prompt = build_analysis_prompt(extracted_profile, classification)

    # Call Claude API with one retry
    for attempt in range(2):
        try:
            return _call_claude(key, SYSTEM_PROMPT, user_prompt)
        except Exception as e:
            logger.warning("Claude API call failed (attempt %d): %s", attempt + 1, e)
            if attempt == 0:
                time.sleep(2)

    logger.error("Claude API failed after 2 attempts; returning placeholder")
    return _placeholder_narrative(extracted_profile, classification)


def _call_claude(api_key: str, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Make the actual API call to Claude."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Extract text from response
    text = message.content[0].text.strip()

    # Parse JSON (handle potential markdown fencing)
    if text.startswith("```"):
        # Strip markdown code fences
        lines = text.split("\n")
        start = 1 if lines[0].startswith("```") else 0
        end = -1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end]).strip()

    narrative = json.loads(text)
    return narrative


def _placeholder_narrative(
    profile: dict[str, Any],
    classification: dict[str, Any],
) -> dict[str, Any]:
    """Generate a data-driven placeholder when Claude API is unavailable.

    Uses the extracted features directly to create a reasonable summary.
    """
    probs = classification.get("archetype_probabilities", {})
    dominant = classification.get("dominant_archetype", "unknown")
    confidence = classification.get("confidence_score", 0)
    method = classification.get("method", "unknown")

    patterns = profile.get("patterns", {})
    hold = patterns.get("holding_period", {})
    entry = patterns.get("entry_patterns", {})
    traits = profile.get("traits", {})
    meta = profile.get("metadata", {})
    stress = profile.get("stress_response", {})
    risk = profile.get("risk_profile", {})

    # Build archetype blend description
    sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)
    top_archetypes = [(a, p) for a, p in sorted_probs if p > 0.05]

    archetype_labels = {
        "momentum": "momentum trader",
        "value": "value investor",
        "income": "income-focused investor",
        "swing": "swing trader",
        "day_trader": "day trader",
        "event_driven": "event-driven trader",
        "mean_reversion": "mean reversion trader",
        "passive_dca": "passive DCA investor",
    }

    headline_label = archetype_labels.get(dominant, dominant)
    headline = f"Your profile: {headline_label} with {hold.get('mean_days', 0):.0f}-day average holds and {patterns.get('win_rate', 0):.0%} win rate."

    if len(top_archetypes) > 1:
        blend_desc = " and ".join(
            f"{p:.0%} {archetype_labels.get(a, a)}"
            for a, p in top_archetypes[:3]
        )
        summary = (
            f"Your behavioral profile is a blend of {blend_desc}. "
            f"Your dominant pattern is {archetype_labels.get(dominant, dominant)}, "
            f"classified with {confidence:.0%} confidence using {method} analysis."
        )
    else:
        summary = (
            f"You show a clear {archetype_labels.get(dominant, dominant)} profile. "
            f"Classification confidence: {confidence:.0%} ({method})."
        )

    deep_dive = (
        f"Over your {meta.get('total_trades', 0)} trades, you enter positions "
        f"through breakouts {entry.get('breakout_pct', 0):.0%} of the time and "
        f"dip-buys {entry.get('dip_buy_pct', 0):.0%} of the time. "
        f"Your average holding period is {hold.get('mean_days', 0):.1f} days with a "
        f"standard deviation of {hold.get('std_days', 0):.1f} days. "
        f"You trade approximately {patterns.get('trade_frequency_per_month', 0):.1f} times per month."
    )

    risk_text = (
        f"Your risk appetite score: {traits.get('risk_appetite', 0)}/100. "
        f"Your average position: {risk.get('avg_position_pct', 0):.1f}% of portfolio. "
        f"Your drawdown behavior: {stress.get('drawdown_behavior', 'N/A')}. "
        f"Your discipline score: {traits.get('discipline', 0)}/100."
    )

    return {
        "headline": headline,
        "archetype_summary": summary,
        "behavioral_deep_dive": deep_dive,
        "risk_personality": risk_text,
        "tax_efficiency": None,
        "regulatory_context": None,
        "key_recommendation": "Enable Claude API (ANTHROPIC_API_KEY) for detailed, personalized recommendations.",
        "confidence_note": f"Your analysis is based on {meta.get('total_trades', 0)} trades. "
                          f"{'High' if meta.get('total_trades', 0) > 100 else 'Moderate'} confidence in your behavioral patterns.",
        "_generated_by": "placeholder",
    }
