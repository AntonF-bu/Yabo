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
    holdings_profile: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Compute archetype trait scores (0-100) from extracted features.

    Uses multiplicative scoring: each archetype requires MULTIPLE distinctive
    features to align.  Holding period is the primary differentiator.
    Holdings profile (what the trader buys) is now equally weighted with
    how they trade.
    """

    dist = holding.get("distribution", {})
    mean_hold = holding.get("mean_days", 30)
    breakout = entry.get("breakout_pct", 0)
    dip_buy = entry.get("dip_buy_pct", 0)
    earnings = entry.get("earnings_proximity_pct", 0)
    dca_det = entry.get("dca_pattern_detected", False)
    dca_soft = entry.get("dca_soft_detected", False)

    # New MA-relative and RSI features for better discrimination
    pct_above_ma = entry.get("pct_above_ma20", 0.5)
    pct_below_ma = entry.get("pct_below_ma20", 0.5)
    avg_rsi = entry.get("avg_rsi_at_entry", 50.0)
    avg_ma_dev = entry.get("avg_entry_ma20_deviation", 0.0)
    avg_vol_ratio = entry.get("avg_vol_ratio_at_entry", 1.0)

    # Holdings-based features (what the trader buys)
    hp = holdings_profile or {}
    holdings_risk = hp.get("holdings_risk_score", 50)
    speculative_ratio = hp.get("speculative_holdings_ratio", 0.0)
    avg_mcap_cat = hp.get("weighted_avg_market_cap_category", "unknown")
    vol_exposure = hp.get("sector_volatility_exposure", {})
    high_vol_pct = vol_exposure.get("high", 0.0)
    low_vol_pct = vol_exposure.get("low", 0.0)
    index_etf_pct = hp.get("index_etf_pct", 0.0)

    short_pct = dist.get("intraday", 0) + dist.get("1_5_days", 0)
    med_short_pct = dist.get("5_20_days", 0)
    long_pct = dist.get("90_365_days", 0) + dist.get("365_plus_days", 0)
    very_long_pct = dist.get("365_plus_days", 0)

    # --- Momentum ---
    # Breakout entries + above MA20 + medium holds (5-60d) + trailing stops + higher freq
    momentum = 0.0
    momentum += breakout * 120
    momentum += pct_above_ma * 40        # buying above MA = momentum signal
    if avg_ma_dev > 0.02:               # buying well above MA
        momentum += 20
    if avg_rsi > 55:                     # entering on strength
        momentum += 15
    if 5 < mean_hold < 60:
        momentum += 30
    if exit_patterns.get("trailing_stop_detected"):
        momentum += 20
    if trade_freq > 6:
        momentum += 15
    # Penalties
    if mean_hold > 90:
        momentum *= 0.3
    if pct_below_ma > 0.6:              # mostly buying below MA = not momentum
        momentum *= 0.4
    if dca_det:
        momentum *= 0.3
    # Holdings-based boost: high-risk speculative holdings + medium holds = growth conviction
    # A trader holding IONQ, SOUN, INMB for 100+ days is growth/momentum, not value
    if holdings_risk > 50 and mean_hold > 30:
        momentum += 25
    if speculative_ratio > 0.25:
        momentum += 15
    if high_vol_pct > 0.5:
        momentum += 10
    # Low-risk blue chip holdings = less momentum
    if holdings_risk < 25 and low_vol_pct > 0.5:
        momentum *= 0.6
    momentum = _clamp(momentum)

    # --- Value ---
    # Dip-buy entries + below MA20 + LONG holds (60+d) + low frequency
    value = 0.0
    value += dip_buy * 70
    value += pct_below_ma * 25
    if mean_hold > 60:
        value += min(35, (mean_hold - 60) / 3)
    value += long_pct * 90               # strongest signal: actually holding long
    if trade_freq < 5:
        value += 15
    if avg_rsi < 40:
        value += 10
    # Penalties
    if mean_hold < 30:
        value *= 0.2
    if short_pct > 0.4:
        value *= 0.3
    if breakout > 0.3:
        value *= 0.5
    # DCA penalty only if dip_buy is LOW (true DCA buys on schedule, not dips)
    if (dca_det or dca_soft) and dip_buy < 0.4:
        value *= 0.5
    # Holdings-based penalty: value investors buy established, proven companies
    # A portfolio of IONQ + INMB + SOUN is NOT a value portfolio regardless of hold period
    if holdings_risk > 50:
        value *= 0.35
    if speculative_ratio > 0.15:
        value *= 0.4
    if avg_mcap_cat in ("mid", "small", "micro", "unknown"):
        value *= 0.4
    if high_vol_pct > 0.5:
        value *= 0.6
    value = _clamp(value)

    # --- Income ---
    # DCA entries, very long holds (180+), extremely low frequency
    income = 0.0
    if dca_det:
        income += 50
    elif dca_soft:
        income += 30
    income += very_long_pct * 100
    income += dist.get("90_365_days", 0) * 50
    if mean_hold > 180:
        income += 25
    elif mean_hold > 90:
        income += 10
    if trade_freq < 3:
        income += 20
    # Penalties
    if mean_hold < 60:
        income *= 0.2
    if trade_freq > 8:
        income *= 0.3
    if breakout > 0.3:
        income *= 0.5
    if short_pct > 0.3:
        income *= 0.3
    # Holdings-based penalty: income investors hold dividend aristocrats and blue chips
    # A tech/biotech-heavy speculative portfolio is NOT an income portfolio
    if holdings_risk > 40:
        income *= 0.3
    if high_vol_pct > 0.5:
        income *= 0.4
    if speculative_ratio > 0.15:
        income *= 0.35
    income = _clamp(income)

    # --- Swing ---
    # 2-15 day holds + mixed entry styles + MODERATE freq (not day-trader freq)
    swing = 0.0
    swing_hold_pct = dist.get("1_5_days", 0) + dist.get("5_20_days", 0)
    swing += swing_hold_pct * 80
    if 2 < mean_hold < 15:
        swing += 35
    elif 15 <= mean_hold < 25:
        swing += 15
    if 5 < trade_freq < 30:
        swing += 15
    # Penalties
    if mean_hold > 40:
        swing *= 0.3
    if long_pct > 0.3:
        swing *= 0.3
    if dist.get("intraday", 0) > 0.5:
        swing *= 0.4
    if trade_freq > 35:                  # very high freq = day trader, not swing
        swing *= 0.4
    if breakout > 0.45:
        swing *= 0.5
    if earnings > 0.20:
        swing *= 0.4
    if dca_det:
        swing *= 0.3
    if pct_below_ma > 0.65 and dip_buy > 0.4:  # dip buying below MA = mean_reversion
        swing *= 0.5
    swing = _clamp(swing)

    # --- Day trading ---
    # Intraday/very short holds, very high frequency
    day_trading = 0.0
    day_trading += dist.get("intraday", 0) * 200
    day_trading += dist.get("1_5_days", 0) * 60
    if mean_hold < 3:
        day_trading += 50
    elif mean_hold < 5:
        day_trading += 25
    if trade_freq > 20:
        day_trading += 30
    if avg_vol_ratio > 1.3:             # active volume trading
        day_trading += 10
    # Penalties
    if mean_hold > 10:
        day_trading *= 0.2
    if mean_hold > 30:
        day_trading *= 0.1
    if dca_det:
        day_trading *= 0.1
    day_trading = _clamp(day_trading)

    # --- Event-driven ---
    # Earnings proximity is THE defining signal
    event_driven = 0.0
    event_driven += earnings * 250
    if dist.get("1_5_days", 0) + dist.get("5_20_days", 0) > 0.5:
        event_driven += 15
    # Penalties
    if earnings < 0.05:
        event_driven *= 0.2
    if dca_det:
        event_driven *= 0.3
    event_driven = _clamp(event_driven)

    # --- Mean reversion ---
    # Dip-buy entries + BELOW MA20 + SHORT holds (3-30d) + target exits
    mean_reversion = 0.0
    mean_reversion += dip_buy * 80
    mean_reversion += pct_below_ma * 30
    if avg_rsi < 40:
        mean_reversion += 15
    if avg_ma_dev < -0.02:
        mean_reversion += 15
    if 3 < mean_hold < 30:
        mean_reversion += 30
    if med_short_pct > 0.3:
        mean_reversion += 15
    if exit_patterns.get("stop_loss_detected"):
        mean_reversion += 10
    if wl.get("win_rate", 0) > 0.55:
        mean_reversion += 10
    # Penalties — separate from value (long holds) and swing (no dip signal)
    if mean_hold > 45:
        mean_reversion *= 0.3
    if mean_hold > 70:
        mean_reversion *= 0.2
    if long_pct > 0.2:
        mean_reversion *= 0.3
    if dca_det or dca_soft:
        mean_reversion *= 0.3
    if pct_above_ma > 0.6:             # buying above MA = not mean reversion
        mean_reversion *= 0.4
    mean_reversion = _clamp(mean_reversion)

    # --- Passive DCA ---
    # DCA detected + long holds + very low frequency
    # KEY: passive DCA buys on SCHEDULE, not on dips. High dip_buy = value, not DCA.
    passive_dca = 0.0
    if dca_det:
        passive_dca += 55
    elif dca_soft:
        passive_dca += 35
    if trade_freq < 4:
        passive_dca += 25
    passive_dca += long_pct * 50
    if mean_hold > 60:
        passive_dca += 15
    # Index ETF boost: >50% index ETFs = strong passive signal
    if index_etf_pct > 0.5:
        passive_dca += 30
    elif index_etf_pct > 0.25:
        passive_dca += 15
    # Penalties
    if trade_freq > 8:
        passive_dca *= 0.2
    if mean_hold < 30:
        passive_dca *= 0.3
    if breakout > 0.3:
        passive_dca *= 0.4
    if short_pct > 0.3:
        passive_dca *= 0.3
    if dip_buy > 0.5:
        passive_dca *= 0.5              # high dip_buy = value investor, not DCA
    # Holdings-based penalty: passive DCA buys index funds or blue chips, not speculative names.
    # A trader picking IONQ/SOUN/INMB on a monthly funding schedule is making active bets,
    # not passively dollar-cost averaging.
    if momentum > 70:
        passive_dca *= 0.3                  # strong momentum characteristics ≠ passive
    if holdings_risk > 50 and index_etf_pct < 0.25:
        passive_dca *= 0.4                  # speculative micro caps ≠ DCA targets
    if speculative_ratio > 0.15:
        passive_dca *= 0.5                  # 15%+ in sub-$2B = active bets
    unique_tickers_traded = len({t["ticker"] for t in trips}) if trips else 0
    if unique_tickers_traded > 8 and mean_hold < 120:
        passive_dca *= 0.6                  # DCA = 1-4 positions held indefinitely
    passive_dca = _clamp(passive_dca)

    # --- Risk appetite ---
    risk = 0.0
    risk += sizing.get("avg_position_pct", 0) * 3
    risk += sizing.get("max_position_pct", 0) * 1.5
    if trade_freq > 15:
        risk += 20
    if day_trading > 50:
        risk += 15
    # Holdings-based: speculative/high-risk holdings increase risk appetite score
    risk += holdings_risk * 0.3
    if speculative_ratio > 0.3:
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

    # Reconstruct portfolio-level equity curve.
    # Base value scaled to total capital deployed, minimum 100K.
    total_deployed = sum(
        abs(t.get("entry_price", 0) * t.get("quantity", 0)) for t in trips
    )
    base_value = max(total_deployed * 0.5, 100_000.0)

    cum_pnl: list[float] = []
    running = 0.0
    for t in trips:
        pnl = t["pnl"]
        # Sanity check: clamp extreme PnL values
        if abs(pnl) > base_value * 5:
            logger.warning("Clamping extreme PnL value: %.2f for %s", pnl, t.get("ticker", "?"))
            pnl = max(min(pnl, base_value), -base_value * 0.5)
        running += pnl
        cum_pnl.append(running)

    equity = np.array([base_value + pnl for pnl in cum_pnl])
    # Floor equity at 10% of base to prevent extreme drawdown ratios
    equity = np.maximum(equity, base_value * 0.1)
    peak = np.maximum.accumulate(equity)
    drawdowns = (peak - equity) / np.where(peak > 0, peak, 1.0)
    max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
    max_dd = min(max_dd, 0.95)  # Cap at 95% — 100% means zero equity, unrealistic

    recovery_days: list[float] = []
    in_dd = False
    dd_start_idx = 0
    for i in range(1, len(equity)):
        if equity[i] < peak[i] and not in_dd:
            in_dd = True
            dd_start_idx = i
        elif equity[i] >= peak[i] and in_dd:
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


def compute_options_profile(
    option_trades: list[dict[str, Any]],
    estimated_portfolio_value: float | None = None,
) -> dict[str, Any] | None:
    """Compute behavioral profile from options trades.

    Returns None if no option trades exist.
    """
    if not option_trades:
        return None

    calls_bought = sum(1 for t in option_trades if t["side"] == "BUY" and t["option_type"] == "CALL")
    calls_sold = sum(1 for t in option_trades if t["side"] == "SELL" and t["option_type"] == "CALL")
    puts_bought = sum(1 for t in option_trades if t["side"] == "BUY" and t["option_type"] == "PUT")
    puts_sold = sum(1 for t in option_trades if t["side"] == "SELL" and t["option_type"] == "PUT")
    exercises = sum(1 for t in option_trades if t.get("is_exercise_or_assignment"))

    # Directional bias
    bullish = calls_bought + puts_sold
    bearish = puts_bought + calls_sold
    total_directional = bullish + bearish
    if total_directional > 0:
        bullish_ratio = bullish / total_directional
        if bullish_ratio > 0.75:
            directional_bias = "strongly_bullish"
        elif bullish_ratio > 0.55:
            directional_bias = "bullish"
        elif bullish_ratio < 0.25:
            directional_bias = "strongly_bearish"
        elif bullish_ratio < 0.45:
            directional_bias = "bearish"
        else:
            directional_bias = "mixed"
    else:
        directional_bias = "neutral"

    # Expiry horizon classification
    dte_values = [t["days_to_expiry"] for t in option_trades if t.get("days_to_expiry")]
    horizon = {"weekly": 0, "monthly": 0, "quarterly": 0, "leaps": 0}
    for dte in dte_values:
        if dte < 7:
            horizon["weekly"] += 1
        elif dte <= 45:
            horizon["monthly"] += 1
        elif dte <= 120:
            horizon["quarterly"] += 1
        else:
            horizon["leaps"] += 1

    avg_dte = np.mean(dte_values) if dte_values else 0

    # Premium analysis
    premiums = [t["total_premium"] for t in option_trades if t.get("total_premium")]
    total_premium = sum(premiums) if premiums else 0
    avg_premium = np.mean(premiums) if premiums else 0

    premium_pct = 0.0
    if estimated_portfolio_value and estimated_portfolio_value > 0:
        premium_pct = total_premium / estimated_portfolio_value * 100

    # Underlying concentration
    underlying_conc: dict[str, dict[str, Any]] = {}
    for t in option_trades:
        ut = t.get("underlying_ticker", "UNKNOWN")
        if ut not in underlying_conc:
            underlying_conc[ut] = {"trades": 0, "total_premium": 0.0, "bullish": 0, "bearish": 0}
        underlying_conc[ut]["trades"] += 1
        underlying_conc[ut]["total_premium"] += t.get("total_premium", 0) or 0
        if t["direction"] in ("bullish",):
            underlying_conc[ut]["bullish"] += 1
        elif t["direction"] in ("bearish",):
            underlying_conc[ut]["bearish"] += 1

    # Determine direction per underlying
    for ut, data in underlying_conc.items():
        if data["bullish"] > data["bearish"] * 2:
            data["direction"] = "bullish"
        elif data["bearish"] > data["bullish"] * 2:
            data["direction"] = "bearish"
        else:
            data["direction"] = "mixed"
        data["total_premium"] = round(data["total_premium"], 2)
        del data["bullish"]
        del data["bearish"]

    # Strategy patterns
    pure_directional = calls_bought + puts_bought
    premium_collection = calls_sold + puts_sold

    logger.info(
        "[OPTIONS] Profiled %d option trades: %d calls bought, %d calls sold, "
        "%d puts bought, %d puts sold, %d exercises. Bias: %s",
        len(option_trades), calls_bought, calls_sold, puts_bought, puts_sold,
        exercises, directional_bias,
    )

    return {
        "total_option_trades": len(option_trades),
        "calls_bought": calls_bought,
        "calls_sold": calls_sold,
        "puts_bought": puts_bought,
        "puts_sold": puts_sold,
        "exercises_and_assignments": exercises,
        "directional_bias": directional_bias,
        "bullish_trades": bullish,
        "bearish_trades": bearish,
        "preferred_expiry_horizon": horizon,
        "avg_days_to_expiry_at_entry": round(avg_dte, 1),
        "avg_premium_per_trade": round(avg_premium, 2),
        "total_premium_deployed": round(total_premium, 2),
        "premium_as_pct_of_portfolio": round(premium_pct, 2),
        "underlying_concentration": underlying_conc,
        "strategy_patterns": {
            "pure_directional": pure_directional,
            "premium_collection": premium_collection,
            "exercise_conversion": exercises,
        },
    }


def compute_options_round_trips(option_trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Match option buys with sells for the SAME option symbol (FIFO).

    Different strikes are NOT matched — only exact symbol matches.
    """
    open_lots: dict[str, list[dict]] = {}
    closed: list[dict[str, Any]] = []

    sorted_trades = sorted(option_trades, key=lambda t: t["date"])

    for t in sorted_trades:
        if t.get("is_exercise_or_assignment"):
            continue  # Don't match exercise/assignment as round trips
        symbol = t["option_symbol"]
        side = t["side"]
        contracts = t["contracts"]
        premium = t.get("premium_per_share")
        if premium is None:
            continue

        if side == "BUY":
            open_lots.setdefault(symbol, []).append({
                "symbol": symbol,
                "underlying": t.get("underlying_ticker"),
                "option_type": t["option_type"],
                "date": t["date"],
                "premium": premium,
                "contracts": contracts,
            })
        elif side == "SELL":
            lots = open_lots.get(symbol, [])
            remaining = contracts
            while remaining > 0 and lots:
                lot = lots[0]
                matched = min(remaining, lot["contracts"])
                pnl_per_share = premium - lot["premium"]
                pnl = pnl_per_share * matched * 100  # per contract = 100 shares
                pnl_pct = pnl_per_share / lot["premium"] if lot["premium"] > 0 else 0

                hold_days = (t["date"] - lot["date"]).days

                closed.append({
                    "ticker": lot.get("underlying", symbol),
                    "option_symbol": symbol,
                    "option_type": lot["option_type"],
                    "instrument_type": "option",
                    "entry_date": lot["date"],
                    "exit_date": t["date"],
                    "entry_price": lot["premium"],
                    "exit_price": premium,
                    "quantity": matched * 100,  # shares-equivalent
                    "contracts": matched,
                    "hold_days": max(hold_days, 0),
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                })

                remaining -= matched
                lot["contracts"] -= matched
                if lot["contracts"] <= 0:
                    lots.pop(0)

    if closed:
        logger.info("[OPTIONS] Matched %d option round trips", len(closed))
    return closed


