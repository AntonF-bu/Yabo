"""V2 Behavioral Classification Engine.

Takes the 212-feature dict from extract_all_features() and produces a
multi-dimensional behavioral profile with 8 scored dimensions (0-100).
Runs alongside the old GMM/heuristic classifier for comparison.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _safe(features: dict, key: str, default: float = 0.0) -> float:
    """Get a feature value, coercing None / missing to *default*."""
    v = features.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _linear(value: float, low: float, high: float) -> float:
    """Map *value* linearly from [low, high] -> [0, 100], clamped."""
    if high == low:
        return 50.0
    return _clamp((value - low) / (high - low) * 100)


def _inv_linear(value: float, low: float, high: float) -> float:
    """Inverse linear: low value -> 100, high value -> 0."""
    return 100.0 - _linear(value, low, high)


def _label_from_scale(score: float, labels: list[tuple[int, str]]) -> str:
    """Pick a label from a list of (upper_bound, label) pairs."""
    for bound, label in labels:
        if score <= bound:
            return label
    return labels[-1][1]


# ── Dimension scorers ────────────────────────────────────────────────────────


def _score_active_passive(f: dict) -> dict:
    """0 = fully passive, 100 = hyperactive."""
    components: list[tuple[float, float]] = []
    evidence: list[str] = []

    # trading_days_per_month (weight 20%)
    days = _safe(f, "timing_trading_days_per_month")
    s = _linear(days, 3, 18)
    components.append((s, 0.20))
    if days > 15:
        evidence.append(f"Trades {days:.0f} days per month")
    elif days < 5:
        evidence.append(f"Only active {days:.0f} days per month")

    # avg_trades_per_active_day (weight 10%)
    tpad = _safe(f, "timing_avg_trades_per_active_day")
    components.append((_linear(tpad, 1, 5), 0.10))
    if tpad > 3:
        evidence.append(f"{tpad:.1f} trades per active day")

    # holding_pct_investment (weight 15%) — high = passive lean
    inv_pct = _safe(f, "holding_pct_investment")
    components.append((_inv_linear(inv_pct, 0, 0.9), 0.15))
    if inv_pct > 0.7:
        evidence.append(f"{inv_pct:.0%} of positions are investment-length holds")

    # day + swing pct (weight 15%)
    day_swing = _safe(f, "holding_pct_day_trades") + _safe(f, "holding_pct_swing")
    components.append((_linear(day_swing, 0, 0.7), 0.15))
    if day_swing > 0.5:
        evidence.append(f"{day_swing:.0%} of trades are day or swing trades")

    # monthly_turnover (weight 15%)
    turnover = _safe(f, "portfolio_monthly_turnover")
    components.append((_linear(turnover, 0.05, 0.8), 0.15))

    # exit_partial_ratio (weight 10%)
    partial = _safe(f, "exit_partial_ratio")
    components.append((_linear(partial, 0, 0.7), 0.10))
    if partial > 0.5:
        evidence.append(f"{partial:.0%} partial-exit ratio indicates active management")

    # sector_ticker_churn (weight 10%)
    churn = _safe(f, "sector_ticker_churn")
    components.append((_linear(churn, 0, 0.8), 0.10))

    # instrument_etf_pct (weight 5%) — high = passive lean
    etf = _safe(f, "instrument_etf_pct")
    components.append((_inv_linear(etf, 0, 0.8), 0.05))

    score = _clamp(sum(s * w for s, w in components))

    labels = [(20, "Passive Holder"), (40, "Mostly Passive"),
              (60, "Balanced"), (80, "Active Trader"), (100, "Hyperactive")]

    evidence = [
        f"Trades {days:.0f} days per month averaging {tpad:.1f} trades per active day",
        f"{turnover:.0%} monthly portfolio turnover",
    ]
    if day_swing > 0.3:
        evidence.append(f"{day_swing:.0%} of trades are day or swing trades")
    elif inv_pct > 0.5:
        evidence.append(f"{inv_pct:.0%} of positions are investment-length holds")
    else:
        evidence.append(f"{partial:.0%} partial-exit ratio")

    return {
        "score": round(score, 1),
        "label": _label_from_scale(score, labels),
        "evidence": evidence[:3],
    }


def _score_momentum_value(f: dict) -> dict:
    """0 = deep value, 100 = pure momentum."""
    components: list[tuple[float, float]] = []
    evidence: list[str] = []

    # entry_breakout_score (weight 20%)
    breakout = _safe(f, "entry_breakout_score")
    components.append((_linear(breakout, 0, 0.7), 0.20))
    if breakout > 0.5:
        evidence.append(f"{breakout:.0%} breakout entry score")

    # entry_above_ma_score (weight 15%)
    above_ma = _safe(f, "entry_above_ma_score")
    components.append((_linear(above_ma, 0.3, 0.9), 0.15))
    if above_ma > 0.7:
        evidence.append(f"{above_ma:.0%} of entries above moving average")

    # entry_dip_buyer_score (weight 20%) — high = value (inverted)
    dip = _safe(f, "entry_dip_buyer_score")
    components.append((_inv_linear(dip, 0, 0.6), 0.20))
    if dip > 0.3:
        evidence.append(f"{dip:.0%} dip-buyer score (value signal)")

    # entry_vs_52w_range (weight 15%)
    vs52 = _safe(f, "entry_vs_52w_range", 0.5)
    components.append((_linear(vs52, 0.2, 0.8), 0.15))

    # red vs green day entries (weight 10%)
    red = _safe(f, "entry_on_red_days")
    green = _safe(f, "entry_on_green_days")
    if red + green > 0:
        red_ratio = red / (red + green)
        components.append((_inv_linear(red_ratio, 0.3, 0.7), 0.10))
        if red_ratio > 0.55:
            evidence.append(f"{red_ratio:.0%} of entries on red days (contrarian)")
    else:
        components.append((50.0, 0.10))

    # market_contrarian_score (weight 10%) — positive = value lean
    contrarian = _safe(f, "market_contrarian_score")
    components.append((_inv_linear(contrarian, -0.5, 0.5), 0.10))

    # holding_median_days (weight 10%) — long holds = value lean
    median_days = _safe(f, "holding_median_days")
    components.append((_inv_linear(median_days, 5, 120), 0.10))

    score = _clamp(sum(s * w for s, w in components))

    labels = [(20, "Deep Value"), (40, "Value Leaning"),
              (60, "Blend"), (80, "Momentum Leaning"), (100, "Pure Momentum")]

    evidence = [
        f"{breakout:.0%} breakout entry score with {above_ma:.0%} of entries above moving average",
        f"{dip:.0%} dip-buyer score, entries at {vs52:.0%} of 52-week range",
        f"Median holding period of {median_days:.0f} days",
    ]

    return {
        "score": round(score, 1),
        "label": _label_from_scale(score, labels),
        "evidence": evidence[:3],
    }


def _score_concentrated_diversified(f: dict) -> dict:
    """0 = fully diversified, 100 = ultra concentrated."""
    components: list[tuple[float, float]] = []
    evidence: list[str] = []

    # instrument_top3_concentration (weight 20%)
    top3 = _safe(f, "instrument_top3_concentration")
    components.append((_linear(top3, 0.2, 0.8), 0.20))
    if top3 > 0.6:
        evidence.append(f"Top 3 tickers are {top3:.0%} of portfolio")

    # sector_hhi (weight 20%)
    hhi = _safe(f, "sector_hhi")
    components.append((_linear(hhi, 0.1, 0.5), 0.20))
    if hhi > 0.3:
        evidence.append(f"Sector HHI of {hhi:.2f} (concentrated)")

    # portfolio_diversification (weight 15%) — inverted: low diversification = concentrated
    div_score = _safe(f, "portfolio_diversification", 0.5)
    components.append((_inv_linear(div_score, 0.2, 0.9), 0.15))

    # instrument_unique_tickers (weight 15%)
    tickers = _safe(f, "instrument_unique_tickers", 10)
    components.append((_inv_linear(tickers, 3, 25), 0.15))
    if tickers < 5:
        evidence.append(f"Only {tickers:.0f} unique tickers traded")
    elif tickers > 20:
        evidence.append(f"{tickers:.0f} unique tickers traded (diversified)")

    # sizing_max_single_trade_pct (weight 15%)
    max_pct = _safe(f, "sizing_max_single_trade_pct")
    components.append((_linear(max_pct, 0.05, 0.35), 0.15))
    if max_pct > 0.2:
        evidence.append(f"Max single trade of {max_pct:.0%} of portfolio")

    # sector_count (weight 10%)
    sec_count = _safe(f, "sector_count", 5)
    components.append((_inv_linear(sec_count, 2, 8), 0.10))

    # sector_core_vs_explore (weight 5%)
    core = _safe(f, "sector_core_vs_explore", 0.5)
    components.append((_linear(core, 0.3, 0.9), 0.05))

    score = _clamp(sum(s * w for s, w in components))

    labels = [(20, "Broadly Diversified"), (40, "Moderately Diversified"),
              (60, "Balanced"), (80, "Concentrated"), (100, "Ultra Concentrated")]

    evidence = [
        f"Top 3 tickers are {top3:.0%} of portfolio",
        f"Sector HHI of {hhi:.2f} across {sec_count:.0f} sectors",
        f"{tickers:.0f} unique tickers with largest single trade at {max_pct:.0%}",
    ]

    return {
        "score": round(score, 1),
        "label": _label_from_scale(score, labels),
        "evidence": evidence[:3],
    }


def _score_disciplined_emotional(f: dict) -> dict:
    """0 = fully emotional, 100 = highly disciplined."""
    components: list[tuple[float, float]] = []
    evidence: list[str] = []

    # psych_revenge_score (weight 15%) — high = emotional (inverted)
    revenge = _safe(f, "psych_revenge_score")
    components.append((_inv_linear(revenge, 0, 0.6), 0.15))
    if revenge > 0.3:
        evidence.append(f"Revenge trading score of {revenge:.0%} (emotional signal)")

    # psych_freeze_score (weight 10%) — high = emotional
    freeze = _safe(f, "psych_freeze_score")
    components.append((_inv_linear(freeze, 0, 0.5), 0.10))

    # sizing_cv (weight 15%) — high CV = emotional
    sizing_cv = _safe(f, "sizing_cv", 0.8)
    components.append((_inv_linear(sizing_cv, 0.3, 2.0), 0.15))
    if sizing_cv < 0.5:
        evidence.append(f"Position sizing CV of {sizing_cv:.2f} (very consistent)")
    elif sizing_cv > 1.5:
        evidence.append(f"Position sizing CV of {sizing_cv:.2f} (erratic sizing)")

    # holding_cv (weight 10%) — high CV = emotional
    hold_cv = _safe(f, "holding_cv", 0.8)
    components.append((_inv_linear(hold_cv, 0.3, 2.0), 0.10))

    # psych_emotional_index (weight 15%) — high = emotional
    emo_idx = _safe(f, "psych_emotional_index")
    components.append((_inv_linear(emo_idx, 0, 0.6), 0.15))
    if emo_idx > 0.3:
        evidence.append(f"Emotional index of {emo_idx:.0%}")

    # exit_take_profit_discipline (weight 10%)
    tp = _safe(f, "exit_take_profit_discipline")
    components.append((_linear(tp, 0, 0.8), 0.10))
    if tp > 0.5:
        evidence.append(f"Take-profit discipline score of {tp:.0%}")

    # risk_has_stops (weight 10%)
    stops = _safe(f, "risk_has_stops")
    components.append((100.0 if stops > 0.5 else 0.0, 0.10))
    if stops > 0.5:
        evidence.append("Uses stop-losses consistently")

    # learning_mistake_repetition (weight 10%) — high = emotional
    mistakes = _safe(f, "learning_mistake_repetition")
    components.append((_inv_linear(mistakes, 0, 0.5), 0.10))

    # bias_disposition (weight 5%)
    disp = _safe(f, "bias_disposition", 1.0)
    if disp > 1.5:
        components.append((20.0, 0.05))
    elif disp < 0.8:
        components.append((80.0, 0.05))
    else:
        components.append((50.0, 0.05))

    score = _clamp(sum(s * w for s, w in components))

    labels = [(20, "Highly Emotional"), (40, "Impulsive"),
              (60, "Mixed Discipline"), (80, "Disciplined"), (100, "Systematic")]

    evidence = [
        f"Position sizing CV of {sizing_cv:.2f}",
        f"Revenge trading score of {revenge:.0%} with {mistakes:.0%} mistake repetition",
    ]
    if stops > 0.5:
        evidence.append("Uses stop-losses consistently")
    else:
        evidence.append(f"Emotional index at {emo_idx:.0%}")

    return {
        "score": round(score, 1),
        "label": _label_from_scale(score, labels),
        "evidence": evidence[:3],
    }


def _score_sophisticated_simple(f: dict) -> dict:
    """0 = very simple, 100 = highly sophisticated."""
    components: list[tuple[float, float]] = []
    evidence: list[str] = []

    # h_overall_sophistication from holdings analysis (weight 25%)
    # This is a 0-100 score from the holdings extractor measuring
    # portfolio structure sophistication (options, structured products,
    # multi-account, income engineering, etc.)
    h_soph = _safe(f, "h_overall_sophistication")
    if h_soph > 0:
        components.append((h_soph, 0.25))
        evidence.append(f"Holdings sophistication score {h_soph:.0f}/100")
        # Scale trade-based weights to 75% when holdings data is available
        tw = 0.75
    else:
        # No holdings data — trade features get full weight
        tw = 1.0

    # instrument_options_pct (weight 20% * tw)
    opts = _safe(f, "instrument_options_pct")
    components.append((_linear(opts, 0, 0.3), 0.20 * tw))
    if opts > 0.1:
        evidence.append(f"{opts:.0%} options usage")

    # instrument_etf_pct as core allocation (weight 10% * tw)
    etf = _safe(f, "instrument_etf_pct")
    components.append((_linear(etf, 0, 0.5) * 0.5, 0.10 * tw))  # moderate boost

    # leveraged / inverse ETFs (weight 10% * tw)
    lev = _safe(f, "instrument_leveraged_etf")
    inv = _safe(f, "instrument_inverse_etf")
    lev_score = 100.0 if (lev > 0 or inv > 0) else 0.0
    components.append((lev_score, 0.10 * tw))
    if lev > 0 or inv > 0:
        evidence.append("Uses leveraged or inverse ETFs")

    # risk_hedge_ratio (weight 15% * tw)
    hedge = _safe(f, "risk_hedge_ratio")
    components.append((_linear(hedge, 0, 0.3), 0.15 * tw))
    if hedge > 0:
        evidence.append(f"Hedge ratio of {hedge:.0%}")

    # sector_count (weight 10% * tw)
    sec = _safe(f, "sector_count", 3)
    components.append((_linear(sec, 2, 8), 0.10 * tw))

    # instrument_complexity_trend (weight 10% * tw)
    trend = _safe(f, "instrument_complexity_trend")
    components.append((_linear(trend, -0.5, 0.5), 0.10 * tw))

    # exit_trailing_stop_score (weight 10% * tw)
    trail = _safe(f, "exit_trailing_stop_score")
    components.append((_linear(trail, 0, 0.5), 0.10 * tw))
    if trail > 0.2:
        evidence.append(f"Trailing stop usage score of {trail:.0%}")

    # timing_december_shift (weight 10% * tw) — tax-aware = sophisticated
    dec = _safe(f, "timing_december_shift", 1.0)
    components.append((_linear(dec, 0.8, 2.0), 0.10 * tw))
    if dec > 1.3:
        evidence.append(f"December activity shift of {dec:.1f}x (tax aware)")

    # portfolio_income_component (weight 5% * tw)
    income = _safe(f, "portfolio_income_component")
    components.append((_linear(income, 0, 1), 0.05 * tw))

    score = _clamp(sum(s * w for s, w in components))

    labels = [(20, "Beginner"), (40, "Basic"), (60, "Intermediate"),
              (80, "Advanced"), (100, "Sophisticated")]

    evidence = [
        f"{opts:.0%} options usage across {sec:.0f} sectors",
    ]
    if hedge > 0:
        evidence.append(f"Hedge ratio of {hedge:.0%}")
    elif lev > 0 or inv > 0:
        evidence.append("Uses leveraged or inverse ETFs")
    else:
        evidence.append(f"Trailing stop score of {trail:.0%}")
    if dec > 1.1:
        evidence.append(f"December activity shift of {dec:.1f}x suggesting tax awareness")
    elif income > 0:
        evidence.append("Income-generating component in portfolio")
    else:
        evidence.append(f"Instrument complexity trend of {trend:+.2f}")

    return {
        "score": round(score, 1),
        "label": _label_from_scale(score, labels),
        "evidence": evidence[:3],
    }


def _score_improving_declining(f: dict) -> dict:
    """0 = declining, 50 = flat, 100 = rapidly improving."""
    components: list[tuple[float, float]] = []
    evidence: list[str] = []

    # learning_skill_trajectory (weight 30%) — primary signal
    traj = _safe(f, "learning_skill_trajectory")
    components.append((_linear(traj, -1.0, 1.0), 0.30))
    if traj > 0.3:
        evidence.append(f"Skill trajectory of {traj:+.2f} (improving)")
    elif traj < -0.3:
        evidence.append(f"Skill trajectory of {traj:+.2f} (declining)")

    # learning_win_rate_trend (weight 20%)
    wr_trend = _safe(f, "learning_win_rate_trend")
    components.append((_linear(wr_trend, -0.5, 0.5), 0.20))
    if wr_trend > 0.1:
        evidence.append(f"Win rate trending up ({wr_trend:+.2f})")
    elif wr_trend < -0.1:
        evidence.append(f"Win rate trending down ({wr_trend:+.2f})")

    # learning_risk_trend (weight 15%) — negative = improving (taking less risk)
    risk_trend = _safe(f, "learning_risk_trend")
    components.append((_inv_linear(risk_trend, -0.5, 0.5), 0.15))

    # learning_hold_optimization (weight 10%) — negative = improving
    hold_opt = _safe(f, "learning_hold_optimization")
    components.append((_inv_linear(hold_opt, -0.5, 0.5), 0.10))

    # learning_mistake_repetition (weight 15%) — low = improving
    mistakes = _safe(f, "learning_mistake_repetition")
    components.append((_inv_linear(mistakes, 0, 0.5), 0.15))
    if mistakes < 0.15:
        evidence.append("Low mistake repetition rate")
    elif mistakes > 0.3:
        evidence.append(f"Repeats {mistakes:.0%} of past mistakes")

    # learning_sizing_improvement (weight 10%) — negative = improving
    sizing_imp = _safe(f, "learning_sizing_improvement")
    components.append((_inv_linear(sizing_imp, -0.5, 0.5), 0.10))

    score = _clamp(sum(s * w for s, w in components))

    labels = [(20, "Declining"), (40, "Slight Decline"), (60, "Stable"),
              (80, "Improving"), (100, "Rapidly Improving")]

    evidence = [
        f"Skill trajectory of {traj:+.2f}",
        f"Win rate trend of {wr_trend:+.2f}",
        f"Mistake repetition rate of {mistakes:.0%}",
    ]

    return {
        "score": round(score, 1),
        "label": _label_from_scale(score, labels),
        "evidence": evidence[:3],
    }


def _score_independent_herd(f: dict) -> dict:
    """0 = pure herd follower, 100 = fully independent."""
    components: list[tuple[float, float]] = []
    evidence: list[str] = []

    # social_contrarian_independence (weight 25%)
    indep = _safe(f, "social_contrarian_independence", 0.5)
    components.append((_linear(indep, 0, 1.0), 0.25))
    if indep > 0.7:
        evidence.append(f"Independence score of {indep:.0%}")

    # social_meme_rate (weight 20%) — high = herd
    meme = _safe(f, "social_meme_rate")
    components.append((_inv_linear(meme, 0, 0.5), 0.20))
    if meme > 0.2:
        evidence.append(f"{meme:.0%} of trades in meme stocks")

    # social_copycat (weight 15%) — high = herd
    copycat = _safe(f, "social_copycat")
    components.append((_inv_linear(copycat, 0, 0.6), 0.15))

    # market_herd_score (weight 15%) — positive = herd
    herd = _safe(f, "market_herd_score")
    components.append((_inv_linear(herd, -0.5, 0.5), 0.15))

    # social_bagholding (weight 10%) — high = herd
    bag = _safe(f, "social_bagholding")
    components.append((_inv_linear(bag, 0, 0.5), 0.10))
    if bag > 0.3:
        evidence.append(f"Bagholding score of {bag:.0%}")

    # bias_availability (weight 10%) — high = herd lean
    avail = _safe(f, "bias_availability")
    components.append((_inv_linear(avail, 0, 0.8), 0.10))

    # social_influence_trend (weight 5%) — positive = becoming more herd
    infl = _safe(f, "social_influence_trend")
    components.append((_inv_linear(infl, -0.5, 0.5), 0.05))

    score = _clamp(sum(s * w for s, w in components))

    labels = [(20, "Herd Follower"), (40, "Trend Influenced"),
              (60, "Selective"), (80, "Mostly Independent"),
              (100, "Fully Independent")]

    evidence = [
        f"{meme:.0%} of trades in meme stocks",
        f"Independence score of {indep:.0%} with copycat score of {copycat:.0%}",
        f"Bagholding rate of {bag:.0%}",
    ]

    return {
        "score": round(score, 1),
        "label": _label_from_scale(score, labels),
        "evidence": evidence[:3],
    }


def _score_risk_seeking_averse(f: dict) -> dict:
    """0 = very risk averse, 100 = very risk seeking."""
    components: list[tuple[float, float]] = []
    evidence: list[str] = []

    # sizing_max_single_trade_pct (weight 15%)
    max_pct = _safe(f, "sizing_max_single_trade_pct")
    components.append((_linear(max_pct, 0.05, 0.35), 0.15))
    if max_pct > 0.2:
        evidence.append(f"Max single trade of {max_pct:.0%} of portfolio")

    # sizing_avg_position_pct (weight 15%)
    avg_pct = _safe(f, "sizing_avg_position_pct")
    components.append((_linear(avg_pct, 0.02, 0.2), 0.15))

    # risk_has_stops (weight 10%) — no stops = risk seeking
    stops = _safe(f, "risk_has_stops")
    components.append((0.0 if stops > 0.5 else 100.0, 0.10))
    if stops < 0.5:
        evidence.append("No consistent stop-loss usage")

    # risk_max_loss_pct (weight 10%) — magnitude (value is already in %, e.g. -26.22)
    max_loss = abs(_safe(f, "risk_max_loss_pct"))
    components.append((_linear(max_loss, 5, 50), 0.10))
    if max_loss > 20:
        evidence.append(f"Max single-trade loss of {max_loss:.1f}%")

    # instrument_leveraged_etf (weight 10%)
    lev = _safe(f, "instrument_leveraged_etf")
    components.append((100.0 if lev > 0 else 0.0, 0.10))
    if lev > 0:
        evidence.append("Uses leveraged ETFs")

    # sizing_after_losses (weight 10%) — >1.2 = risk seeking (sizing up after losses)
    after_loss = _safe(f, "sizing_after_losses", 1.0)
    components.append((_linear(after_loss, 0.7, 1.5), 0.10))
    if after_loss > 1.2:
        evidence.append(f"Sizes up {after_loss:.1f}x after losses")

    # sector_meme_exposure (weight 10%)
    meme_exp = _safe(f, "sector_meme_exposure")
    components.append((_linear(meme_exp, 0, 0.3), 0.10))

    # portfolio_long_only + no hedging (weight 10%)
    long_only = _safe(f, "portfolio_long_only")
    hedge = _safe(f, "risk_hedge_ratio")
    if long_only > 0.5 and hedge < 0.01:
        components.append((70.0, 0.10))
    else:
        components.append((30.0, 0.10))

    # holding_pct_day_trades (weight 5%)
    day_pct = _safe(f, "holding_pct_day_trades")
    components.append((_linear(day_pct, 0, 0.4), 0.05))

    # psych_escalation (weight 5%)
    esc = _safe(f, "psych_escalation")
    components.append((_linear(esc, 0, 0.5), 0.05))

    score = _clamp(sum(s * w for s, w in components))

    labels = [(20, "Very Conservative"), (40, "Risk Averse"),
              (60, "Moderate Risk"), (80, "Risk Tolerant"),
              (100, "High Risk Seeker")]

    evidence = [
        f"Largest single trade at {max_pct:.0%} with {avg_pct:.0%} average trade size",
    ]
    if stops < 0.5:
        evidence.append("No consistent stop-loss usage")
    else:
        evidence.append("Uses stop-losses consistently")
    if max_loss > 20:
        evidence.append(f"Max single-trade loss of {max_loss:.1f}%")
    elif after_loss > 1.1:
        evidence.append(f"Sizes up {after_loss:.1f}x after losses")
    else:
        evidence.append(f"{meme_exp:.0%} meme stock exposure")

    return {
        "score": round(score, 1),
        "label": _label_from_scale(score, labels),
        "evidence": evidence[:3],
    }


# ── Config-driven classification (Supabase registries) ────────────────────

# Module-level cache for Supabase config.  Populated once by
# load_classifier_config(); survives until process restart.
_cached_config: dict[str, Any] | None = None

# Features that need abs() applied before normalization.
_ABS_FEATURES: set[str] = {"risk_max_loss_pct"}

# Direction per (dimension, feature): +1 = high value pushes dimension score
# UP, -1 = high value pushes it DOWN.  Hardcoded for now; will migrate to a
# Supabase column later.
_DIRECTION_MAP: dict[tuple[str, str], int] = {
    # ── active_passive (0 = passive … 100 = hyperactive) ──
    ("active_passive", "timing_trading_days_per_month"): 1,
    ("active_passive", "timing_avg_trades_per_active_day"): 1,
    ("active_passive", "holding_pct_investment"): -1,
    ("active_passive", "holding_pct_day_trades"): 1,
    ("active_passive", "holding_pct_swing"): 1,
    ("active_passive", "portfolio_monthly_turnover"): 1,
    ("active_passive", "exit_partial_ratio"): 1,
    ("active_passive", "sector_ticker_churn"): 1,
    ("active_passive", "instrument_etf_pct"): -1,
    # ── momentum_value (0 = value … 100 = momentum) ──
    ("momentum_value", "entry_breakout_score"): 1,
    ("momentum_value", "entry_above_ma_score"): 1,
    ("momentum_value", "entry_dip_buyer_score"): -1,
    ("momentum_value", "entry_vs_52w_range"): 1,
    ("momentum_value", "entry_on_red_days"): -1,
    ("momentum_value", "entry_on_green_days"): 1,
    ("momentum_value", "market_contrarian_score"): -1,
    ("momentum_value", "holding_median_days"): -1,
    # ── concentrated_diversified (0 = diversified … 100 = concentrated) ──
    ("concentrated_diversified", "instrument_top3_concentration"): 1,
    ("concentrated_diversified", "sector_hhi"): 1,
    ("concentrated_diversified", "portfolio_diversification"): -1,
    ("concentrated_diversified", "instrument_unique_tickers"): -1,
    ("concentrated_diversified", "sizing_max_single_trade_pct"): 1,
    ("concentrated_diversified", "sector_count"): -1,
    ("concentrated_diversified", "sector_core_vs_explore"): 1,
    # ── disciplined_emotional (0 = emotional … 100 = disciplined) ──
    ("disciplined_emotional", "psych_revenge_score"): -1,
    ("disciplined_emotional", "psych_freeze_score"): -1,
    ("disciplined_emotional", "sizing_cv"): -1,
    ("disciplined_emotional", "holding_cv"): -1,
    ("disciplined_emotional", "psych_emotional_index"): -1,
    ("disciplined_emotional", "exit_take_profit_discipline"): 1,
    ("disciplined_emotional", "risk_has_stops"): 1,
    ("disciplined_emotional", "learning_mistake_repetition"): -1,
    ("disciplined_emotional", "bias_disposition"): -1,
    # ── sophisticated_simple (0 = simple … 100 = sophisticated) ──
    ("sophisticated_simple", "h_overall_sophistication"): 1,
    ("sophisticated_simple", "instrument_options_pct"): 1,
    ("sophisticated_simple", "instrument_etf_pct"): 1,
    ("sophisticated_simple", "instrument_leveraged_etf"): 1,
    ("sophisticated_simple", "instrument_inverse_etf"): 1,
    ("sophisticated_simple", "risk_hedge_ratio"): 1,
    ("sophisticated_simple", "sector_count"): 1,
    ("sophisticated_simple", "instrument_complexity_trend"): 1,
    ("sophisticated_simple", "exit_trailing_stop_score"): 1,
    ("sophisticated_simple", "timing_december_shift"): 1,
    ("sophisticated_simple", "portfolio_income_component"): 1,
    # ── improving_declining (0 = declining … 100 = improving) ──
    ("improving_declining", "learning_skill_trajectory"): 1,
    ("improving_declining", "learning_win_rate_trend"): 1,
    ("improving_declining", "learning_risk_trend"): -1,
    ("improving_declining", "learning_hold_optimization"): -1,
    ("improving_declining", "learning_mistake_repetition"): -1,
    ("improving_declining", "learning_sizing_improvement"): -1,
    # ── independent_herd (0 = herd … 100 = independent) ──
    ("independent_herd", "social_contrarian_independence"): 1,
    ("independent_herd", "social_meme_rate"): -1,
    ("independent_herd", "social_copycat"): -1,
    ("independent_herd", "market_herd_score"): -1,
    ("independent_herd", "social_bagholding"): -1,
    ("independent_herd", "bias_availability"): -1,
    ("independent_herd", "social_influence_trend"): -1,
    # ── risk_seeking_averse (0 = averse … 100 = risk seeking) ──
    ("risk_seeking_averse", "sizing_max_single_trade_pct"): 1,
    ("risk_seeking_averse", "sizing_avg_position_pct"): 1,
    ("risk_seeking_averse", "risk_has_stops"): -1,
    ("risk_seeking_averse", "risk_max_loss_pct"): 1,
    ("risk_seeking_averse", "instrument_leveraged_etf"): 1,
    ("risk_seeking_averse", "sizing_after_losses"): 1,
    ("risk_seeking_averse", "sector_meme_exposure"): 1,
    ("risk_seeking_averse", "portfolio_long_only"): 1,
    ("risk_seeking_averse", "risk_hedge_ratio"): -1,
    ("risk_seeking_averse", "holding_pct_day_trades"): 1,
    ("risk_seeking_averse", "psych_escalation"): 1,
}

# Normalization range per (dimension, feature).  Raw value is linearly mapped
# from [low, high] → [0, 1], clamped.
_NORM_RANGES: dict[tuple[str, str], tuple[float, float]] = {
    # ── active_passive ──
    ("active_passive", "timing_trading_days_per_month"): (3, 18),
    ("active_passive", "timing_avg_trades_per_active_day"): (1, 5),
    ("active_passive", "holding_pct_investment"): (0, 0.9),
    ("active_passive", "holding_pct_day_trades"): (0, 0.7),
    ("active_passive", "holding_pct_swing"): (0, 0.7),
    ("active_passive", "portfolio_monthly_turnover"): (0.05, 0.8),
    ("active_passive", "exit_partial_ratio"): (0, 0.7),
    ("active_passive", "sector_ticker_churn"): (0, 0.8),
    ("active_passive", "instrument_etf_pct"): (0, 0.8),
    # ── momentum_value ──
    ("momentum_value", "entry_breakout_score"): (0, 0.7),
    ("momentum_value", "entry_above_ma_score"): (0.3, 0.9),
    ("momentum_value", "entry_dip_buyer_score"): (0, 0.6),
    ("momentum_value", "entry_vs_52w_range"): (0.2, 0.8),
    ("momentum_value", "entry_on_red_days"): (0, 1.0),
    ("momentum_value", "entry_on_green_days"): (0, 1.0),
    ("momentum_value", "market_contrarian_score"): (-0.5, 0.5),
    ("momentum_value", "holding_median_days"): (5, 120),
    # ── concentrated_diversified ──
    ("concentrated_diversified", "instrument_top3_concentration"): (0.2, 0.8),
    ("concentrated_diversified", "sector_hhi"): (0.1, 0.5),
    ("concentrated_diversified", "portfolio_diversification"): (0.2, 0.9),
    ("concentrated_diversified", "instrument_unique_tickers"): (3, 25),
    ("concentrated_diversified", "sizing_max_single_trade_pct"): (0.05, 0.35),
    ("concentrated_diversified", "sector_count"): (2, 8),
    ("concentrated_diversified", "sector_core_vs_explore"): (0.3, 0.9),
    # ── disciplined_emotional ──
    ("disciplined_emotional", "psych_revenge_score"): (0, 0.6),
    ("disciplined_emotional", "psych_freeze_score"): (0, 0.5),
    ("disciplined_emotional", "sizing_cv"): (0.3, 2.0),
    ("disciplined_emotional", "holding_cv"): (0.3, 2.0),
    ("disciplined_emotional", "psych_emotional_index"): (0, 0.6),
    ("disciplined_emotional", "exit_take_profit_discipline"): (0, 0.8),
    ("disciplined_emotional", "risk_has_stops"): (0, 1.0),
    ("disciplined_emotional", "learning_mistake_repetition"): (0, 0.5),
    ("disciplined_emotional", "bias_disposition"): (0.8, 1.5),
    # ── sophisticated_simple ──
    ("sophisticated_simple", "h_overall_sophistication"): (0, 100),
    ("sophisticated_simple", "instrument_options_pct"): (0, 0.3),
    ("sophisticated_simple", "instrument_etf_pct"): (0, 1.0),
    ("sophisticated_simple", "instrument_leveraged_etf"): (0, 1.0),
    ("sophisticated_simple", "instrument_inverse_etf"): (0, 1.0),
    ("sophisticated_simple", "risk_hedge_ratio"): (0, 0.3),
    ("sophisticated_simple", "sector_count"): (2, 8),
    ("sophisticated_simple", "instrument_complexity_trend"): (-0.5, 0.5),
    ("sophisticated_simple", "exit_trailing_stop_score"): (0, 0.5),
    ("sophisticated_simple", "timing_december_shift"): (0.8, 2.0),
    ("sophisticated_simple", "portfolio_income_component"): (0, 1.0),
    # ── improving_declining ──
    ("improving_declining", "learning_skill_trajectory"): (-1.0, 1.0),
    ("improving_declining", "learning_win_rate_trend"): (-0.5, 0.5),
    ("improving_declining", "learning_risk_trend"): (-0.5, 0.5),
    ("improving_declining", "learning_hold_optimization"): (-0.5, 0.5),
    ("improving_declining", "learning_mistake_repetition"): (0, 0.5),
    ("improving_declining", "learning_sizing_improvement"): (-0.5, 0.5),
    # ── independent_herd ──
    ("independent_herd", "social_contrarian_independence"): (0, 1.0),
    ("independent_herd", "social_meme_rate"): (0, 0.5),
    ("independent_herd", "social_copycat"): (0, 0.6),
    ("independent_herd", "market_herd_score"): (-0.5, 0.5),
    ("independent_herd", "social_bagholding"): (0, 0.5),
    ("independent_herd", "bias_availability"): (0, 0.8),
    ("independent_herd", "social_influence_trend"): (-0.5, 0.5),
    # ── risk_seeking_averse ──
    ("risk_seeking_averse", "sizing_max_single_trade_pct"): (0.05, 0.35),
    ("risk_seeking_averse", "sizing_avg_position_pct"): (0.02, 0.2),
    ("risk_seeking_averse", "risk_has_stops"): (0, 1.0),
    ("risk_seeking_averse", "risk_max_loss_pct"): (5, 50),
    ("risk_seeking_averse", "instrument_leveraged_etf"): (0, 1.0),
    ("risk_seeking_averse", "sizing_after_losses"): (0.7, 1.5),
    ("risk_seeking_averse", "sector_meme_exposure"): (0, 0.3),
    ("risk_seeking_averse", "portfolio_long_only"): (0, 1.0),
    ("risk_seeking_averse", "risk_hedge_ratio"): (0, 0.3),
    ("risk_seeking_averse", "holding_pct_day_trades"): (0, 0.4),
    ("risk_seeking_averse", "psych_escalation"): (0, 0.5),
}

# Human-readable evidence templates.  {value} is replaced at runtime.
_EVIDENCE_TEMPLATES: dict[str, str] = {
    "timing_trading_days_per_month": "Trades {value:.0f} days per month",
    "timing_avg_trades_per_active_day": "{value:.1f} trades per active day",
    "holding_pct_investment": "{value:.0%} of positions are investment-length holds",
    "holding_pct_day_trades": "{value:.0%} of trades are day trades",
    "holding_pct_swing": "{value:.0%} of trades are swing trades",
    "portfolio_monthly_turnover": "{value:.0%} monthly portfolio turnover",
    "exit_partial_ratio": "{value:.0%} partial-exit ratio",
    "sector_ticker_churn": "{value:.0%} ticker churn rate",
    "instrument_etf_pct": "{value:.0%} ETF allocation",
    "entry_breakout_score": "{value:.0%} breakout entry score",
    "entry_above_ma_score": "{value:.0%} of entries above moving average",
    "entry_dip_buyer_score": "{value:.0%} dip-buyer score",
    "entry_vs_52w_range": "Entries at {value:.0%} of 52-week range",
    "entry_on_red_days": "{value:.0f} entries on red days",
    "entry_on_green_days": "{value:.0f} entries on green days",
    "market_contrarian_score": "Contrarian score of {value:+.2f}",
    "holding_median_days": "Median holding period of {value:.0f} days",
    "instrument_top3_concentration": "Top 3 tickers are {value:.0%} of portfolio",
    "sector_hhi": "Sector concentration (HHI) of {value:.2f}",
    "portfolio_diversification": "Diversification score of {value:.0%}",
    "instrument_unique_tickers": "{value:.0f} unique tickers traded",
    "sizing_max_single_trade_pct": "Largest trade at {value:.0%} of portfolio",
    "sector_count": "{value:.0f} sectors traded",
    "sector_core_vs_explore": "Core-vs-explore ratio of {value:.0%}",
    "psych_revenge_score": "Revenge trading score of {value:.0%}",
    "psych_freeze_score": "Freeze response score of {value:.0%}",
    "sizing_cv": "Position sizing consistency (CV {value:.2f})",
    "holding_cv": "Holding period consistency (CV {value:.2f})",
    "psych_emotional_index": "Emotional index at {value:.0%}",
    "exit_take_profit_discipline": "Take-profit discipline of {value:.0%}",
    "risk_has_stops": "Stop-loss usage rate of {value:.0%}",
    "learning_mistake_repetition": "Mistake repetition rate of {value:.0%}",
    "bias_disposition": "Disposition effect ratio of {value:.2f}",
    "instrument_options_pct": "{value:.0%} options usage",
    "instrument_leveraged_etf": "Leveraged ETF exposure of {value:.0%}",
    "instrument_inverse_etf": "Inverse ETF exposure of {value:.0%}",
    "risk_hedge_ratio": "Hedge ratio of {value:.0%}",
    "instrument_complexity_trend": "Complexity trend of {value:+.2f}",
    "exit_trailing_stop_score": "Trailing stop score of {value:.0%}",
    "timing_december_shift": "December activity shift of {value:.1f}x",
    "portfolio_income_component": "Income component of {value:.0%}",
    "learning_skill_trajectory": "Skill trajectory of {value:+.2f}",
    "learning_win_rate_trend": "Win rate trend of {value:+.2f}",
    "learning_risk_trend": "Risk trend of {value:+.2f}",
    "learning_hold_optimization": "Hold optimization trend of {value:+.2f}",
    "learning_sizing_improvement": "Sizing improvement of {value:+.2f}",
    "social_contrarian_independence": "Independence score of {value:.0%}",
    "social_meme_rate": "{value:.0%} meme stock trading rate",
    "social_copycat": "Copycat score of {value:.0%}",
    "market_herd_score": "Herd following score of {value:+.2f}",
    "social_bagholding": "Bagholding rate of {value:.0%}",
    "bias_availability": "Availability bias of {value:.0%}",
    "social_influence_trend": "Social influence trend of {value:+.2f}",
    "sizing_avg_position_pct": "Average position size of {value:.0%}",
    "risk_max_loss_pct": "Max single-trade loss of {value:.1f}%",
    "sizing_after_losses": "Post-loss sizing ratio of {value:.1f}x",
    "sector_meme_exposure": "{value:.0%} meme stock exposure",
    "portfolio_long_only": "Long-only ratio of {value:.0%}",
    "psych_escalation": "Escalation behavior of {value:.0%}",
}


def load_classifier_config() -> dict[str, Any] | None:
    """Load classifier config from Supabase feature_registry + dimension_registry.

    Fetches active dimensions and their feature weights, caches the result
    in a module-level variable so subsequent calls are free.  Returns *None*
    if Supabase is unreachable (caller should fall back to hardcoded weights).
    """
    global _cached_config
    if _cached_config is not None:
        return _cached_config

    try:
        from storage.supabase_client import _get_client

        client = _get_client()
        if client is None:
            logger.info("[CLASSIFY_V2] Supabase not configured; using hardcoded weights")
            return None

        # Load active dimensions
        dim_result = (
            client.table("dimension_registry")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        dim_rows = dim_result.data or []

        # Load active features (filter out null dimension_feeds in Python
        # for maximum client-library compatibility)
        feat_result = (
            client.table("feature_registry")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        feat_rows = [
            r for r in (feat_result.data or [])
            if r.get("dimension_feeds")
        ]

        # Build config structure
        config: dict[str, Any] = {"dimensions": {}}

        for dim in dim_rows:
            dim_key = dim["dimension_key"]
            config["dimensions"][dim_key] = {
                "name": dim["name"],
                "low_label": dim["low_label"],
                "high_label": dim["high_label"],
                "display_order": dim.get("display_order", 0),
                "features": {},
            }

        # Group features into their dimension, including direction + norm ranges
        for feat in feat_rows:
            dim_key = feat["dimension_feeds"]
            if dim_key not in config["dimensions"]:
                continue
            feat_key = feat["feature_key"]
            config["dimensions"][dim_key]["features"][feat_key] = {
                "weight": float(feat.get("weight", 0.0)),
                "direction": feat.get("direction"),    # SMALLINT: 1 or -1 or None
                "norm_min": feat.get("norm_min"),       # FLOAT or None
                "norm_max": feat.get("norm_max"),       # FLOAT or None
            }

        _cached_config = config
        total_features = sum(
            len(d["features"]) for d in config["dimensions"].values()
        )
        dir_norm_count = sum(
            1
            for d in config["dimensions"].values()
            for fc in d["features"].values()
            if fc.get("direction") is not None
            and fc.get("norm_min") is not None
            and fc.get("norm_max") is not None
        )
        logger.info(
            "[CLASSIFIER] Loaded config from Supabase: %d dimensions, "
            "%d features, %d direction+norm mappings",
            len(config["dimensions"]),
            total_features,
            dir_norm_count,
        )
        return config

    except Exception:
        logger.warning(
            "[CLASSIFY_V2] Failed to load config from Supabase; "
            "will use hardcoded fallback",
            exc_info=True,
        )
        return None


def _normalize(value: float, low: float, high: float) -> float:
    """Normalize *value* from [low, high] → [0, 1], clamped."""
    if high == low:
        return 0.5
    return max(0.0, min(1.0, (value - low) / (high - low)))


def _generate_label(
    score: float,
    low_label: str,
    high_label: str,
) -> str:
    """Generate a human-readable label from a 0-100 score.

    Ranges:
        0-15   → low_label
        16-35  → "Leaning <low_label>"
        36-50  → "Moderate"
        51-65  → "Leaning <high_label>"
        66-85  → high_label
        86-100 → "Extreme <high_label>"
    """
    if score <= 15:
        return low_label
    if score <= 35:
        return f"Leaning {low_label}"
    if score <= 50:
        return "Moderate"
    if score <= 65:
        return f"Leaning {high_label}"
    if score <= 85:
        return high_label
    return f"Extreme {high_label}"


def _format_evidence_entry(feat_key: str, value: float) -> str:
    """Format a single feature contribution as a human-readable string."""
    template = _EVIDENCE_TEMPLATES.get(feat_key)
    if template:
        try:
            return template.format(value=value)
        except (ValueError, KeyError):
            pass
    # Fallback: turn "sizing_avg_position_pct" → "sizing avg position pct"
    readable = feat_key.replace("_", " ")
    if 0 < abs(value) < 1:
        return f"{readable}: {value:.0%}"
    return f"{readable}: {value:.2f}"


def _score_dimension_from_config(
    features: dict[str, Any],
    dim_cfg: dict[str, Any],
    dim_key: str,
) -> dict[str, Any]:
    """Score a single dimension using config-driven weights and ranges."""
    components: list[tuple[float, float]] = []
    # (feat_key, weighted_contribution, raw_value) — only for present features
    contributions: list[tuple[str, float, float]] = []

    for feat_key, feat_cfg in dim_cfg["features"].items():
        weight = feat_cfg["weight"]
        if weight <= 0:
            continue

        value = _safe(features, feat_key)

        if feat_key in _ABS_FEATURES:
            value = abs(value)

        # Direction: prefer Supabase config, fall back to hardcoded dict
        cfg_direction = feat_cfg.get("direction")
        if cfg_direction is not None:
            direction = int(cfg_direction)
        else:
            fallback_dir = _DIRECTION_MAP.get((dim_key, feat_key))
            if fallback_dir is not None:
                direction = fallback_dir
            else:
                logger.warning(
                    "[CLASSIFY_V2] No direction for %s.%s — skipping",
                    dim_key, feat_key,
                )
                continue

        # Normalization range: prefer Supabase config, fall back to hardcoded
        cfg_norm_min = feat_cfg.get("norm_min")
        cfg_norm_max = feat_cfg.get("norm_max")
        if cfg_norm_min is not None and cfg_norm_max is not None:
            norm_range = (float(cfg_norm_min), float(cfg_norm_max))
        else:
            fallback_range = _NORM_RANGES.get((dim_key, feat_key))
            if fallback_range is not None:
                norm_range = fallback_range
            else:
                logger.warning(
                    "[CLASSIFY_V2] No norm range for %s.%s — skipping",
                    dim_key, feat_key,
                )
                continue

        normalized = _normalize(value, norm_range[0], norm_range[1])
        if direction == -1:
            normalized = 1.0 - normalized

        component_score = normalized * 100.0
        components.append((component_score, weight))

        # Track contribution for evidence (only features actually present)
        if features.get(feat_key) is not None:
            contributions.append(
                (feat_key, abs(component_score * weight), value)
            )

    if not components:
        return {"score": 50.0, "label": "Moderate", "evidence": []}

    # Weighted average → 0-100 regardless of whether weights sum to 1
    total_weight = sum(w for _, w in components)
    if total_weight > 0:
        score = _clamp(sum(s * w for s, w in components) / total_weight)
    else:
        score = 50.0

    label = _generate_label(
        score,
        dim_cfg.get("low_label", "Low"),
        dim_cfg.get("high_label", "High"),
    )

    # Evidence: top 3 features by absolute weighted contribution
    contributions.sort(key=lambda x: x[1], reverse=True)
    evidence = [
        _format_evidence_entry(fk, val)
        for fk, _, val in contributions[:3]
    ]

    return {
        "score": round(score, 1),
        "label": label,
        "evidence": evidence,
    }


def _classify_from_config(
    features: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Score all dimensions using Supabase-driven config."""
    dimensions: dict[str, dict[str, Any]] = {}
    for dim_key, dim_cfg in config["dimensions"].items():
        dimensions[dim_key] = _score_dimension_from_config(
            features, dim_cfg, dim_key,
        )
    return dimensions


