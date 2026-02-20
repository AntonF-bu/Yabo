"""System prompts and user prompt builder for narrative generation.

This module builds structured Claude prompts from the 212-feature engine
output and 8-dimension classifier scores.  It replaces the legacy prompt
builder that consumed the old extractor's nested profile dict.
"""

from __future__ import annotations

from typing import Any

# ── Confidence tiers (unchanged) ────────────────────────────────────────────

CONFIDENCE_TIERS = {
    "insufficient": {"min_trades": 0, "max_trades": 14, "label": "Insufficient Data"},
    "preliminary": {"min_trades": 15, "max_trades": 29, "label": "Preliminary"},
    "emerging": {"min_trades": 30, "max_trades": 74, "label": "Emerging"},
    "developing": {"min_trades": 75, "max_trades": 149, "label": "Developing"},
    "confident": {"min_trades": 150, "max_trades": 999999, "label": "Confident"},
}

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

# ── System prompt ───────────────────────────────────────────────────────────

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
the score represents in unique language for each trader. Make every behavioral \
observation feel like it was discovered by watching THIS specific person trade, not read \
off a scorecard. Use the raw scores only to calibrate your interpretation, never as \
direct quotes in the narrative.

CRITICAL DATA SCOPE RULE: Always say "the analyzed portion of the portfolio" or \
"based on the trades uploaded" rather than "your total portfolio." We may not see every \
account or every trade. Never claim a position is "short" unless the data explicitly \
says strategy: "naked_short." When multi-leg options strategies are visible, identify \
them by name (covered call, calendar spread, protective put, etc.).

CRITICAL SPECIFICITY RULE: Reference specific dollar amounts, percentages, day counts, \
and ticker names from the data. Never write vague statements like "you tend to hold \
positions for a while" when the data says "your median hold is 47 days." Every claim \
must be backed by a number from the data package below.

PLAIN ENGLISH RULE: Write in plain English. Never use jargon like HHI, CV, or alpha \
without explaining what it means in context. Instead of "sector HHI of 0.42" write \
"your trading is heavily concentrated in a few sectors." Instead of "position sizing CV \
of 1.8" write "your trade sizes vary widely, ranging from small probes to large \
conviction bets."

You have access to a comprehensive 212-feature behavioral analysis engine spanning \
15 dimensions: Timing, Position Sizing, Holding Period, Entry Behavior, Exit Behavior, \
Win/Loss Psychology, Instrument Sophistication, Sector Behavior, Portfolio Construction, \
Market Awareness, Risk Management, Behavioral Biases, Social/Trend Sensitivity, \
Learning/Adaptation, and Unique Signature.

Your job is to generate a Trading DNA profile that:

1. Opens with a one-sentence characterization that captures the trader's essence \
(use "you/your")
2. Identifies their dominant strategy and how it manifests in actual behavior
3. Surfaces one non-obvious pattern they probably don't know about themselves
4. Addresses their relationship with risk through the lens of their actual decisions
5. Evaluates tax efficiency relative to their jurisdiction (if jurisdiction is provided)
6. Identifies the single behavioral change that would most improve their performance
7. If regulatory constraints are detected (PDT, options level), distinguishes between \
chosen behavior and forced behavior

KEY RECOMMENDATION RULE: The key_recommendation must contain exactly ONE behavioral \
change. Not two. Not "do X and also Y." Pick the single change with the highest expected \
impact on this trader's after-tax risk-adjusted returns. Be specific: include a number, a \
timeframe, or a concrete action.

TAX ADVICE REALISM RULE: If the trader's average holding period is under 30 days, do NOT \
recommend extending to 365+ days. That contradicts their core strategy. Instead focus on \
wash sale awareness, loss harvesting, or estimated tax payments.

CRITICAL COHERENCE RULE: Never open by stating a classification and then contradicting it. \
Lead with what the features reveal. The reader should never feel like the system is arguing \
with itself.

