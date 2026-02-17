"""System prompts and output format templates for narrative generation."""

from __future__ import annotations

from typing import Any

# Confidence tier definitions
CONFIDENCE_TIERS = {
    "insufficient": {"min_trades": 0, "max_trades": 14, "label": "Insufficient Data"},
    "preliminary": {"min_trades": 15, "max_trades": 29, "label": "Preliminary"},
    "emerging": {"min_trades": 30, "max_trades": 74, "label": "Emerging"},
    "developing": {"min_trades": 75, "max_trades": 149, "label": "Developing"},
    "confident": {"min_trades": 150, "max_trades": 999999, "label": "Confident"},
}

# Tier-specific tone modifiers
_TIER_MODIFIERS = {
    "preliminary": """\
CONFIDENCE TIER: PRELIMINARY (15-29 trades)
The data set is small. Use hedging language throughout: "early patterns suggest," \
"with more data this may shift," "your initial tendency appears to be." \
Avoid definitive statements about strategy or archetype. Focus on what CAN be observed \
and explicitly note what CANNOT yet be determined. Shorten the behavioral_deep_dive to \
1 paragraph.""",

    "emerging": """\
CONFIDENCE TIER: EMERGING (30-74 trades)
Moderate data available. Use moderate hedging: "your data suggests," "based on the \
trades analyzed so far." You can identify patterns but note they may evolve with more \
data. Keep behavioral_deep_dive to 1-2 paragraphs.""",

    "developing": """\
CONFIDENCE TIER: DEVELOPING (75-149 trades)
Good data available. Use light hedging only for less certain observations. Most patterns \
are reliable at this sample size. You can speak with moderate authority.""",

    "confident": """\
CONFIDENCE TIER: CONFIDENT (150+ trades)
Strong data set. Speak definitively. The data IS definitive at this volume. Never hedge \
with "it appears" or "it seems." Your observations are backed by rigorous quantitative \
data.""",
}

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

CRITICAL ANTI-TEMPLATE RULE: Never cite raw metric scores in prose (e.g., "your revenge \
trading score of 40/100" or "your discipline score is 72"). Instead, describe the BEHAVIOR \
the score represents in unique language for each trader. Instead of "your revenge trading \
score of 40 indicates moderate emotional reactivity," say something like "after your worst \
losing week, you placed three trades in 48 hours at sizes 15% larger than your average, \
then went quiet for two weeks" (if the data supports this). Make every behavioral \
observation feel like it was discovered by watching THIS specific person trade, not read \
off a scorecard. Use the raw scores only to calibrate your interpretation, never as \
direct quotes in the narrative.

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
5. Evaluates tax efficiency relative to their jurisdiction using the JURISDICTION DATA \
provided (which includes specific rates, notes, and quirks). Reference jurisdiction-specific \
details rather than giving generic advice. A Swiss trader needs to hear about professional \
trader classification risk. A UK trader needs to hear about their CGT allowance. A \
Singapore trader needs to hear about the income classification risk from frequent trading.
6. Identifies the single behavioral change that would most improve their performance
7. If regulatory constraints are detected (PDT, options level), distinguishes between \
chosen behavior and forced behavior. Specifically address how the PDT rule (3 day trades \
per rolling 5-day period for accounts under $25K) is constraining their natural trading \
style, and whether their observed behavior looks like adaptation to this constraint.

KEY RECOMMENDATION RULE: The key_recommendation must contain exactly ONE behavioral \
change. Not two. Not "do X and also Y." Pick the single change with the highest expected \
impact on this trader's after-tax risk-adjusted returns. Be specific: include a number, a \
timeframe, or a concrete action. "Extend your average hold from 48 days to 120 days" is \
good. "Diversify and also extend your holds" is bad. If two changes are equally impactful, \
pick the one that is easier to implement because that is the one they will actually do.

TAX ADVICE REALISM RULE: If the trader's average holding period is under 30 days, do NOT \
recommend extending to 365+ days. That contradicts their core strategy and they will not \
do it. Instead focus on: wash sale awareness, loss harvesting, estimated tax payments, or \
simply acknowledge that their tax rate is the cost of their strategy and suggest they \
ensure their pre-tax alpha justifies it. Honest advice that respects their trading style \
is more valuable than theoretically correct advice they will ignore.

Tone: authoritative but not cold. Like a mentor who respects the trader enough to be \
honest. Never use financial jargon without context.

Never use emojis. Never use bullet points in the narrative sections. Write in flowing \
prose paragraphs.

