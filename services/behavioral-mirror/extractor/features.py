"""Archetype scoring: derive trait scores from extracted features."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> int:
    return int(max(lo, min(hi, value)))


def compute_trait_scores(
    holding: dict[str, Any],
    entry: dict[str, Any],
    exit_patterns: dict[str, Any],
    wl: dict[str, Any],
    sizing: dict[str, Any],
    trips: list[dict],
    trade_freq: float,
) -> dict[str, int]:
    """Compute archetype trait scores (0-100) from extracted features.

    Uses multiplicative scoring: each archetype requires MULTIPLE distinctive
    features to align.  Holding period is the primary differentiator.
    """

    dist = holding.get("distribution", {})
    mean_hold = holding.get("mean_days", 30)
    breakout = entry.get("breakout_pct", 0)
    dip_buy = entry.get("dip_buy_pct", 0)
    earnings = entry.get("earnings_proximity_pct", 0)
    dca_det = entry.get("dca_pattern_detected", False)

    short_pct = dist.get("intraday", 0) + dist.get("1_5_days", 0)
    long_pct = dist.get("90_365_days", 0) + dist.get("365_plus_days", 0)
    very_long_pct = dist.get("365_plus_days", 0)

    # --- Momentum ---
    # Breakout entries + medium holds (5-60 days) + trailing stops + higher freq
    momentum = 0.0
    momentum += breakout * 120
    if 5 < mean_hold < 60:
        momentum += 30
    if exit_patterns.get("trailing_stop_detected"):
        momentum += 20
    if trade_freq > 6:
        momentum += 15
    if mean_hold > 90:
        momentum *= 0.4
    if mean_hold > 180:
        momentum *= 0.3
    momentum = _clamp(momentum)

    # --- Value ---
    # Dip-buy entries + LONG holds (60+ days) + low frequency
    value = 0.0
    value += dip_buy * 80
    if mean_hold > 60:
        value += min(40, (mean_hold - 60) / 3)
    value += long_pct * 80
    if trade_freq < 5:
        value += 15
    if mean_hold < 30:
        value *= 0.3
    if short_pct > 0.4:
        value *= 0.3
    value = _clamp(value)

    # --- Income ---
    # DCA entries, very long holds (180+), extremely low frequency
    income = 0.0
    if dca_det:
        income += 50
    income += very_long_pct * 100
    income += dist.get("90_365_days", 0) * 50
    if mean_hold > 180:
        income += 25
    if trade_freq < 3:
        income += 20
    if mean_hold < 60:
        income *= 0.2
    if trade_freq > 8:
        income *= 0.3
    income = _clamp(income)

    # --- Swing ---
    # Short-medium holds (2-20 days), mixed entries, moderate-high freq
    swing = 0.0
    swing += dist.get("1_5_days", 0) * 100
    swing += dist.get("5_20_days", 0) * 80
    if 2 < mean_hold < 20:
        swing += 35
    if 5 < trade_freq < 30:
        swing += 15
    if mean_hold > 40:
        swing *= 0.3
    if long_pct > 0.3:
        swing *= 0.3
    swing = _clamp(swing)

    # --- Day trading ---
    # Intraday/very short holds, very high frequency
    day_trading = 0.0
    day_trading += dist.get("intraday", 0) * 200
    day_trading += dist.get("1_5_days", 0) * 80
    if mean_hold < 3:
        day_trading += 50
    elif mean_hold < 5:
        day_trading += 25
    if trade_freq > 20:
        day_trading += 30
    if mean_hold > 10:
        day_trading *= 0.2
    if mean_hold > 30:
        day_trading *= 0.1
    day_trading = _clamp(day_trading)

    # --- Event-driven ---
    # Earnings proximity is THE defining signal
    event_driven = 0.0
    event_driven += earnings * 250
    if dist.get("1_5_days", 0) + dist.get("5_20_days", 0) > 0.5:
        event_driven += 15
    if earnings < 0.05:
        event_driven *= 0.2
    event_driven = _clamp(event_driven)

    # --- Mean reversion ---
    # Dip-buy entries + SHORT-MEDIUM holds (3-30 days) + target exits
    mean_reversion = 0.0
    mean_reversion += dip_buy * 100
    if 3 < mean_hold < 30:
        mean_reversion += 30
    if exit_patterns.get("stop_loss_detected"):
        mean_reversion += 15
    if wl.get("win_rate", 0) > 0.55:
        mean_reversion += 10
    if mean_hold > 60:
        mean_reversion *= 0.3
    if long_pct > 0.3:
        mean_reversion *= 0.4
    mean_reversion = _clamp(mean_reversion)

    # --- Passive DCA ---
    # DCA detected + very long holds + very low frequency
    passive_dca = 0.0
    if dca_det:
        passive_dca += 55
    if trade_freq < 4:
        passive_dca += 25
    passive_dca += long_pct * 50
    if mean_hold > 60:
        passive_dca += 15
    if trade_freq > 8:
        passive_dca *= 0.2
    if mean_hold < 30:
        passive_dca *= 0.3
    passive_dca = _clamp(passive_dca)

    # --- Risk appetite ---
    risk = 0.0
    risk += sizing.get("avg_position_pct", 0) * 3
    risk += sizing.get("max_position_pct", 0) * 1.5
    if trade_freq > 15:
        risk += 20
    if day_trading > 50:
        risk += 15
    risk = _clamp(risk)

    # --- Discipline ---
    discipline = 0.0
    discipline += sizing.get("position_size_consistency", 0) * 60
    if exit_patterns.get("stop_loss_detected"):
        discipline += 20
    if exit_patterns.get("trailing_stop_detected"):
        discipline += 15
    win_rate = wl.get("win_rate", 0.5)
    if 0.4 < win_rate < 0.65:
        discipline += 10
    discipline = _clamp(discipline)

    # --- Conviction consistency ---
    conviction = 0.0
    if sizing.get("conviction_sizing_detected"):
        conviction += 50
    if sizing.get("position_size_consistency", 0) > 0.7:
        conviction += 25
    if wl.get("profit_factor", 0) > 1.5:
        conviction += 25
    conviction = _clamp(conviction)

    # --- Loss aversion ---
    loss_aversion = 0.0
    avg_loser = abs(wl.get("avg_loser_pct", 0))
    avg_winner = abs(wl.get("avg_winner_pct", 0))
    if avg_loser > 0 and avg_winner > 0:
        ratio = avg_loser / avg_winner
        if ratio < 0.5:
            loss_aversion += 60
        elif ratio < 0.8:
            loss_aversion += 40
        elif ratio > 1.5:
            loss_aversion += 10
    if exit_patterns.get("stop_loss_detected"):
        loss_aversion += 25
    post_loss_change = sizing.get("post_loss_sizing_change", 0)
    if post_loss_change < -0.2:
        loss_aversion += 20
    loss_aversion = _clamp(loss_aversion)

    return {
        "momentum_score": momentum,
        "value_score": value,
        "income_score": income,
        "swing_score": swing,
        "day_trading_score": day_trading,
        "event_driven_score": event_driven,
        "mean_reversion_score": mean_reversion,
        "passive_dca_score": passive_dca,
        "risk_appetite": risk,
        "discipline": discipline,
        "conviction_consistency": conviction,
        "loss_aversion": loss_aversion,
    }


def compute_stress_response(trips: list[dict], sizing: dict[str, Any],
                            timing_info: dict[str, float]) -> dict[str, Any]:
    """Analyze stress/drawdown behavior."""
    if not trips:
        return {
            "drawdown_behavior": "insufficient_data",
            "max_drawdown_pct": 0.0,
            "recovery_time_avg_days": 0.0,
            "loss_streak_response": "insufficient_data",
            "post_loss_sizing_change": 0.0,
            "post_loss_frequency_change": 0.0,
            "revenge_trading_score": 0,
        }

    cum_pnl: list[float] = []
    running = 0.0
    for t in trips:
        running += t["pnl"]
        cum_pnl.append(running)

    arr = np.array(cum_pnl)
    peak = np.maximum.accumulate(arr)
    drawdowns = (peak - arr) / np.where(peak > 0, peak, 1.0)
    max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

    recovery_days: list[float] = []
    in_dd = False
    dd_start_idx = 0
    for i in range(1, len(arr)):
        if arr[i] < peak[i] and not in_dd:
            in_dd = True
            dd_start_idx = i
        elif arr[i] >= peak[i] and in_dd:
            in_dd = False
            days = (trips[i]["exit_date"] - trips[dd_start_idx]["entry_date"]).days
            recovery_days.append(days)

    avg_recovery = float(np.mean(recovery_days)) if recovery_days else 0.0

    post_loss_sizing = sizing.get("post_loss_sizing_change", 0.0)
    post_loss_freq = timing_info.get("post_loss_frequency_change", 0.0)

    if max_dd < 0.05:
        dd_behavior = "minimal_drawdowns"
    elif post_loss_sizing > 0.1:
        dd_behavior = "average_down"
    elif post_loss_sizing < -0.3:
        dd_behavior = "reduce_and_hedge"
    elif max_dd > 0.15 and avg_recovery < 10:
        dd_behavior = "stop_loss"
    else:
        dd_behavior = "hold_through"

    if post_loss_freq > 0.3:
        ls_response = "pause_trading"
    elif post_loss_freq < -0.3:
        ls_response = "revenge_trade"
    elif post_loss_sizing < -0.2:
        ls_response = "reduce_size"
    else:
        ls_response = "no_change"

    revenge = 0
    if post_loss_freq < -0.2:
        revenge += 40
    if post_loss_sizing > 0.2:
        revenge += 30
    revenge = min(revenge, 100)

    return {
        "drawdown_behavior": dd_behavior,
        "max_drawdown_pct": round(max_dd * 100, 2),
        "recovery_time_avg_days": round(avg_recovery, 1),
        "loss_streak_response": ls_response,
        "post_loss_sizing_change": round(post_loss_sizing, 4),
        "post_loss_frequency_change": round(post_loss_freq, 4),
        "revenge_trading_score": revenge,
    }


def compute_active_vs_passive(trips: list[dict], market_data: pd.DataFrame | None) -> dict[str, Any]:
    """Compare trader returns to passive SPY buy-and-hold."""
    if not trips or market_data is None:
        return {
            "active_return_pct": 0.0,
            "passive_shadow_pct": 0.0,
            "alpha": 0.0,
            "information_ratio": None,
        }

    total_invested = sum(t["entry_price"] * t["quantity"] for t in trips)
    total_pnl = sum(t["pnl"] for t in trips)
    active_return = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0

    first_date = min(t["entry_date"] for t in trips)
    last_date = max(t["exit_date"] for t in trips)

    spy_start = market_data.get("SPY_Close")
    if spy_start is None:
        return {
            "active_return_pct": round(active_return, 2),
            "passive_shadow_pct": 0.0,
            "alpha": round(active_return, 2),
            "information_ratio": None,
        }

    try:
        idx_start = spy_start.index.searchsorted(first_date)
        idx_end = spy_start.index.searchsorted(last_date)
        spy_price_start = float(spy_start.iloc[max(0, idx_start)])
        spy_price_end = float(spy_start.iloc[min(idx_end, len(spy_start) - 1)])
        passive_return = ((spy_price_end - spy_price_start) / spy_price_start * 100)
    except Exception:
        passive_return = 0.0

    alpha = active_return - passive_return

    info_ratio = None
    if len(trips) >= 10:
        trip_returns = [t["pnl_pct"] for t in trips]
        tracking_error = float(np.std(trip_returns))
        if tracking_error > 0:
            info_ratio = round(alpha / (tracking_error * 100), 4)

    return {
        "active_return_pct": round(active_return, 2),
        "passive_shadow_pct": round(passive_return, 2),
        "alpha": round(alpha, 2),
        "information_ratio": info_ratio,
    }