IMPORTANT TONE RULES:
- Never insult the trader's intelligence or experience.
- Never use words like "devastating," "toxic," "destruction," "reckless," "gambling," \
"disaster," "struggling," "poor," "failing," or "problematic."
- Present findings analytically, not judgmentally.
- Acknowledge when data limitations affect confidence in metrics.
- Frame recommendations as opportunities for improvement, not corrections of mistakes.
- Never assume the trader is unsophisticated.
- When multi-instrument usage is detected, the headline should reflect the full strategy.

Tone: authoritative but respectful. Like a mentor who takes the trader seriously enough \
to be honest, while acknowledging the limits of the data. Never use financial jargon \
without context.

Never use emojis. Never use bullet points in the narrative sections. Write in flowing \
prose paragraphs.

Format your response as JSON with these fields:
{
  "headline": "One sentence, max 15 words. Address the trader as 'you'.",
  "archetype_summary": "2-3 sentences. What kind of trader you are and your blend. Use second person.",
  "behavioral_deep_dive": "2-3 paragraphs. The detailed analysis. Entry patterns, exit patterns, holding behavior, sector preferences. Surface one non-obvious insight.",
  "risk_personality": "1-2 paragraphs. How you actually handle risk, drawdowns, losses.",
  "tax_efficiency": "1 paragraph. Only if tax_jurisdiction is provided. Jurisdiction-aware. Set to null if no jurisdiction.",
  "regulatory_context": "1 paragraph. Only if PDT or options constraints detected. Set to null if no constraints.",
  "key_recommendation": "2-3 sentences. EXACTLY ONE specific behavioral change. Data-backed.",
  "confidence_note": "1 sentence. How confident the analysis is based on trade count and data quality."
}

Return ONLY the JSON object. No markdown fencing, no preamble, no explanation outside the JSON."""


def get_tier_system_prompt(confidence_tier: str) -> str:
    """Get the system prompt with tier-specific modifications."""
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


# ── Helpers for safe feature extraction ─────────────────────────────────────

def _f(features: dict, key: str, default: float = 0.0) -> float:
    """Get a feature value safely, coercing None to *default*."""
    v = features.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _pct(features: dict, key: str, default: float = 0.0) -> str:
    """Format a feature as a percentage string."""
    return f"{_f(features, key, default):.0%}"


def _days(features: dict, key: str, default: float = 0.0) -> str:
    """Format a feature as a day count."""
    return f"{_f(features, key, default):.0f}"


def _flt(features: dict, key: str, default: float = 0.0, decimals: int = 1) -> str:
    """Format a feature as a float."""
    return f"{_f(features, key, default):.{decimals}f}"


def _pct_val(value: float | None) -> str:
    """Format a raw float as a percentage string, or 'N/A' if None."""
    if value is None:
        return "N/A"
    return f"{value:.0%}"


# ── User prompt builder ─────────────────────────────────────────────────────

def build_analysis_prompt(
    features: dict[str, Any],
    dimensions: dict[str, Any],
    classification_v2: dict[str, Any] | None = None,
    profile_meta: dict[str, Any] | None = None,
    holdings_features: dict[str, Any] | None = None,
) -> str:
    """Build the user prompt with curated feature subsets per section.

    Instead of dumping all 212 features, this selects the 10-20 most relevant
    features for each narrative section and presents them with context.

    Args:
        features: The 212-feature flat dict from extract_all_features().
        dimensions: The 8 dimension scores dict from classify_v2().
        classification_v2: Full classify_v2() output (archetype, summary, etc.).
        profile_meta: Optional dict with profile_id, tax_jurisdiction, etc.
        holdings_features: Optional dict of 69 h_ features from HoldingsExtractor.
    """
    meta = profile_meta or {}
    cv2 = classification_v2 or {}
    total_trades = _f(features, "portfolio_total_round_trips")

    prompt = (
        'Analyze the behavioral data below and generate a Trading DNA profile.\n'
        'Remember: address the trader directly as "you/your" throughout.\n'
    )

    # ── Data scope note ─────────────────────────────────────────────────
    prompt += f"""