def _classify_hardcoded(features: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Score all dimensions using the original hardcoded weights (fallback)."""
    return {
        "active_passive": _score_active_passive(features),
        "momentum_value": _score_momentum_value(features),
        "concentrated_diversified": _score_concentrated_diversified(features),
        "disciplined_emotional": _score_disciplined_emotional(features),
        "sophisticated_simple": _score_sophisticated_simple(features),
        "improving_declining": _score_improving_declining(features),
        "independent_herd": _score_independent_herd(features),
        "risk_seeking_averse": _score_risk_seeking_averse(features),
    }


# ── Primary archetype mapping ───────────────────────────────────────────────


def _map_primary_archetype(dims: dict[str, dict], f: dict) -> tuple[str, float]:
    """Assign a primary archetype from the 8 dimension scores.

    Returns (archetype_name, confidence).
    Checks rules in priority order; first match wins.
    """
    active = dims["active_passive"]["score"]
    momentum = dims["momentum_value"]["score"]
    concentrated = dims["concentrated_diversified"]["score"]
    disciplined = dims["disciplined_emotional"]["score"]
    improving = dims["improving_declining"]["score"]
    sophisticated = dims["sophisticated_simple"]["score"]
    risk_seeking = dims["risk_seeking_averse"]["score"]

    meme_rate = _safe(f, "social_meme_rate")
    day_pct = _safe(f, "holding_pct_day_trades")
    etf_pct = _safe(f, "instrument_etf_pct")

    rules: list[tuple[bool, str, float]] = [
        (active < 25 and etf_pct > 0.5, "Passive Indexer", 0.85),
        (active > 80 and day_pct > 0.3, "Day Trader", 0.80),
        (active > 60 and momentum > 70, "Momentum Trader", 0.75),
        (active > 60 and momentum < 30, "Value Hunter", 0.75),
        (concentrated > 70 and disciplined > 60, "Conviction Investor", 0.70),
        (concentrated > 70 and disciplined < 40, "Concentrated Gambler", 0.65),
        (risk_seeking > 75 and meme_rate > 0.2, "Meme Trader", 0.65),
        (disciplined > 80 and active > 50, "Systematic Trader", 0.80),
        (improving > 70, "Evolving Trader", 0.60),
        (sophisticated > 70, "Multi-Strategy", 0.70),
    ]

    for condition, archetype, conf in rules:
        if condition:
            return archetype, conf

    # Default: label based on the dimension with the largest deviation from 50
    all_dims = {
        "active_passive": ("Active Trader" if active > 50 else "Passive Trader", active),
        "momentum_value": ("Momentum Trader" if momentum > 50 else "Value Investor", momentum),
        "concentrated_diversified": ("Concentrated Investor" if concentrated > 50 else "Diversified Investor", concentrated),
        "disciplined_emotional": ("Disciplined Trader" if disciplined > 50 else "Intuitive Trader", disciplined),
        "risk_seeking_averse": ("Risk Taker" if risk_seeking > 50 else "Conservative Trader", risk_seeking),
    }
    strongest_key = max(all_dims, key=lambda k: abs(all_dims[k][1] - 50))
    return all_dims[strongest_key][0], 0.50


# ── Summary generator ────────────────────────────────────────────────────────


def _build_summary(dims: dict[str, dict], archetype: str) -> str:
    """One-sentence behavioral summary in natural language.

    Pattern: [Holding style] [entry strategy] [noun] [with/making] [2-3 traits].

    Target quality: "Patient momentum trader making concentrated bets in
    basic instruments with independent conviction."

    Every word carries information about this specific trader.  Avoids filler
    like "straightforward", "methodical", "who is", "moderately".
    """
    scores = {k: v["score"] for k, v in dims.items()}
    ap = scores["active_passive"]
    mv = scores["momentum_value"]
    cd = scores["concentrated_diversified"]
    de = scores["disciplined_emotional"]
    ss = scores["sophisticated_simple"]
    ih = scores["independent_herd"]
    rs = scores["risk_seeking_averse"]

    # ── Holding-style adjective ──
    if ap >= 70:
        tempo = "Active"
    elif ap >= 55:
        tempo = "Frequent"
    elif ap <= 30:
        tempo = "Patient"
    elif ap <= 42:
        tempo = "Deliberate"
    else:
        tempo = ""  # near-neutral: skip to avoid "moderate"

    # ── Entry-strategy adjective ──
    if mv >= 70:
        strategy = "momentum"
    elif mv >= 55:
        strategy = "trend-following"
    elif mv <= 30:
        strategy = "value"
    elif mv <= 42:
        strategy = "contrarian"
    else:
        strategy = ""

    # ── Noun ──
    noun = "trader" if ap > 50 else "investor"

    # ── Build the lead: "Patient momentum trader" / "Active value investor" ──
    lead_parts = [p for p in [tempo, strategy, noun] if p]
    lead = " ".join(lead_parts)

    # ── Collect behavioural trait phrases, ranked by distinctiveness ──
    # Each phrase is a compact noun phrase that works with "with".
    trait_candidates: list[tuple[str, float]] = []

    # Concentration
    if cd >= 65:
        trait_candidates.append(("concentrated bets", abs(cd - 50)))
    elif cd <= 35:
        trait_candidates.append(("diversified holdings", abs(cd - 50)))

    # Instruments
    if ss <= 30:
        trait_candidates.append(("basic instruments", abs(ss - 50)))
    elif ss >= 70:
        trait_candidates.append(("multi-instrument strategies", abs(ss - 50)))

    # Discipline
    if de >= 70:
        trait_candidates.append(("disciplined holds", abs(de - 50)))
    elif de <= 30:
        trait_candidates.append(("reactive exits", abs(de - 50)))

    # Independence
    if ih >= 65:
        trait_candidates.append(("independent conviction", abs(ih - 50)))
    elif ih <= 35:
        trait_candidates.append(("herd-influenced timing", abs(ih - 50)))

    # Risk
    if rs >= 65:
        trait_candidates.append(("aggressive sizing", abs(rs - 50)))
    elif rs <= 35:
        trait_candidates.append(("conservative sizing", abs(rs - 50)))

    # Trajectory
    imp = scores["improving_declining"]
    if imp >= 65:
        trait_candidates.append(("improving results", abs(imp - 50)))
    elif imp <= 35:
        trait_candidates.append(("declining returns", abs(imp - 50)))

    # Sort by deviation (most distinctive first) and take top 3
    trait_candidates.sort(key=lambda t: t[1], reverse=True)
    phrases = [t[0] for t in trait_candidates[:3]]

    if not phrases:
        return f"{lead.capitalize()} with a balanced profile."

    # ── Assemble ──
    # "Patient momentum trader with concentrated bets, disciplined holds,
    #  and independent conviction."
    if len(phrases) == 1:
        return f"{lead.capitalize()} with {phrases[0]}."
    elif len(phrases) == 2:
        return f"{lead.capitalize()} with {phrases[0]} and {phrases[1]}."
    else:
        return f"{lead.capitalize()} with {phrases[0]}, {phrases[1]}, and {phrases[2]}."


# ── Public API ───────────────────────────────────────────────────────────────


def classify_v2(
    features: dict[str, Any],
    v1_classification: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    holdings_features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Produce a multi-dimensional behavioral profile from the 212-feature dict.

    Args:
        features: Flat dict as returned by ``extract_all_features()``.
        v1_classification: Optional old classifier output for comparison.
        config: Optional pre-loaded classifier config from Supabase.
            If *None*, calls ``load_classifier_config()``; falls back to
            hardcoded weights when Supabase is unreachable.
        holdings_features: Optional dict of 69 h_ features from
            ``HoldingsExtractor.extract()``.  When provided, merged with
            trade features before dimension scoring, enabling the
            feature_registry's h_ entries to feed into dimension scores.

    Returns:
        Dict with ``dimensions``, ``primary_archetype``,
        ``archetype_confidence``, ``behavioral_summary``, and
        ``v1_comparison``.
    """
    # Merge holdings features into the feature dict if provided
    # h_ features don't collide with trade features (different prefix)
    merged = dict(features)
    if holdings_features:
        for k, v in holdings_features.items():
            if k.startswith("h_") and v is not None:
                merged[k] = v
        logger.info(
            "[CLASSIFY_V2] Merged %d holdings features (281 total)",
            sum(1 for k in holdings_features if k.startswith("h_") and holdings_features[k] is not None),
        )

    # ── Score dimensions (prefer Supabase config, fall back to hardcoded) ──
    try:
        if config is None:
            config = load_classifier_config()
        if config and config.get("dimensions"):
            dimensions = _classify_from_config(merged, config)
            logger.debug("[CLASSIFY_V2] Scored via Supabase config")
        else:
            dimensions = _classify_hardcoded(merged)
            logger.debug("[CLASSIFY_V2] Scored via hardcoded weights (no config)")
    except Exception:
        logger.warning(
            "[CLASSIFY_V2] Config-driven scoring failed; "
            "falling back to hardcoded weights",
            exc_info=True,
        )
        dimensions = _classify_hardcoded(merged)

    archetype, confidence = _map_primary_archetype(dimensions, merged)
    summary = _build_summary(dimensions, archetype)

    result: dict[str, Any] = {
        "dimensions": dimensions,
        "primary_archetype": archetype,
        "archetype_confidence": round(confidence, 2),
        "behavioral_summary": summary,
        "v1_comparison": {},
        "holdings_available": holdings_features is not None and len(holdings_features or {}) > 0,
    }

    if v1_classification:
        result["v1_comparison"] = {
            "v1_dominant_archetype": v1_classification.get("dominant_archetype"),
            "v1_archetype_probabilities": v1_classification.get("archetype_probabilities"),
            "v1_confidence": v1_classification.get("confidence_score"),
            "v1_method": v1_classification.get("method"),
        }

    logger.info(
        "[CLASSIFY_V2] %s (%.0f%% confidence) — %s",
        archetype, confidence * 100, summary,
    )

    return result
