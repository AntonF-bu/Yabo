"""Generate Trading DNA narrative profiles using Claude API.

This module produces the behavioral narrative from the 212-feature engine
output and 8-dimension classifier scores.  The old extractor is no longer
required.  If the Claude API is unavailable, a data-driven placeholder is
generated from the features dict.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)


# ── Confidence tier helpers ─────────────────────────────────────────────────

def _get_confidence_tier(total_trades: int) -> tuple[str, str]:
    """Return (tier_key, tier_label) based on trade count."""
    if total_trades < 15:
        return "insufficient", "Insufficient Data"
    if total_trades < 30:
        return "preliminary", "Preliminary"
    if total_trades < 75:
        return "emerging", "Emerging"
    if total_trades < 150:
        return "developing", "Developing"
    return "confident", "Confident"


def _safe(features: dict, key: str, default: float = 0.0) -> float:
    """Get a feature value safely."""
    v = features.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ── Public API ──────────────────────────────────────────────────────────────

def generate_narrative(
    features: dict[str, Any],
    dimensions: dict[str, Any],
    classification_v2: dict[str, Any] | None = None,
    profile_meta: dict[str, Any] | None = None,
    api_key: str | None = None,
    holdings_features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a Trading DNA narrative from the 212-feature engine output.

    Args:
        features: Flat dict from ``extract_all_features()`` (212 features).
        dimensions: The 8-dimension scores dict (from ``classify_v2()["dimensions"]``).
        classification_v2: Full ``classify_v2()`` output (archetype, summary, etc.).
        profile_meta: Optional dict with profile_id, tax_jurisdiction, etc.
        api_key: Anthropic API key. Falls back to ``ANTHROPIC_API_KEY`` env var.
        holdings_features: Optional dict of 69 h_ features from HoldingsExtractor.
            When provided, enriches the narrative with portfolio structure context.

    Returns:
        Narrative dict with headline, archetype_summary, behavioral_deep_dive,
        risk_personality, tax_efficiency, regulatory_context, key_recommendation,
        confidence_note, confidence_metadata, and _generated_by.
    """
    total_trades = int(_safe(features, "portfolio_total_round_trips"))
    confidence_tier, tier_label = _get_confidence_tier(total_trades)

    # For insufficient data (<15 trades), skip Claude entirely
    if confidence_tier == "insufficient":
        logger.info("Insufficient data (%d trades) — returning template narrative", total_trades)
        result = _insufficient_data_narrative(features)
        result["confidence_metadata"] = {
            "tier": confidence_tier,
            "total_trades": total_trades,
            "tier_label": tier_label,
        }
        return result

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        logger.warning("No ANTHROPIC_API_KEY set; returning placeholder narrative")
        result = _placeholder_narrative(features, dimensions, classification_v2, holdings_features)
        result["confidence_metadata"] = {
            "tier": confidence_tier,
            "total_trades": total_trades,
            "tier_label": tier_label,
        }
        return result

    from narrative.prompts import get_tier_system_prompt, build_analysis_prompt

    system_prompt = get_tier_system_prompt(confidence_tier)
    user_prompt = build_analysis_prompt(
        features, dimensions,
        classification_v2=classification_v2,
        profile_meta=profile_meta,
        holdings_features=holdings_features,
    )

    # Call Claude API with one retry
    for attempt in range(2):
        try:
            result = _call_claude(key, system_prompt, user_prompt)
            result["confidence_metadata"] = {
                "tier": confidence_tier,
                "total_trades": total_trades,
                "tier_label": tier_label,
            }
            result["_generated_by"] = "claude"
            if holdings_features:
                result["holdings_context_included"] = True
            return result
        except Exception as e:
            logger.warning("Claude API call failed (attempt %d): %s", attempt + 1, e)
            if attempt == 0:
                time.sleep(2)

    logger.error("Claude API failed after 2 attempts; returning placeholder")
    result = _placeholder_narrative(features, dimensions, classification_v2, holdings_features)
    result["confidence_metadata"] = {
        "tier": confidence_tier,
        "total_trades": total_trades,
        "tier_label": tier_label,
    }
    return result


# ── Claude API call ─────────────────────────────────────────────────────────

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

    text = message.content[0].text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1 if lines[0].startswith("```") else 0
        end = -1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end]).strip()

    narrative = json.loads(text)
    return narrative