Format your response as JSON with these fields:
{
  "headline": "One sentence, max 15 words. Address the trader as 'you'. E.g. 'You are a disciplined momentum trader who times entries with precision.'",
  "archetype_summary": "2-3 sentences. What kind of trader you are and your blend. Use second person.",
  "behavioral_deep_dive": "2-3 paragraphs. The detailed analysis. Entry patterns, exit patterns, holding behavior, sector preferences. This is where the non-obvious insight lives. Use second person throughout.",
  "risk_personality": "1-2 paragraphs. How you actually handle risk, drawdowns, losses. Include portfolio-as-percentage-of-net-worth context if available. Use second person.",
  "tax_efficiency": "1 paragraph. Only if tax_jurisdiction is provided. Specific, actionable, jurisdiction-aware. Reference the jurisdiction quirks provided. Do NOT default to generic LTCG advice. Use second person.",
  "regulatory_context": "1 paragraph. Only if PDT or options constraints detected. Distinguishes chosen vs forced behavior. Mention specific account size and PDT rule. Use second person. Set to null if no constraints.",
  "key_recommendation": "2-3 sentences. EXACTLY ONE specific behavioral change — not two bundled together. Data-backed with a number, timeframe, or concrete action. Use second person.",
  "confidence_note": "1 sentence. How confident the analysis is based on trade count and data quality."
}

Return ONLY the JSON object. No markdown fencing, no preamble, no explanation outside the JSON."""


def get_tier_system_prompt(confidence_tier: str) -> str:
    """Get the system prompt with tier-specific modifications.

    For 'confident' tier, the base prompt is used as-is (definitive language).
    For lower tiers, hedging instructions are prepended.
    """
    modifier = _TIER_MODIFIERS.get(confidence_tier)
    if modifier:
        return SYSTEM_PROMPT + "\n\n" + modifier
    return SYSTEM_PROMPT


def _load_jurisdiction_data(code: str) -> dict[str, Any] | None:
    """Load full jurisdiction data from centralized tax_jurisdictions.json."""
    try:
        from tax_data import get_jurisdiction
        return get_jurisdiction(code)
    except Exception:
        return None


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

    # Holdings profile (what the trader buys)
    hp = extracted_profile.get("holdings_profile", {})
    mcap_dist = hp.get("market_cap_distribution", {})
    vol_exp = hp.get("sector_volatility_exposure", {})

    if hp:
        prompt += f"""

HOLDINGS PROFILE (what you buy, not just how you trade):
- Weighted avg market cap category: {hp.get('weighted_avg_market_cap_category', 'unknown')}
- Market cap distribution: mega {mcap_dist.get('mega', 0):.0%}, large {mcap_dist.get('large', 0):.0%}, \
mid {mcap_dist.get('mid', 0):.0%}, small {mcap_dist.get('small', 0):.0%}, \
micro {mcap_dist.get('micro', 0):.0%}, unknown {mcap_dist.get('unknown', 0):.0%}
- Holdings risk score: {hp.get('holdings_risk_score', 50)}/100 (higher = riskier/more speculative)
- Sector volatility exposure: high {vol_exp.get('high', 0):.0%}, \
medium {vol_exp.get('medium', 0):.0%}, low {vol_exp.get('low', 0):.0%}
- Speculative holdings ratio: {hp.get('speculative_holdings_ratio', 0):.0%} (% in stocks < $2B market cap)
IMPORTANT: The holdings profile is a CRITICAL input. A trader holding IONQ, SOUN, INMB (speculative \
micro/small caps) for 100+ days is NOT a value investor — they are a growth conviction / momentum \
trader. Use the holdings risk score and speculative ratio to inform your archetype interpretation. \
If the holdings risk is high (>50) with long holds, this trader has growth conviction, not value \
discipline."""

    # Estimated portfolio value for sizing context
    est_pv = risk.get("estimated_portfolio_value")
    pv_source = risk.get("portfolio_value_source")
    if est_pv:
        prompt += f"""

PORTFOLIO VALUE ESTIMATE:
- Estimated portfolio value: ${est_pv:,.0f} (source: {pv_source})
- This affects position sizing interpretation: a $250 trade on a ${est_pv:,.0f} portfolio is \
{250/est_pv*100:.1f}%, not the same as on a $100K portfolio."""

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

    # Tax context — enriched with centralized jurisdiction data
    tax_jur = context.get("tax_jurisdiction")
    if tax_jur:
        short_pct = dist.get("intraday", 0) + dist.get("1_5_days", 0) + dist.get("5_20_days", 0)
        long_pct = dist.get("365_plus_days", 0)
        mean_hold = hold.get("mean_days", 0)

        # Load full jurisdiction data from centralized JSON
        jur_data = _load_jurisdiction_data(tax_jur)

        prompt += f"""

