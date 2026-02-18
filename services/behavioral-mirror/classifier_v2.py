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

    # sizing_max_pct (weight 15%)
    max_pct = _safe(f, "sizing_max_pct")
    components.append((_linear(max_pct, 0.05, 0.35), 0.15))
    if max_pct > 0.2:
        evidence.append(f"Max position size of {max_pct:.0%}")

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
        f"{tickers:.0f} unique tickers with max position size of {max_pct:.0%}",
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

    # instrument_options_pct (weight 20%)
    opts = _safe(f, "instrument_options_pct")
    components.append((_linear(opts, 0, 0.3), 0.20))
    if opts > 0.1:
        evidence.append(f"{opts:.0%} options usage")

    # instrument_etf_pct as core allocation (weight 10%)
    etf = _safe(f, "instrument_etf_pct")
    components.append((_linear(etf, 0, 0.5) * 0.5, 0.10))  # moderate boost

    # leveraged / inverse ETFs (weight 10%)
    lev = _safe(f, "instrument_leveraged_etf")
    inv = _safe(f, "instrument_inverse_etf")
    lev_score = 100.0 if (lev > 0 or inv > 0) else 0.0
    components.append((lev_score, 0.10))
    if lev > 0 or inv > 0:
        evidence.append("Uses leveraged or inverse ETFs")

    # risk_hedge_ratio (weight 15%)
    hedge = _safe(f, "risk_hedge_ratio")
    components.append((_linear(hedge, 0, 0.3), 0.15))
    if hedge > 0:
        evidence.append(f"Hedge ratio of {hedge:.0%}")

    # sector_count (weight 10%)
    sec = _safe(f, "sector_count", 3)
    components.append((_linear(sec, 2, 8), 0.10))

    # instrument_complexity_trend (weight 10%)
    trend = _safe(f, "instrument_complexity_trend")
    components.append((_linear(trend, -0.5, 0.5), 0.10))

    # exit_trailing_stop_score (weight 10%)
    trail = _safe(f, "exit_trailing_stop_score")
    components.append((_linear(trail, 0, 0.5), 0.10))
    if trail > 0.2:
        evidence.append(f"Trailing stop usage score of {trail:.0%}")

    # timing_december_shift (weight 10%) — tax-aware = sophisticated
    dec = _safe(f, "timing_december_shift", 1.0)
    components.append((_linear(dec, 0.8, 2.0), 0.10))
    if dec > 1.3:
        evidence.append(f"December activity shift of {dec:.1f}x (tax aware)")

    # portfolio_income_component (weight 5%)
    income = _safe(f, "portfolio_income_component")
    components.append((_linear(income, 0, 1), 0.05))

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

    # sizing_max_pct (weight 15%)
    max_pct = _safe(f, "sizing_max_pct")
    components.append((_linear(max_pct, 0.05, 0.35), 0.15))
    if max_pct > 0.2:
        evidence.append(f"Max position of {max_pct:.0%} of portfolio")

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
        f"Max position of {max_pct:.0%} with {avg_pct:.0%} average position size",
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
    """One-sentence plain-English behavioral summary."""
    ap = dims["active_passive"]["score"]
    mv = dims["momentum_value"]["score"]
    cd = dims["concentrated_diversified"]["score"]
    de = dims["disciplined_emotional"]["score"]
    imp = dims["improving_declining"]["score"]
    ih = dims["independent_herd"]["score"]
    rs = dims["risk_seeking_averse"]["score"]

    # Activity + style + noun phrase
    if ap > 60:
        activity = "Active"
    elif ap < 40:
        activity = "Passive"
    else:
        activity = "Moderately active"

    if mv > 60:
        style = "momentum"
    elif mv < 40:
        style = "value-oriented"
    else:
        style = "blend-style"

    noun = "trader" if ap > 50 else "investor"
    opener = f"{activity} {style} {noun}"

    # Collect modifier phrases for "with X, Y, and Z"
    modifiers: list[str] = []

    if cd > 60:
        modifiers.append("concentrated positions")
    elif cd < 40:
        modifiers.append("diversified holdings")

    if de > 70:
        modifiers.append("strong discipline")
    elif de < 30:
        modifiers.append("emotional tendencies")
    else:
        modifiers.append("moderate discipline")

    if imp > 65:
        modifiers.append("improving over time")
    elif imp < 35:
        modifiers.append("a declining performance trend")

    if ih > 70:
        modifiers.append("largely independent from herd behavior")
    elif ih < 30:
        modifiers.append("significant herd influence")

    if rs > 70:
        modifiers.append("risk-tolerant sizing")
    elif rs < 30:
        modifiers.append("conservative risk management")

    if not modifiers:
        return f"{opener} with a balanced profile across all dimensions."

    if len(modifiers) == 1:
        return f"{opener} with {modifiers[0]}."

    # Oxford comma join: "X, Y, and Z"
    head = ", ".join(modifiers[:-1])
    return f"{opener} with {head}, and {modifiers[-1]}."


# ── Public API ───────────────────────────────────────────────────────────────


def classify_v2(
    features: dict[str, Any],
    v1_classification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Produce a multi-dimensional behavioral profile from the 212-feature dict.

    Args:
        features: Flat dict as returned by ``extract_all_features()``.
        v1_classification: Optional old classifier output for comparison.

    Returns:
        Dict with ``dimensions``, ``primary_archetype``,
        ``archetype_confidence``, ``behavioral_summary``, and
        ``v1_comparison``.
    """
    dimensions = {
        "active_passive": _score_active_passive(features),
        "momentum_value": _score_momentum_value(features),
        "concentrated_diversified": _score_concentrated_diversified(features),
        "disciplined_emotional": _score_disciplined_emotional(features),
        "sophisticated_simple": _score_sophisticated_simple(features),
        "improving_declining": _score_improving_declining(features),
        "independent_herd": _score_independent_herd(features),
        "risk_seeking_averse": _score_risk_seeking_averse(features),
    }

    archetype, confidence = _map_primary_archetype(dimensions, features)
    summary = _build_summary(dimensions, archetype)

    result: dict[str, Any] = {
        "dimensions": dimensions,
        "primary_archetype": archetype,
        "archetype_confidence": round(confidence, 2),
        "behavioral_summary": summary,
        "v1_comparison": {},
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