DATA SCOPE:
- Total round trips analyzed: {total_trades:.0f}
- Date range of analyzed trades: {features.get('timing_date_range_days', 'unknown')} days
- This covers the analyzed portion of the portfolio, not necessarily every account or trade.
"""

    # ── Classification summary ──────────────────────────────────────────
    archetype = cv2.get("primary_archetype", "unknown")
    confidence = cv2.get("archetype_confidence", 0)
    summary = cv2.get("behavioral_summary", "")

    prompt += f"""
BEHAVIORAL CLASSIFICATION:
- Primary archetype: {archetype}
- Archetype confidence: {confidence:.0%}
- One-line summary: {summary}
"""

    # ── 8-Dimension profile ─────────────────────────────────────────────
    prompt += "\nDIMENSIONAL PROFILE (8 scored axes, each 0-100):\n"
    dim_labels = {
        "active_passive": ("ACTIVE vs PASSIVE", "0=passive, 100=hyperactive"),
        "momentum_value": ("MOMENTUM vs VALUE", "0=deep value, 100=pure momentum"),
        "concentrated_diversified": ("CONCENTRATED vs DIVERSIFIED", "0=diversified, 100=concentrated"),
        "disciplined_emotional": ("DISCIPLINED vs EMOTIONAL", "0=emotional, 100=disciplined"),
        "sophisticated_simple": ("SOPHISTICATED vs SIMPLE", "0=simple, 100=sophisticated"),
        "improving_declining": ("IMPROVING vs DECLINING", "0=declining, 100=improving"),
        "independent_herd": ("INDEPENDENT vs HERD", "0=herd, 100=independent"),
        "risk_seeking_averse": ("RISK SEEKING vs AVERSE", "0=averse, 100=risk-seeking"),
    }
    for key, (label, scale) in dim_labels.items():
        d = dimensions.get(key, {})
        score = d.get("score", 50)
        dlabel = d.get("label", "")
        evidence = d.get("evidence", [])
        ev_str = "; ".join(evidence) if evidence else "no evidence"
        prompt += f"- {label} ({scale}): {score:.0f}/100 ({dlabel}) — {ev_str}\n"

    # ── Section 1: Trading Activity & Timing ────────────────────────────
    prompt += f"""
TRADING ACTIVITY & TIMING:
- Trading days per month: {_flt(features, 'timing_trading_days_per_month')}
- Trades per active day: {_flt(features, 'timing_avg_trades_per_active_day')}
- Most active session: {features.get('timing_most_active_session', 'unknown')}
- Day-of-week pattern: Monday {_pct(features, 'timing_dow_monday')}, Friday {_pct(features, 'timing_dow_friday')}
- Monthly portfolio turnover: {_pct(features, 'portfolio_monthly_turnover')}
- December activity shift: {_flt(features, 'timing_december_shift')}x (>1.3 suggests tax-awareness)
"""

    # ── Section 2: Position Sizing ──────────────────────────────────────
    prompt += f"""
POSITION SIZING:
- Average position size: {_pct(features, 'sizing_avg_position_pct')} of portfolio
- Largest single trade: {_pct(features, 'sizing_max_single_trade_pct')} of portfolio
- Position size consistency (CV): {_flt(features, 'sizing_cv', 0.8, 2)} (lower = more consistent)
- Sizing after losses: {_flt(features, 'sizing_after_losses', 1.0)}x (>1.0 = sizing up after losses)
- Sizing after wins: {_flt(features, 'sizing_after_wins', 1.0)}x
"""

    # ── Section 3: Holding Period ───────────────────────────────────────
    prompt += f"""
HOLDING BEHAVIOR:
- Mean holding period: {_flt(features, 'holding_mean_days')} days
- Median holding period: {_flt(features, 'holding_median_days')} days
- Holding period consistency (CV): {_flt(features, 'holding_cv', 0.8, 2)}
- Day trades: {_pct(features, 'holding_pct_day_trades')} of positions
- Swing trades (2-20 days): {_pct(features, 'holding_pct_swing')} of positions
- Investment-length holds (>90 days): {_pct(features, 'holding_pct_investment')} of positions
- Winners held longer than losers: {_flt(features, 'holding_winner_vs_loser_ratio', 1.0, 2)}x ratio
"""

    # ── Section 4: Entry Patterns ───────────────────────────────────────
    prompt += f"""
