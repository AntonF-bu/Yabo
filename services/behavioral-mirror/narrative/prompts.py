"""System prompts and output format templates for narrative generation."""

SYSTEM_PROMPT = """\
You are the Behavioral Mirror, an expert trading psychologist and quantitative analyst. \
You analyze traders the way a world-class portfolio manager would evaluate a candidate \
for their fund. You are direct, precise, and insightful. You do not flatter or soften \
your observations. You speak with authority because your analysis is backed by rigorous \
quantitative data.

Your job is to take pre-computed behavioral features and classification scores, and \
generate a Trading DNA profile that:

1. Opens with a one-sentence characterization that captures the trader's essence
2. Identifies their dominant strategy and how it manifests in actual behavior
3. Surfaces one non-obvious pattern they probably don't know about themselves
4. Addresses their relationship with risk through the lens of their actual decisions, \
not what they'd say in a questionnaire
5. Evaluates tax efficiency relative to their jurisdiction
6. Identifies the single behavioral change that would most improve their performance
7. If regulatory constraints are detected (PDT, options level), distinguishes between \
chosen behavior and forced behavior

Tone: authoritative but not cold. Like a mentor who respects the trader enough to be \
honest. Never use financial jargon without context. Never hedge with "it appears" or \
"it seems" -- the data is definitive, speak definitively.

Never use emojis. Never use bullet points in the narrative sections. Write in flowing \
prose paragraphs.

Format your response as JSON with these fields:
{
  "headline": "One sentence, max 15 words. The trader's essence.",
  "archetype_summary": "2-3 sentences. What kind of trader they are and their blend.",
  "behavioral_deep_dive": "2-3 paragraphs. The detailed analysis. Entry patterns, exit patterns, holding behavior, sector preferences. This is where the non-obvious insight lives.",
  "risk_personality": "1-2 paragraphs. How they actually handle risk, drawdowns, losses. Not what they'd say, what they do.",
  "tax_efficiency": "1 paragraph. Only if tax_jurisdiction is provided. Specific, actionable.",
  "regulatory_context": "1 paragraph. Only if PDT or options constraints detected. Distinguishes chosen vs forced behavior.",
  "key_recommendation": "2-3 sentences. The single most impactful behavioral change. Specific and data-backed.",
  "confidence_note": "1 sentence. How confident the analysis is based on trade count and data quality."
}

Return ONLY the JSON object. No markdown fencing, no preamble, no explanation outside the JSON."""


