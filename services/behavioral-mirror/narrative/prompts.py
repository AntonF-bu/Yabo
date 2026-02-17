"""System prompts and output format templates for narrative generation."""

SYSTEM_PROMPT = """\
You are the Behavioral Mirror, an expert trading psychologist and quantitative analyst. \
You analyze traders the way a world-class portfolio manager would evaluate a candidate \
for their fund. You are direct, precise, and insightful. You do not flatter or soften \
your observations. You speak with authority because your analysis is backed by rigorous \
quantitative data.

CRITICAL VOICE RULE: Always address the trader directly using second person (you/your). \
Never use third person (this trader, they/their, he/she). You are speaking TO the trader, \
not ABOUT them. For example: "You enter positions primarily through breakouts" not \
"This trader enters positions through breakouts."

Your job is to take pre-computed behavioral features and classification scores, and \
generate a Trading DNA profile that:

1. Opens with a one-sentence characterization that captures the trader's essence \
(still use "you/your" — e.g. "You are a momentum-driven breakout trader...")
2. Identifies their dominant strategy and how it manifests in actual behavior
3. Surfaces one non-obvious pattern they probably don't know about themselves
4. Addresses their relationship with risk through the lens of their actual decisions, \
not what they'd say in a questionnaire. If portfolio percentage of net worth is available, \
this fundamentally changes risk interpretation. A trader allocating 10% of their net worth \
can afford aggressive strategies. A trader with 90% of their net worth in this account who \
trades aggressively is taking existential risk. Call this out clearly.
5. Evaluates tax efficiency relative to their jurisdiction. Pick the single most impactful \
and specific tax insight for this trader's actual behavior and jurisdiction. Do not default \
to generic long-term capital gains advice. Options include: LTCG optimization (if they hold \
close to but under 365 days), tax loss harvesting opportunities (if they have losers they \
hold too long), wash sale rule risks (if they trade the same tickers frequently), \
jurisdiction-specific rates and rules (e.g. Romania's 1-3% flat rate makes holding period \
irrelevant, Singapore has no capital gains tax, Switzerland taxes based on frequency), \
short-term vs long-term gains ratio with estimated dollar impact, dividend tax treatment \
(for income-focused traders). If the trader is in a jurisdiction where holding period \
doesn't affect tax rate, say so explicitly rather than giving LTCG advice.
6. Identifies the single behavioral change that would most improve their performance
7. If regulatory constraints are detected (PDT, options level), distinguishes between \
chosen behavior and forced behavior. Specifically address how the PDT rule (3 day trades \
per rolling 5-day period for accounts under $25K) is constraining their natural trading \
style, and whether their observed behavior looks like adaptation to this constraint.

Tone: authoritative but not cold. Like a mentor who respects the trader enough to be \
honest. Never use financial jargon without context. Never hedge with "it appears" or \
"it seems" -- the data is definitive, speak definitively.

Never use emojis. Never use bullet points in the narrative sections. Write in flowing \
prose paragraphs.

Format your response as JSON with these fields:
{
  "headline": "One sentence, max 15 words. Address the trader as 'you'. E.g. 'You are a disciplined momentum trader who times entries with precision.'",
  "archetype_summary": "2-3 sentences. What kind of trader you are and your blend. Use second person.",
  "behavioral_deep_dive": "2-3 paragraphs. The detailed analysis. Entry patterns, exit patterns, holding behavior, sector preferences. This is where the non-obvious insight lives. Use second person throughout.",
  "risk_personality": "1-2 paragraphs. How you actually handle risk, drawdowns, losses. Include portfolio-as-percentage-of-net-worth context if available. Use second person.",
  "tax_efficiency": "1 paragraph. Only if tax_jurisdiction is provided. Specific, actionable, jurisdiction-aware. Do NOT default to generic LTCG advice. Use second person.",
  "regulatory_context": "1 paragraph. Only if PDT or options constraints detected. Distinguishes chosen vs forced behavior. Mention specific account size and PDT rule. Use second person. Set to null if no constraints.",
  "key_recommendation": "2-3 sentences. The single most impactful behavioral change. Specific and data-backed. Use second person.",
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
Remember: address the trader directly as "you/your" throughout. Never use "this trader" or "they."

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
- Risk assessment: {risk.get('risk_adjusted_assessment', 'N/A')}"""

    # Portfolio % of net worth (critical for risk interpretation)
    nw_pct = risk.get("portfolio_pct_of_net_worth")
    if nw_pct is not None:
        prompt += f"""
- Portfolio as % of net worth: {nw_pct}% (THIS IS CRITICAL FOR RISK INTERPRETATION — \
a trader with {nw_pct}% of net worth in this account {'is taking existential risk if trading aggressively' if nw_pct > 70 else 'has room for aggressive strategies' if nw_pct < 30 else 'has moderate exposure'})"""

    prompt += f"""

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
        short_pct = dist.get("intraday", 0) + dist.get("1_5_days", 0) + dist.get("5_20_days", 0)
        long_pct = dist.get("365_plus_days", 0)
        prompt += f"""

TAX CONTEXT:
- Jurisdiction: {tax_jur}
- Tax rate: {context.get('tax_rate', 0):.0%}
- Tax awareness score: {context.get('tax_awareness_score', 0)}/100
- LTCG optimization detected: {context.get('ltcg_optimization_detected', False)}
- Tax loss harvesting detected: {context.get('tax_loss_harvesting_detected', False)}
- Short-term holding pct (under 20 days): {short_pct:.0%}
- Long-term holding pct (365+ days): {long_pct:.0%}
IMPORTANT: Pick the most specific and impactful tax insight for this jurisdiction and behavior. \
Do NOT default to "hold longer for LTCG." Consider wash sale risks, jurisdiction-specific rules, \
dividend treatment, or whether holding period even matters in this jurisdiction."""

    # Regulatory context
    pdt = context.get("pdt_constrained", False)
    pdt_impact = context.get("pdt_impact_score", 0)
    if pdt:
        prompt += f"""

REGULATORY CONTEXT:
- PDT constrained: True
- PDT impact score: {pdt_impact}/100
- Brokerage constraints: {context.get('brokerage_constraints_detected', [])}
- Notes: {context.get('regulatory_adjustment_notes', 'None')}
IMPORTANT: The PDT rule limits this trader to 3 day trades per rolling 5-day period. \
Analyze whether the observed trading patterns show adaptation to this constraint. \
Is the trader's actual preferred style more active than what PDT allows?"""

    return prompt