def compute_instruments_summary(
    equity_count: int,
    option_count: int,
    equity_tickers: int,
    option_underlyings: int,
    equity_volume: float,
    total_premium: float,
    etf_count: int,
    resolved: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build unified instrument view across equities, options, and ETFs."""
    total = equity_count + option_count
    if total == 0:
        return {"multi_instrument_trader": False, "primary_instrument": "unknown"}

    etf_volume = 0.0  # ETF trades are a subset of equity trades

    return {
        "equities": {
            "trade_count": equity_count,
            "unique_tickers": equity_tickers,
            "total_volume": round(equity_volume, 2),
            "pct_of_activity": round(equity_count / total, 2) if total > 0 else 0,
        },
        "options": {
            "trade_count": option_count,
            "unique_underlyings": option_underlyings,
            "total_premium": round(total_premium, 2),
            "pct_of_activity": round(option_count / total, 2) if total > 0 else 0,
        },
        "etfs": {
            "trade_count": etf_count,
            "unique_tickers": sum(
                1 for v in resolved.values()
                if v.get("instrument_type") == "ETF"
            ),
        },
        "multi_instrument_trader": option_count > 0,
        "primary_instrument": "equities" if equity_count >= option_count else "options",
        "leverage_usage": (
            "options_for_conviction" if option_count > 5
            else "occasional_options" if option_count > 0
            else "equities_only"
        ),
    }


def adjust_traits_for_options(
    traits: dict[str, int],
    options_profile: dict[str, Any] | None,
) -> dict[str, int]:
    """Adjust archetype trait scores based on options activity.

    Options usage is a STRONG behavioral signal that should influence classification.
    """
    if not options_profile or options_profile.get("total_option_trades", 0) < 3:
        return traits

    traits = dict(traits)  # don't mutate original

    # 1. Event-driven boost: options with short DTE suggest event plays
    avg_dte = options_profile.get("avg_days_to_expiry_at_entry", 0)
    if avg_dte < 30 and options_profile.get("pure_directional", 0) or \
       options_profile.get("strategy_patterns", {}).get("pure_directional", 0) > 3:
        traits["event_driven_score"] = _clamp(traits.get("event_driven_score", 0) + 25)

    # 2. Momentum boost if strongly directional
    bias = options_profile.get("directional_bias", "neutral")
    if bias in ("strongly_bullish", "strongly_bearish"):
        traits["momentum_score"] = _clamp(traits.get("momentum_score", 0) + 15)

    # 3. Day trading boost if weekly options
    horizon = options_profile.get("preferred_expiry_horizon", {})
    if horizon.get("weekly", 0) > 3:
        traits["day_trading_score"] = _clamp(traits.get("day_trading_score", 0) + 20)

    # 4. Risk appetite boost based on premium allocation
    premium_pct = options_profile.get("premium_as_pct_of_portfolio", 0)
    if premium_pct > 15:
        traits["risk_appetite"] = _clamp(traits.get("risk_appetite", 0) + 30)
    elif premium_pct > 5:
        traits["risk_appetite"] = _clamp(traits.get("risk_appetite", 0) + 15)

    # 5. Conviction boost from concentrated options bets
    underlying = options_profile.get("underlying_concentration", {})
    for ut, data in underlying.items():
        if data.get("total_premium", 0) > 50000:
            traits["conviction_consistency"] = _clamp(
                traits.get("conviction_consistency", 0) + 15
            )
            break

    return traits


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