def build_analysis_prompt(
    extracted_profile: dict,
    classification: dict,
) -> str:
    """Build the user prompt with all computed features and classification data.

    The prompt feeds Claude specific numbers so the narrative is grounded in data.
    """
    patterns = extracted_profile.get("patterns", {})
    hold = patterns.get("holding_period", {})
    entry = patterns.get("entry_patterns", {})
    exit_p = patterns.get("exit_patterns", {})
    tc = patterns.get("ticker_concentration", {})
    traits = extracted_profile.get("traits", {})
    stress = extracted_profile.get("stress_response", {})
    risk = extracted_profile.get("risk_profile", {})
    context = extracted_profile.get("context_factors", {})
    active_passive = extracted_profile.get("active_vs_passive", {})
    meta = extracted_profile.get("metadata", {})
    dist = hold.get("distribution", {})

    # Classification data
    probs = classification.get("archetype_probabilities", {})
    dominant = classification.get("dominant_archetype", "unknown")
    confidence = classification.get("confidence_score", 0)

    # Format archetype blend as readable string
    sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)
    blend_str = ", ".join(f"{a}: {p:.1%}" for a, p in sorted_probs if p > 0.02)

    # Sectors
    sectors = patterns.get("dominant_sectors", [])
    sector_str = ", ".join(
        f"{s['sector']} ({s['weight']:.0%})" for s in sectors[:4]
    ) if sectors else "no sector data"

    # Top tickers
    top_tickers = tc.get("top_3_tickers", [])
    ticker_str = ", ".join(top_tickers) if top_tickers else "N/A"

    prompt = f"""Analyze this trader's behavioral data and generate a Trading DNA profile.

CLASSIFICATION:
- Dominant archetype: {dominant}
- Full blend: {blend_str}
- Classification confidence: {confidence:.0%}
- Method: {classification.get('method', 'unknown')}

HOLDING BEHAVIOR:
- Mean holding period: {hold.get('mean_days', 0):.1f} days
- Median holding period: {hold.get('median_days', 0):.1f} days
- Holding period std dev: {hold.get('std_days', 0):.1f} days
- Distribution: intraday {dist.get('intraday', 0):.0%}, 1-5 days {dist.get('1_5_days', 0):.0%}, \
5-20 days {dist.get('5_20_days', 0):.0%}, 20-90 days {dist.get('20_90_days', 0):.0%}, \
90-365 days {dist.get('90_365_days', 0):.0%}, 365+ days {dist.get('365_plus_days', 0):.0%}
- Avg winner hold: {exit_p.get('avg_winner_hold_days', 0):.1f} days
- Avg loser hold: {exit_p.get('avg_loser_hold_days', 0):.1f} days

ENTRY PATTERNS:
- Breakout entries (above MA + volume): {entry.get('breakout_pct', 0):.0%}
- Dip-buy entries (below recent highs): {entry.get('dip_buy_pct', 0):.0%}
- Earnings-proximity entries: {entry.get('earnings_proximity_pct', 0):.0%}
- Entries above 20-day MA: {entry.get('pct_above_ma20', 0.5):.0%}
- Entries below 20-day MA: {entry.get('pct_below_ma20', 0.5):.0%}
- Avg RSI at entry: {entry.get('avg_rsi_at_entry', 50):.1f}
- Avg MA deviation at entry: {entry.get('avg_entry_ma20_deviation', 0):.2%}
- Avg volume ratio at entry: {entry.get('avg_vol_ratio_at_entry', 1.0):.2f}x
- DCA pattern detected: {entry.get('dca_pattern_detected', False)}
- DCA soft signal: {entry.get('dca_soft_detected', False)}

EXIT PATTERNS:
- Stop loss detected: {exit_p.get('stop_loss_detected', False)}
- Trailing stop detected: {exit_p.get('trailing_stop_detected', False)}
- Time-based exits: {exit_p.get('time_based_exits_pct', 0):.0%}

PERFORMANCE:
- Win rate: {patterns.get('win_rate', 0):.0%}
- Avg winner: +{patterns.get('avg_winner_pct', 0):.1f}%
- Avg loser: {patterns.get('avg_loser_pct', 0):.1f}%
- Profit factor: {patterns.get('profit_factor', 0):.2f}
- Trade frequency: {patterns.get('trade_frequency_per_month', 0):.1f} trades/month
- Total trades analyzed: {meta.get('total_trades', 0)}

RISK PROFILE:
- Avg position size: {risk.get('avg_position_pct', 0):.1f}% of portfolio
- Max position size: {risk.get('max_position_pct', 0):.1f}% of portfolio
- Position size consistency: {risk.get('position_size_consistency', 0):.0%}
- Conviction sizing detected: {risk.get('conviction_sizing_detected', False)}
- Sector concentration (HHI): {tc.get('hhi_index', 0):.3f}
- Risk assessment: {risk.get('risk_adjusted_assessment', 'N/A')}

STRESS RESPONSE:
- Drawdown behavior: {stress.get('drawdown_behavior', 'N/A')}
- Max drawdown: {stress.get('max_drawdown_pct', 0):.1f}%
- Avg recovery time: {stress.get('recovery_time_avg_days', 0):.1f} days
- Loss streak response: {stress.get('loss_streak_response', 'N/A')}
- Post-loss sizing change: {stress.get('post_loss_sizing_change', 0):+.2%}
- Revenge trading score: {stress.get('revenge_trading_score', 0)}/100

PORTFOLIO CONTEXT:
- Top sectors: {sector_str}
- Top tickers: {ticker_str}
- Unique tickers traded: {tc.get('unique_tickers', 0)}

ACTIVE VS PASSIVE:
- Active return: {active_passive.get('active_return_pct', 0):+.2f}%
- Passive benchmark return: {active_passive.get('passive_shadow_pct', 0):+.2f}%
- Alpha: {active_passive.get('alpha', 0):+.2f}%
- Information ratio: {active_passive.get('information_ratio', 'N/A')}"""

    # Add trait scores for context
    prompt += f"""

HEURISTIC TRAIT SCORES (0-100):
- Momentum: {traits.get('momentum_score', 0)}
- Value: {traits.get('value_score', 0)}
- Income: {traits.get('income_score', 0)}
- Swing: {traits.get('swing_score', 0)}
- Day Trading: {traits.get('day_trading_score', 0)}
- Event-Driven: {traits.get('event_driven_score', 0)}
- Mean Reversion: {traits.get('mean_reversion_score', 0)}
- Passive DCA: {traits.get('passive_dca_score', 0)}
- Risk Appetite: {traits.get('risk_appetite', 0)}
- Discipline: {traits.get('discipline', 0)}
- Conviction Consistency: {traits.get('conviction_consistency', 0)}
- Loss Aversion: {traits.get('loss_aversion', 0)}"""

    # Tax context
    tax_jur = context.get("tax_jurisdiction")
    if tax_jur:
        prompt += f"""

TAX CONTEXT:
- Jurisdiction: {tax_jur}
- Tax rate: {context.get('tax_rate', 0):.0%}
- Tax awareness score: {context.get('tax_awareness_score', 0)}/100
- LTCG optimization detected: {context.get('ltcg_optimization_detected', False)}
- Tax loss harvesting detected: {context.get('tax_loss_harvesting_detected', False)}"""

    # Regulatory context
    pdt = context.get("pdt_constrained", False)
    if pdt:
        prompt += f"""

REGULATORY CONTEXT:
- PDT constrained: {pdt}
- PDT impact score: {context.get('pdt_impact_score', 0)}/100
- Brokerage constraints: {context.get('brokerage_constraints_detected', [])}
- Notes: {context.get('regulatory_adjustment_notes', 'None')}"""

    return prompt