TAX CONTEXT:
- Jurisdiction: {tax_jur}
- Tax rate (combined long-term): {context.get('tax_rate', 0):.0%}
- Tax awareness score: {context.get('tax_awareness_score', 0)}/100
- LTCG optimization detected: {context.get('ltcg_optimization_detected', False)}
- Tax loss harvesting detected: {context.get('tax_loss_harvesting_detected', False)}
- Short-term holding pct (under 20 days): {short_pct:.0%}
- Long-term holding pct (365+ days): {long_pct:.0%}
- Mean holding period: {mean_hold:.1f} days"""

        if jur_data:
            prompt += f"""

JURISDICTION DATA (from centralized tax database):
- Label: {jur_data.get('label', tax_jur)}
- Country: {jur_data.get('country', 'unknown')}
- Combined short-term rate: {jur_data.get('combined_short_term', 0):.1%}
- Combined long-term rate: {jur_data.get('combined_long_term', 0):.1%}
- State income tax: {jur_data.get('state_income_tax') if jur_data.get('state_income_tax') is not None else 'N/A'}
- State capital gains tax: {jur_data.get('state_capital_gains_tax') if jur_data.get('state_capital_gains_tax') is not None else 'N/A'}
- Has state income tax: {jur_data.get('has_state_income_tax', 'N/A')}
- Notes: {jur_data.get('notes', 'None')}
- Quirks: {jur_data.get('quirks', 'None')}"""

        # Determine if this is a US jurisdiction
        is_us = jur_data.get("country") == "US" if jur_data else tax_jur in (
            "CA", "TX", "FL", "NY", "WA", "IL", "MA", "NJ", "NV", "TN",
            "WY", "CT", "PA", "OH", "CO", "GA", "NC", "VA", "AZ", "OR",
        )

        if is_us:
            prompt += f"""

US TAX ADVICE GUIDANCE — For US traders, analyze their SPECIFIC tax situation and pick \
the MOST NOVEL insight. Do NOT default to holding period extension advice unless it is \
genuinely the most impactful finding. Consider these alternatives IN ORDER OF PRIORITY:
1. Wash sale violations: if they sell and rebuy the same ticker within 30 days, this is \
likely costing them deductible losses. Flag it specifically with the tickers involved.
2. Tax loss harvesting timing: if they hold losers past year-end without harvesting, \
quantify the missed deduction.
3. Short-term vs long-term ratio: if >80% of gains are short-term, quantify the dollar \
difference at their specific state rate (combined ST rate: \
{jur_data.get('combined_short_term', 0.37):.1%} vs combined LT rate: \
{jur_data.get('combined_long_term', 0.20):.1%}).
4. Qualified dividend holding period: for income investors, are they holding dividend \
stocks long enough for qualified treatment (60 days around ex-date)?
5. Estimated tax payment risk: if they are generating significant short-term gains, they \
may owe quarterly estimated taxes and face underpayment penalties.
6. State-specific quirks: {jur_data.get('quirks', 'None') if jur_data else 'None'}
7. LTCG holding period extension: ONLY if the trader's average hold is between 200-364 \
days, making this a small behavioral tweak with large impact. If they hold {mean_hold:.0f} \
days on average{' — telling them to hold for a year is unrealistic advice' if mean_hold < 100 else ''}.
Pick ONE of these. The most specific and actionable one for THIS trader. Never give \
generic advice."""

        if mean_hold < 30:
            prompt += f"""

TAX REALISM CHECK: This trader's average holding period is {mean_hold:.1f} days. Do NOT \
recommend extending to 365+ days. That contradicts their core strategy and they will not \
do it. Instead focus on: wash sale awareness, loss harvesting, estimated tax payments, or \
acknowledge that their short-term tax rate is the cost of their strategy and suggest they \
ensure their pre-tax alpha justifies it."""

        prompt += """

IMPORTANT: Pick the most specific and impactful tax insight for this jurisdiction and \
behavior. Reference the jurisdiction quirks above if they are relevant to this trader's \
actual behavior. Do NOT default to "hold longer for LTCG" unless the data strongly \
supports it AND the trader's holding period makes it realistic."""

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