ENTRY PATTERNS:
- Breakout entry score: {_pct(features, 'entry_breakout_score')} (entries on strength + volume)
- Dip-buyer score: {_pct(features, 'entry_dip_buyer_score')} (entries on pullbacks)
- Entries above moving average: {_pct(features, 'entry_above_ma_score')}
- Entry point in 52-week range: {_pct(features, 'entry_vs_52w_range')} (1.0 = buying at 52w highs)
- Entries on red (down) days: {_flt(features, 'entry_on_red_days')}
- Entries on green (up) days: {_flt(features, 'entry_on_green_days')}
"""

    # ── Section 5: Exit Patterns ────────────────────────────────────────
    prompt += f"""
EXIT PATTERNS:
- Partial exit ratio: {_pct(features, 'exit_partial_ratio')} (scaling out vs all-at-once)
- Take-profit discipline: {_pct(features, 'exit_take_profit_discipline')}
- Trailing stop usage score: {_pct(features, 'exit_trailing_stop_score')}
- Exit clustering: {_pct(features, 'exit_clustering')} (simultaneous exits across positions)
"""

    # ── Section 6: Performance ──────────────────────────────────────────
    prompt += f"""
PERFORMANCE (based on the analyzed portion):
- Win rate: {_pct(features, 'portfolio_win_rate')}
- Profit factor: {_flt(features, 'portfolio_profit_factor', 0, 2)}
- Avg winner: {_flt(features, 'portfolio_avg_winner_pct')}%
- Avg loser: {_flt(features, 'portfolio_avg_loser_pct')}%
- Best single trade: {_flt(features, 'portfolio_best_trade_pct')}%
- Worst single trade: {_flt(features, 'portfolio_worst_trade_pct')}%
"""

    # ── Section 7: Risk Management ──────────────────────────────────────
    prompt += f"""
RISK MANAGEMENT:
- Uses stop-losses: {_pct(features, 'risk_has_stops')} confidence
- Max single-trade loss: {_flt(features, 'risk_max_loss_pct')}%
- Hedge ratio: {_pct(features, 'risk_hedge_ratio')}
- Max drawdown: {_flt(features, 'risk_max_drawdown_pct')}%
"""

    # ── Section 8: Psychology & Discipline ──────────────────────────────
    prompt += f"""
PSYCHOLOGY & DISCIPLINE:
- Revenge trading score: {_pct(features, 'psych_revenge_score')} (trading impulsively after losses)
- Freeze response score: {_pct(features, 'psych_freeze_score')} (going inactive after losses)
- Emotional index: {_pct(features, 'psych_emotional_index')} (overall emotional reactivity)
- Escalation behavior: {_pct(features, 'psych_escalation')} (increasing risk when losing)
- Disposition effect: {_flt(features, 'bias_disposition', 1.0, 2)} (>1.5 = holding losers too long)
"""

    # ── Section 9: Instrument Sophistication ────────────────────────────
    opts_pct = _f(features, "instrument_options_pct")
    etf_pct = _f(features, "instrument_etf_pct")
    lev_pct = _f(features, "instrument_leveraged_etf")
    inv_pct = _f(features, "instrument_inverse_etf")

    prompt += f"""
INSTRUMENT USAGE:
- Options as % of trades: {opts_pct:.0%}
- ETF allocation: {etf_pct:.0%}
- Leveraged ETF usage: {lev_pct:.0%}
- Inverse ETF usage: {inv_pct:.0%}
- Complexity trend: {_flt(features, 'instrument_complexity_trend', 0, 2)} (positive = becoming more sophisticated)
"""

    # ── Section 10: Sector & Concentration ──────────────────────────────
    prompt += f"""