# ── Insufficient data template ──────────────────────────────────────────────

def _insufficient_data_narrative(features: dict[str, Any]) -> dict[str, Any]:
    """Template narrative for insufficient data (<15 trades)."""
    total = int(_safe(features, "portfolio_total_round_trips"))
    mean_days = _safe(features, "holding_mean_days")
    win_rate = _safe(features, "portfolio_win_rate")

    return {
        "headline": f"Early snapshot from {total} trades — more data needed for a full profile.",
        "archetype_summary": (
            f"With only {total} trades on record, it is too early to identify a reliable "
            f"trading archetype. Initial patterns may emerge after 30+ trades."
        ),
        "behavioral_deep_dive": (
            f"Your {total} trades show an average holding period of "
            f"{mean_days:.0f} days with a win rate of "
            f"{win_rate:.0%}. These numbers will become meaningful "
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


# ── Placeholder narrative (no API key or API failure) ───────────────────────

def _placeholder_narrative(
    features: dict[str, Any],
    dimensions: dict[str, Any],
    classification_v2: dict[str, Any] | None = None,
    holdings_features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Data-driven placeholder when Claude API is unavailable.

    Uses the 212 features and 8 dimensions to produce a reasonable summary
    without calling any external API.
    """
    cv2 = classification_v2 or {}
    archetype = cv2.get("primary_archetype", "trader")
    cv2_summary = cv2.get("behavioral_summary", "")

    total_trades = int(_safe(features, "portfolio_total_round_trips"))
    mean_days = _safe(features, "holding_mean_days")
    median_days = _safe(features, "holding_median_days")
    win_rate = _safe(features, "portfolio_win_rate")
    profit_factor = _safe(features, "portfolio_profit_factor")
    trade_days = _safe(features, "timing_trading_days_per_month")
    trades_per_day = _safe(features, "timing_avg_trades_per_active_day")
    breakout = _safe(features, "entry_breakout_score")
    dip_buy = _safe(features, "entry_dip_buyer_score")
    max_pos = _safe(features, "sizing_max_single_trade_pct")
    avg_pos = _safe(features, "sizing_avg_position_pct")
    revenge = _safe(features, "psych_revenge_score")
    sizing_after = _safe(features, "sizing_after_losses", 1.0)
    winner_ratio = _safe(features, "holding_winner_vs_loser_ratio", 1.0)
    options_pct = _safe(features, "instrument_options_pct")
    meme_rate = _safe(features, "social_meme_rate")
    tickers = int(_safe(features, "instrument_unique_tickers"))

    # ── Headline ────────────────────────────────────────────────────────
    if options_pct > 0.1:
        headline = (
            f"You are a multi-instrument {archetype.lower()} holding positions "
            f"for {median_days:.0f} days on average."
        )
    else:
        headline = (
            f"You are a {archetype.lower()} with a {win_rate:.0%} win rate "
            f"across {total_trades} analyzed trades."
        )

    # ── Archetype summary ───────────────────────────────────────────────
    if cv2_summary:
        summary = (
            f"{cv2_summary} Your classification as a {archetype} was determined "
            f"from 8 behavioral dimensions across {total_trades} trades."
        )
    else:
        summary = (
            f"Across {total_trades} trades, you show a clear {archetype.lower()} profile. "
            f"Your median hold is {median_days:.0f} days with a {win_rate:.0%} win rate."
        )

    # ── Behavioral deep dive ────────────────────────────────────────────
    entry_style = "breakout entries" if breakout > dip_buy else "dip-buying"
    deep_dive = (
        f"Over {total_trades} round trips in the analyzed portion of your portfolio, "
        f"you favor {entry_style} and hold positions for a median of {median_days:.0f} days. "
        f"You trade {trade_days:.0f} days per month, averaging {trades_per_day:.1f} "
        f"trades per active day across {tickers} unique tickers. "
    )

    if winner_ratio > 1.3:
        deep_dive += (
            f"You show patience with winners, holding them {winner_ratio:.1f}x longer "
            f"than losers, which is a disciplined asymmetry. "
        )
    elif winner_ratio < 0.7:
        deep_dive += (
            f"You tend to cut winners early and hold losers longer "
            f"({winner_ratio:.1f}x ratio), suggesting difficulty letting winners run. "
        )

    deep_dive += (
        f"Your profit factor of {profit_factor:.2f} and {win_rate:.0%} win rate "
        f"define the economics of your trading in this data window."
    )

    # ── Holdings context (if available) ──────────────────────────────
    holdings_summary = None
    if holdings_features:
        hf = holdings_features
        h_total = hf.get("h_total_value")
        h_accounts = hf.get("h_account_count")
        h_types = hf.get("h_instrument_type_count")
        h_soph = hf.get("h_overall_sophistication")

        parts = []
        if h_total and h_accounts:
            parts.append(
                f"Your broader portfolio spans {h_accounts} accounts "
                f"with an estimated value of ${h_total:,.0f}"
            )
        if h_types and h_types > 1:
            parts.append(f"across {h_types} instrument types")
        if hf.get("h_covered_call_count", 0) > 0:
            parts.append(
                f"including {hf['h_covered_call_count']} covered call positions"
            )
        if h_soph is not None:
            level = "high" if h_soph > 70 else "moderate" if h_soph > 40 else "basic"
            parts.append(f"with {level} overall sophistication")

        if parts:
            holdings_summary = ". ".join(parts) + "."
            deep_dive += f" {holdings_summary}"

    # ── Risk personality ────────────────────────────────────────────────
    risk_text = (
        f"Your average position is {avg_pos:.0%} of portfolio "
        f"(peak: {max_pos:.0%}). "
    )
    if revenge > 0.3:
        risk_text += (
            f"After losses, you show signs of reactive trading, "
            f"sizing positions {sizing_after:.1f}x relative to your normal size. "
        )
    elif sizing_after > 1.2:
        risk_text += (
            f"You tend to increase your position sizes to {sizing_after:.1f}x "
            f"after losses, which amplifies drawdowns. "
        )
    else:
        risk_text += "Your sizing stays relatively stable through winning and losing streaks. "

    risk_dim = dimensions.get("risk_seeking_averse", {})
    risk_label = risk_dim.get("label", "")
    if risk_label:
        risk_text += f"Your overall risk profile is classified as {risk_label}."

    # ── Key recommendation ──────────────────────────────────────────────
    if winner_ratio < 0.8:
        rec = (
            f"Focus on holding your winners longer. Your current ratio of "
            f"{winner_ratio:.1f}x (winners vs losers hold time) suggests you "
            f"cut winners too early. Aim for a 1.5x ratio by adding a trailing stop "
            f"rule instead of taking profits immediately."
        )
    elif meme_rate > 0.2:
        rec = (
            f"Reduce your meme stock exposure from {meme_rate:.0%} to under 10%. "
            f"These positions carry outsized volatility that may not align with "
            f"your overall strategy."
        )
    elif profit_factor < 1.0 and win_rate < 0.45:
        rec = (
            f"Your profit factor of {profit_factor:.2f} combined with a {win_rate:.0%} "
            f"win rate means losses outweigh gains. Consider tightening your stop-loss "
            f"to improve the loss side of the equation."
        )
    else:
        rec = (
            f"With {trade_days:.0f} trading days per month and "
            f"{median_days:.0f}-day median holds, review whether your trading "
            f"frequency is justified by your {profit_factor:.2f} profit factor."
        )

    # ── Confidence note ─────────────────────────────────────────────────
    if total_trades >= 150:
        conf_note = (
            f"Analysis based on {total_trades} trades from the analyzed portion "
            f"of your portfolio. High confidence in behavioral patterns."
        )
    elif total_trades >= 75:
        conf_note = (
            f"Analysis based on {total_trades} trades. "
            f"Moderate confidence — patterns are reliable at this sample size."
        )
    else:
        conf_note = (
            f"Analysis based on {total_trades} trades. "
            f"Patterns may evolve as more data becomes available."
        )

    result = {
        "headline": headline,
        "archetype_summary": summary,
        "behavioral_deep_dive": deep_dive,
        "risk_personality": risk_text,
        "tax_efficiency": None,
        "regulatory_context": None,
        "key_recommendation": rec,
        "confidence_note": conf_note,
        "_generated_by": "placeholder",
    }
    if holdings_features:
        result["holdings_context_included"] = True
    return result
