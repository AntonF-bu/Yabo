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
        Includes confidence_metadata with tier information.
    """
    # Determine confidence tier
    confidence_meta = extracted_profile.get("confidence_metadata", {})
    confidence_tier = confidence_meta.get("confidence_tier", "emerging")
    total_trades = confidence_meta.get("total_trades",
                                       extracted_profile.get("metadata", {}).get("total_trades", 0))

    # For insufficient data (<15 trades), skip Claude entirely
    if confidence_tier == "insufficient":
        logger.info("Insufficient data (%d trades) — returning template narrative", total_trades)
        result = _insufficient_data_narrative(extracted_profile, classification)
        result["confidence_metadata"] = {
            "tier": confidence_tier,
            "total_trades": total_trades,
            "tier_label": "Insufficient Data",
        }
        return result

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        logger.warning("No ANTHROPIC_API_KEY set; returning placeholder narrative")
        result = _placeholder_narrative(extracted_profile, classification)
        result["confidence_metadata"] = {
            "tier": confidence_tier,
            "total_trades": total_trades,
            "tier_label": confidence_tier.title(),
        }
        return result

    from narrative.prompts import get_tier_system_prompt, build_analysis_prompt

    system_prompt = get_tier_system_prompt(confidence_tier)
    user_prompt = build_analysis_prompt(extracted_profile, classification)

    # Call Claude API with one retry
    for attempt in range(2):
        try:
            result = _call_claude(key, system_prompt, user_prompt)
            result["confidence_metadata"] = {
                "tier": confidence_tier,
                "total_trades": total_trades,
                "tier_label": confidence_tier.title(),
            }
            result["_generated_by"] = "claude"
            return result
        except Exception as e:
            logger.warning("Claude API call failed (attempt %d): %s", attempt + 1, e)
            if attempt == 0:
                time.sleep(2)

    logger.error("Claude API failed after 2 attempts; returning placeholder")
    result = _placeholder_narrative(extracted_profile, classification)
    result["confidence_metadata"] = {
        "tier": confidence_tier,
        "total_trades": total_trades,
        "tier_label": confidence_tier.title(),
    }
    return result


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


def _insufficient_data_narrative(
    profile: dict[str, Any],
    classification: dict[str, Any],
) -> dict[str, Any]:
    """Generate a template narrative for insufficient data (<15 trades).

    Does not call Claude API. Returns honest assessment of data limitations.
    """
    meta = profile.get("metadata", {})
    total = meta.get("total_trades", 0)
    patterns = profile.get("patterns", {})
    hold = patterns.get("holding_period", {})

    return {
        "headline": f"Early snapshot from {total} trades — more data needed for a full profile.",
        "archetype_summary": (
            f"With only {total} trades on record, it is too early to identify a reliable "
            f"trading archetype. Initial patterns may emerge after 30+ trades."
        ),
        "behavioral_deep_dive": (
            f"Your {total} trades show an average holding period of "
            f"{hold.get('mean_days', 0):.0f} days with a win rate of "
            f"{patterns.get('win_rate', 0):.0%}. These numbers will become meaningful "
            f"with a larger sample. Upload more trade history for a complete analysis."
        ),
        "risk_personality": (
            "Risk patterns require at least 15-20 trades to establish. "
            "Continue trading and re-upload for risk analysis."
        ),
        "tax_efficiency": None,
        "regulatory_context": None,
        "key_recommendation": (
            "Continue building your trade history. A meaningful behavioral analysis "
            "requires at least 30 trades, ideally 75+."
        ),
        "confidence_note": (
            f"Analysis based on only {total} trades. "
            f"Insufficient data for reliable pattern detection."
        ),
        "_generated_by": "template_insufficient",
    }


def _placeholder_narrative(
    profile: dict[str, Any],
    classification: dict[str, Any],
) -> dict[str, Any]:
    """Generate a data-driven placeholder when Claude API is unavailable.

    Uses the extracted features directly to create a reasonable summary.
    Incorporates jurisdiction-specific tax data from centralized JSON.
    """
    probs = classification.get("archetype_probabilities", {})
    dominant = classification.get("dominant_archetype", "unknown")
    confidence = classification.get("confidence_score", 0)
    method = classification.get("method", "unknown")

    patterns = profile.get("patterns", {})
    hold = patterns.get("holding_period", {})
    entry = patterns.get("entry_patterns", {})
    exit_p = patterns.get("exit_patterns", {})
    traits = profile.get("traits", {})
    meta = profile.get("metadata", {})
    stress = profile.get("stress_response", {})
    risk = profile.get("risk_profile", {})
    context = profile.get("context_factors", {})
    dist = hold.get("distribution", {})

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
    headline = (
        f"You are a {headline_label} who holds positions for "
        f"{hold.get('mean_days', 0):.0f} days on average with a "
        f"{patterns.get('win_rate', 0):.0%} win rate."
    )

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

    # Behavioral deep dive — describe patterns without raw scores
    mean_days = hold.get("mean_days", 0)
    breakout_pct = entry.get("breakout_pct", 0)
    dip_buy_pct = entry.get("dip_buy_pct", 0)
    trade_freq = patterns.get("trade_frequency_per_month", 0)
    winner_hold = exit_p.get("avg_winner_hold_days", 0)
    loser_hold = exit_p.get("avg_loser_hold_days", 0)

    deep_dive = (
        f"Over {meta.get('total_trades', 0)} trades, you favor "
        f"{'breakout entries' if breakout_pct > dip_buy_pct else 'dip-buying'} "
        f"({max(breakout_pct, dip_buy_pct):.0%} of entries), holding positions "
        f"for {mean_days:.1f} days on average. "
    )
    if winner_hold > 0 and loser_hold > 0:
        if winner_hold > loser_hold * 1.3:
            deep_dive += (
                f"You show patience with winners (holding {winner_hold:.0f} days) "
                f"while cutting losers faster ({loser_hold:.0f} days), which is a "
                f"disciplined asymmetry. "
            )
        elif loser_hold > winner_hold * 1.3:
            deep_dive += (
                f"You tend to hold losers longer ({loser_hold:.0f} days) than "
                f"winners ({winner_hold:.0f} days), suggesting difficulty cutting losses. "
            )
    deep_dive += f"You average {trade_freq:.1f} trades per month."

    # Risk personality — describe behavior, not scores
    nw_pct = risk.get("portfolio_pct_of_net_worth")
    avg_pos = risk.get("avg_position_pct", 0)
    max_pos = risk.get("max_position_pct", 0)
    dd_behavior = stress.get("drawdown_behavior", "N/A")
    max_dd = stress.get("max_drawdown_pct", 0)

    risk_text = (
        f"Your average position is {avg_pos:.1f}% of portfolio "
        f"(peak: {max_pos:.1f}%), and your response to drawdowns is "
        f"to {dd_behavior.replace('_', ' ')}. "
    )
    if nw_pct is not None:
        if nw_pct > 70:
            risk_text += (
                f"With {nw_pct}% of your net worth in this account, "
                f"your trading losses have outsized impact on your financial life. "
            )
        elif nw_pct < 30:
            risk_text += (
                f"With only {nw_pct}% of your net worth allocated here, "
                f"you have room for aggressive strategies. "
            )
    if max_dd > 0:
        risk_text += f"Your worst drawdown reached {max_dd:.1f}%."

    # Tax efficiency — jurisdiction-aware
    tax_text = None
    tax_jur = context.get("tax_jurisdiction")
    if tax_jur:
        try:
            from tax_data import get_jurisdiction
            jur_data = get_jurisdiction(tax_jur)
        except Exception:
            jur_data = None

        if jur_data:
            label = jur_data.get("label", tax_jur)
            combined_st = jur_data.get("combined_short_term", 0)
            combined_lt = jur_data.get("combined_long_term", 0)
            quirks = jur_data.get("quirks")
            short_pct = dist.get("intraday", 0) + dist.get("1_5_days", 0) + dist.get("5_20_days", 0)

            tax_text = f"In {label}, your combined tax rate ranges from {combined_lt:.0%} (long-term) to {combined_st:.0%} (short-term). "
            if short_pct > 0.8 and mean_days < 30:
                tax_text += (
                    f"With {short_pct:.0%} of your trades held under 20 days, "
                    f"virtually all gains are taxed at the higher short-term rate. "
                    f"At your trading frequency, this is the cost of your strategy. "
                )
            elif context.get("ltcg_optimization_detected"):
                tax_text += "Your data shows evidence of long-term capital gains optimization. "
            if quirks:
                tax_text += quirks
        else:
            tax_rate = context.get("tax_rate", 0)
            tax_text = f"Your jurisdiction ({tax_jur}) has an effective rate of {tax_rate:.0%}."

    # Regulatory context
    reg_text = None
    if context.get("pdt_constrained"):
        reg_text = (
            "Your account is under $25,000 and subject to the Pattern Day Trader rule, "
            "limiting you to 3 day trades per rolling 5-day period. "
            "This constraint likely forces you to hold positions longer than your "
            "natural trading style would prefer."
        )

    # Data completeness context
    data_comp = profile.get("data_completeness", {})
    inherited = profile.get("inherited_positions", {})
    is_partial = data_comp.get("score") in ("partial", "mostly_complete")

    # Prefix deep dive with data completeness note if partial
    if is_partial:
        inherited_count = data_comp.get("inherited_exits", 0)
        closed_count = data_comp.get("closed_round_trips", 0)
        deep_dive = (
            f"This analysis covers a partial window of your trading activity. "
            f"{inherited_count} position exits appear to predate this window, so "
            f"performance metrics reflect only {closed_count} fully-tracked round trips. "
        ) + deep_dive

        # Add inherited position insight
        if inherited and inherited.get("count", 0) > 0:
            sectors_exited = inherited.get("sectors_exited", {})
            if sectors_exited:
                top_sectors = sorted(
                    sectors_exited.items(), key=lambda x: x[1]["proceeds"], reverse=True
                )[:3]
                sector_desc = ", ".join(
                    f"{s} ({', '.join(d['tickers'][:3])})" for s, d in top_sectors
                )
                deep_dive += (
                    f" Your recent activity shows exits from longer-held positions in "
                    f"{sector_desc}, suggesting a portfolio rotation. "
                )

    # Single recommendation — one specific action
    if is_partial:
        rec = (
            f"Upload your full trading history for a more complete analysis. "
            f"With {data_comp.get('inherited_exits', 0)} position exits predating this data, "
            f"performance metrics may not represent your overall trading performance."
        )
    elif mean_days < 30 and patterns.get("win_rate", 0) < 0.45:
        rec = (
            f"Consider tightening your stop-loss. Your average loser "
            f"({patterns.get('avg_loser_pct', 0):.1f}%) is large relative to your "
            f"{patterns.get('win_rate', 0):.0%} win rate. "
            f"A stop at {abs(patterns.get('avg_loser_pct', 0)) * 0.7:.1f}% could improve your profit factor."
        )
    elif loser_hold > winner_hold * 1.3:
        rec = (
            f"Aim to cut your average loser hold time from {loser_hold:.0f} days to "
            f"{winner_hold:.0f} days to match how you treat winners. "
            f"This single change would reduce loss magnitude without changing your entry strategy."
        )
    else:
        rec = (
            f"With {trade_freq:.0f} trades per month and {mean_days:.0f}-day average holds, "
            f"review whether your trading frequency is justified by your "
            f"{patterns.get('profit_factor', 0):.2f} profit factor."
        )

    # Confidence note — data-completeness-aware
    if is_partial:
        conf_note = (
            f"Analysis based on {meta.get('total_trades', 0)} trades from a partial data window. "
            f"Performance metrics computed on {data_comp.get('closed_round_trips', 0)} closed round trips only."
        )
    else:
        conf_note = (
            f"Analysis based on {meta.get('total_trades', 0)} trades. "
            f"{'High' if meta.get('total_trades', 0) > 100 else 'Moderate'} confidence in behavioral patterns."
        )

    return {
        "headline": headline,
        "archetype_summary": summary,
        "behavioral_deep_dive": deep_dive,
        "risk_personality": risk_text,
        "tax_efficiency": tax_text,
        "regulatory_context": reg_text,
        "key_recommendation": rec,
        "confidence_note": conf_note,
        "_generated_by": "placeholder",
    }