SECTOR & CONCENTRATION:
- Top 3 ticker concentration: {_pct(features, 'instrument_top3_concentration')} of all trades
- Unique tickers traded: {_days(features, 'instrument_unique_tickers')}
- Number of sectors: {_days(features, 'sector_count')}
- Sector concentration (higher = more concentrated): {_flt(features, 'sector_hhi', 0, 2)}
- Ticker churn rate: {_pct(features, 'sector_ticker_churn')} (replacing old tickers with new ones)
- Meme stock exposure: {_pct(features, 'sector_meme_exposure')}
- Core-vs-explore ratio: {_pct(features, 'sector_core_vs_explore')} (high = sticking to core positions)
"""

    # ── Section 11: Social & Independence ───────────────────────────────
    prompt += f"""
SOCIAL & INDEPENDENCE:
- Contrarian independence: {_pct(features, 'social_contrarian_independence')} (higher = more independent)
- Meme stock trading rate: {_pct(features, 'social_meme_rate')}
- Copycat score: {_pct(features, 'social_copycat')} (trading popular names right after trends)
- Herd following: {_flt(features, 'market_herd_score', 0, 2)} (positive = following the crowd)
- Bagholding score: {_pct(features, 'social_bagholding')} (holding losing meme stocks)
"""

    # ── Section 12: Learning & Adaptation ───────────────────────────────
    prompt += f"""
LEARNING & ADAPTATION:
- Skill trajectory: {_flt(features, 'learning_skill_trajectory', 0, 2)} (positive = improving over time)
- Win rate trend: {_flt(features, 'learning_win_rate_trend', 0, 2)} (positive = improving)
- Risk management trend: {_flt(features, 'learning_risk_trend', 0, 2)} (negative = taking less risk, improving)
- Mistake repetition: {_pct(features, 'learning_mistake_repetition')} (lower = learning from mistakes)
- Sizing improvement: {_flt(features, 'learning_sizing_improvement', 0, 2)}
"""

    # ── Section 13: Unique Signature ────────────────────────────────────
    sig_tag = features.get("sig_tag", "")
    sig_quirks = features.get("sig_quirks", [])
    if sig_tag or sig_quirks:
        prompt += f"""
UNIQUE SIGNATURE:
- Signature tag: {sig_tag}
- Notable quirks: {', '.join(sig_quirks) if isinstance(sig_quirks, list) else sig_quirks}
"""

    # ── Tax context (from profile metadata or features) ─────────────────
    tax_jur = meta.get("tax_jurisdiction")
    if tax_jur:
        jur_data = _load_jurisdiction_data(tax_jur)

        holding_mean = _f(features, "holding_mean_days")
        short_term_pct = _f(features, "holding_pct_day_trades") + _f(features, "holding_pct_swing")

        prompt += f"""
TAX CONTEXT:
- Jurisdiction: {tax_jur}
- Short-term holding percentage (under 20 days): {short_term_pct:.0%}
- Mean holding period: {holding_mean:.1f} days
- December activity shift: {_flt(features, 'timing_december_shift')}x
"""
        if jur_data:
            prompt += f"""
JURISDICTION DATA:
- Label: {jur_data.get('label', tax_jur)}
- Country: {jur_data.get('country', 'unknown')}
- Combined short-term rate: {jur_data.get('combined_short_term', 0):.1%}
- Combined long-term rate: {jur_data.get('combined_long_term', 0):.1%}
- Notes: {jur_data.get('notes', 'None')}
- Quirks: {jur_data.get('quirks', 'None')}
"""
            is_us = jur_data.get("country") == "US"
            if is_us:
                prompt += f"""
US TAX GUIDANCE: Pick the MOST NOVEL insight for this trader. Consider in priority order:
1. Wash sale violations (sell and rebuy same ticker within 30 days)
2. Tax loss harvesting timing (holding losers past year-end)
3. Short-term vs long-term ratio impact at their specific rate \
(ST: {jur_data.get('combined_short_term', 0.37):.1%}, LT: {jur_data.get('combined_long_term', 0.20):.1%})
4. Estimated tax payment risk from significant short-term gains
5. State-specific quirks: {jur_data.get('quirks', 'None')}
6. LTCG extension ONLY if average hold is 200-364 days
Pick ONE. The most specific and actionable for THIS trader."""

            if holding_mean < 30:
                prompt += f"""
TAX REALISM CHECK: Average hold is {holding_mean:.1f} days. Do NOT recommend extending \
to 365+ days. Focus on wash sale awareness, loss harvesting, or acknowledge that the \
short-term tax rate is the cost of their strategy."""

    # ── Regulatory context ──────────────────────────────────────────────
    pdt_constrained = meta.get("pdt_constrained", False)
    if pdt_constrained:
        prompt += """
REGULATORY CONTEXT:
- PDT constrained: True (account under $25,000)
- The PDT rule limits to 3 day trades per rolling 5-day period.
- Analyze whether observed patterns show adaptation to this constraint.
"""

    # ── Section 14: Holdings Portfolio Context (if available) ──────────
    if holdings_features:
        hf = holdings_features
        prompt += f"""
PORTFOLIO HOLDINGS CONTEXT (from holdings analysis — WHAT was built, not just HOW they trade):
- Total portfolio value: ${hf.get('h_total_value', 0):,.0f}
- Account count: {hf.get('h_account_count', 0)}
- Account type diversity: {hf.get('h_account_type_count', 0)} types (entropy: {hf.get('h_account_purpose_diversity', 'N/A')})
- Instrument type count: {hf.get('h_instrument_type_count', 0)}
- Covered call positions: {hf.get('h_covered_call_count', 0)}
- LEAPS positions: {hf.get('h_leaps_count', 0)}
- Overall sophistication score: {hf.get('h_overall_sophistication', 'N/A')}/100
- Equity allocation: {_pct_val(hf.get('h_equity_pct'))}
- Fixed income: {_pct_val(hf.get('h_fixed_income_pct'))}
- Options allocation: {_pct_val(hf.get('h_options_pct'))}
- Cash: {_pct_val(hf.get('h_cash_pct'))}
- Top position concentration: {_pct_val(hf.get('h_top1_pct'))}
- Ticker HHI: {hf.get('h_ticker_hhi', 'N/A')}
- Sector HHI: {hf.get('h_sector_hhi', 'N/A')}
- Annual yield: {_pct_val(hf.get('h_annual_yield'))}
- Fee drag: {_pct_val(hf.get('h_fee_drag_pct'))}
- Tax optimization score: {hf.get('h_tax_optimization_score', 'N/A')}/100
- Hedging score: {hf.get('h_hedging_score', 'N/A')}/1.0
- Cross-account overlap: {hf.get('h_cross_account_overlap_count', 0)} tickers
- Stress test (20% decline): ${hf.get('h_stress_test_20pct', 0):,.0f} estimated loss
"""

    # ── Instructions ────────────────────────────────────────────────────
    prompt += """
NARRATIVE INSTRUCTIONS:
- Use the DIMENSIONAL PROFILE as the primary framework for your narrative. Each \
dimension score tells you where this trader falls on a behavioral spectrum.
- Ground every claim in specific numbers from the data above. If you say they are \
"active," cite their trading days per month and trades per active day.
- Surface ONE non-obvious insight: a pattern the trader probably doesn't know about. \
Look at contradictions (e.g., high discipline score but high revenge trading), \
asymmetries (holding winners vs losers differently), or blind spots (meme exposure \
they may not realize).
- In risk_personality: describe what they ACTUALLY DO when losing, not what a \
textbook says about risk. Use the revenge score, freeze score, sizing-after-losses, \
and disposition effect to paint a behavioral picture.
- In key_recommendation: ONE change. Be specific with a number, timeframe, or action.
- Do NOT reference score numbers directly in prose. Describe the behavior instead.
"""

    return prompt
