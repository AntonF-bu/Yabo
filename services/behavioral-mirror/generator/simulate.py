"""Simulate trades for each synthetic trader against real market data."""

from __future__ import annotations

import csv
import json
import logging
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from generator.market_data import TICKER_SECTOR, get_earnings_dates, get_trading_dates

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TRADES_DIR = DATA_DIR / "trades"
GT_DIR = DATA_DIR / "ground_truth"


@dataclass
class OpenPosition:
    ticker: str
    shares: int
    entry_price: float
    entry_date: pd.Timestamp
    peak_price: float = 0.0

    def __post_init__(self) -> None:
        self.peak_price = self.entry_price


@dataclass
class TraderState:
    cash: float
    positions: list[OpenPosition] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    recent_pnl: list[float] = field(default_factory=list)
    day_trades_5d: list[pd.Timestamp] = field(default_factory=list)
    loss_streak: int = 0
    paused_until: pd.Timestamp | None = None
    last_dca_date: pd.Timestamp | None = None  # track DCA schedule


def _pick_tickers(profile: dict[str, Any], available: list[str], n: int = 5) -> list[str]:
    """Pick tickers weighted by sector affinity."""
    sector_aff = profile.get("sector_affinity", {})
    rng = random.Random(hash(profile["trader_id"]))
    weights: list[float] = []
    for t in available:
        sector = TICKER_SECTOR.get(t, "Other")
        w = sector_aff.get(sector, 0.05) + 0.02
        weights.append(w)
    total = sum(weights)
    probs = [w / total for w in weights]
    chosen = set()
    attempts = 0
    while len(chosen) < min(n, len(available)) and attempts < 200:
        pick = rng.choices(available, weights=probs, k=1)[0]
        chosen.add(pick)
        attempts += 1
    return list(chosen)


def _should_enter(profile: dict[str, Any], ticker: str, date: pd.Timestamp,
                  mkt: pd.DataFrame, earnings_dates: dict[str, list[pd.Timestamp]],
                  state: TraderState, rng: random.Random) -> bool:
    """Decide if the trader should open a new position today."""
    entry_style = profile["entry_style"]
    discipline = profile["discipline_score"]
    daily_prob = profile["trades_per_month"] / 21.0
    daily_prob *= max(0.2, 1.0 - len(state.positions) * 0.15)

    if len(state.positions) >= 8:
        return False
    if any(p.ticker == ticker for p in state.positions):
        return False

    price = mkt.get(f"{ticker}_Close")
    if price is None or pd.isna(price):
        return False
    min_trade = float(price) * 5
    if state.cash < min_trade:
        return False

    # Noise
    if rng.random() > discipline:
        return rng.random() < daily_prob * 0.3

    # --- DCA scheduled: regular interval buying ---
    dca_weight = entry_style.get("dca_scheduled", 0)
    if dca_weight > 0.3:
        interval_days = max(7, int(30 / max(profile["trades_per_month"], 0.5)))
        if state.last_dca_date is None or (date - state.last_dca_date).days >= interval_days:
            if rng.random() < dca_weight * 1.5:
                state.last_dca_date = date
                return True

    score = 0.0

    # Breakout
    ma20 = mkt.get(f"{ticker}_MA20")
    vol_ratio = mkt.get(f"{ticker}_VolRatio")
    if not pd.isna(ma20) and not pd.isna(vol_ratio):
        if float(price) > float(ma20) and float(vol_ratio) > 1.2:
            score += entry_style.get("breakout", 0) * 1.5

    # Dip buy
    high10 = mkt.get(f"{ticker}_High10")
    rsi = mkt.get(f"{ticker}_RSI")
    if not pd.isna(high10) and not pd.isna(rsi) and float(high10) > 0:
        drop = (float(high10) - float(price)) / float(high10)
        if drop > 0.03 and float(rsi) < 40:
            score += entry_style.get("dip_buy", 0) * 1.5

    # Earnings anticipation — much stronger signal
    edates = earnings_dates.get(ticker, [])
    for ed in edates:
        diff = (ed - date).days
        if 0 < diff <= 5:
            score += entry_style.get("earnings_anticipation", 0) * 3.0
            break

    # Technical signal
    if not pd.isna(rsi) and 28 < float(rsi) < 35:
        score += entry_style.get("technical_signal", 0) * 1.5

    threshold = 0.3
    return (score * daily_prob) > threshold or (score > 0.5 and rng.random() < daily_prob)


def _should_exit(profile: dict[str, Any], pos: OpenPosition, date: pd.Timestamp,
                 current_price: float, state: TraderState, rng: random.Random) -> bool:
    """Decide if the trader should close a position today."""
    exit_style = profile["exit_style"]
    discipline = profile["discipline_score"]
    risk_tol = profile["risk_tolerance"]

    pnl_pct = (current_price - pos.entry_price) / pos.entry_price
    hold_days = (date - pos.entry_date).days
    base_hold = profile["holding_period_base_days"]

    pos.peak_price = max(pos.peak_price, current_price)
    drawdown_from_peak = (pos.peak_price - current_price) / pos.peak_price if pos.peak_price > 0 else 0

    # === HARD TIME LIMIT: force exit if held way too long ===
    # This ensures day traders don't hold for months
    max_hold = base_hold * 3.0 + 5
    if hold_days > max_hold:
        return True

    # Noise
    if rng.random() > discipline:
        return rng.random() < 0.03

    # Tax awareness deferral
    tax_jur = profile.get("tax_jurisdiction", "TX")
    from generator.profiles import TAX_RATES
    tax_rate = TAX_RATES.get(tax_jur, 0.20)
    tax_awareness = profile.get("tax_awareness", 0.5)
    if tax_awareness > 0.7 and tax_rate > 0.25 and pnl_pct > 0 and 300 <= hold_days < 366:
        return False

    score = 0.0

    # Target hit
    target = 0.10 + risk_tol * 0.15
    if pnl_pct >= target:
        score += exit_style.get("target_hit", 0) * 2.0

    # Trailing stop
    stop_pct = 0.05 + (1 - risk_tol) * 0.10
    if drawdown_from_peak >= stop_pct and hold_days >= 1:
        score += exit_style.get("trailing_stop", 0) * 2.0

    # Time-based exit — stronger multiplier so positions don't overshoot base_hold
    noise_factor = 1.0 + rng.uniform(-0.3, 0.3)
    if hold_days >= base_hold * noise_factor:
        overshoot = hold_days / max(base_hold, 0.5)
        time_score = exit_style.get("time_based", 0) * min(overshoot * 1.5, 5.0)
        score += time_score

    # Fatigue: all traders eventually exit as hold far exceeds base_hold
    if hold_days > base_hold * 2:
        fatigue = min((hold_days / max(base_hold, 0.5) - 2.0) * 0.25, 0.9)
        if rng.random() < fatigue:
            return True

    # Panic sell
    panic_threshold = -(risk_tol * 0.20)
    if pnl_pct <= panic_threshold:
        score += exit_style.get("panic_sell", 0) * 2.5

    # Stop loss from drawdown response
    dd_resp = profile.get("drawdown_response", "hold_through")
    if pnl_pct < -0.05:
        if dd_resp == "stop_loss" and pnl_pct < -(0.05 + (1 - risk_tol) * 0.10):
            score += 1.5
        elif dd_resp == "panic_sell" and pnl_pct < -0.08:
            score += 1.0

    # hold_forever suppression
    if exit_style.get("hold_forever", 0) > 0.3 and pnl_pct > -0.15:
        score *= 0.3

    return score > 0.8


def _position_size(profile: dict[str, Any], price: float, state: TraderState,
                   rng: random.Random) -> int:
    """Calculate number of shares to buy."""
    risk_tol = profile["risk_tolerance"]
    acct_value = state.cash + sum(p.shares * p.entry_price for p in state.positions)
    if acct_value <= 0:
        return 0
    base_alloc = acct_value * risk_tol * 0.15
    if profile.get("conviction_sizing"):
        base_alloc *= rng.uniform(0.5, 1.5)
    max_alloc = acct_value * 0.25
    alloc = min(base_alloc, max_alloc, state.cash * 0.95)
    shares = int(alloc / price)
    return max(shares, 1) if alloc > price else 0


def _check_pdt(state: TraderState, date: pd.Timestamp, is_day_trade: bool) -> bool:
    """Check if PDT rule blocks this trade. Returns True if blocked."""
    cutoff = date - pd.Timedelta(days=5)
    state.day_trades_5d = [d for d in state.day_trades_5d if d > cutoff]
    if is_day_trade and len(state.day_trades_5d) >= 3:
        return True
    return False


def simulate_trader(profile: dict[str, Any], market_data: pd.DataFrame) -> tuple[list[dict], dict]:
    """Simulate trades for a single trader."""
    rng = random.Random(hash(profile["trader_id"]) + 123)

    trader_id = profile["trader_id"]
    trading_dates = get_trading_dates(market_data)
    earnings_dates = get_earnings_dates(market_data)

    all_tickers = [t for t in TICKER_SECTOR if t not in ("SPY", "QQQ", "IWM")
                   and f"{t}_Close" in market_data.columns]
    focus_tickers = _pick_tickers(profile, all_tickers, n=rng.randint(4, 12))

    # Scale simulation length by holding period so long-hold traders get enough time
    base_hold = profile["holding_period_base_days"]
    min_months = max(6, int(base_hold / 21) + 4)
    sim_months = rng.randint(min_months, max(min_months + 3, 15))
    sim_months = min(sim_months, 18)  # cap at 18 months
    start_offset = rng.randint(0, max(0, len(trading_dates) - sim_months * 21 - 60))
    start_idx = start_offset + 60
    end_idx = min(start_idx + sim_months * 21, len(trading_dates))

    state = TraderState(cash=float(profile["account_size"]))
    fees_per_trade = 0.0
    if profile["brokerage_platform"] == "interactive_brokers":
        fees_per_trade = 1.0

    for i in range(start_idx, end_idx):
        date = trading_dates[i]
        row = market_data.iloc[i]

        if state.paused_until and date < state.paused_until:
            continue

        # --- Exit logic ---
        for pos in list(state.positions):
            cp = row.get(f"{pos.ticker}_Close")
            if cp is None or pd.isna(cp):
                continue
            current_price = float(cp)

            if _should_exit(profile, pos, date, current_price, state, rng):
                is_day_trade = (date - pos.entry_date).days == 0
                if profile["pdt_constrained"] and _check_pdt(state, date, is_day_trade):
                    continue

                proceeds = pos.shares * current_price - fees_per_trade
                pnl = (current_price - pos.entry_price) * pos.shares
                state.cash += proceeds
                state.positions.remove(pos)
                state.recent_pnl.append(pnl)
                if len(state.recent_pnl) > 20:
                    state.recent_pnl = state.recent_pnl[-20:]
                if is_day_trade:
                    state.day_trades_5d.append(date)

                state.trades.append({
                    "trader_id": trader_id,
                    "ticker": pos.ticker,
                    "action": "SELL",
                    "quantity": pos.shares,
                    "price": round(current_price, 2),
                    "date": date.strftime("%Y-%m-%d"),
                    "fees": round(fees_per_trade, 2),
                })

                if pnl < 0:
                    state.loss_streak += 1
                    lsr = profile.get("loss_streak_response", "no_change")
                    if lsr == "pause_trading" and state.loss_streak >= 3:
                        state.paused_until = date + pd.Timedelta(days=rng.randint(3, 10))
                else:
                    state.loss_streak = 0

        # --- Entry logic ---
        rng.shuffle(focus_tickers)
        for ticker in focus_tickers:
            if _should_enter(profile, ticker, date, row, earnings_dates, state, rng):
                price_val = row.get(f"{ticker}_Close")
                if price_val is None or pd.isna(price_val):
                    continue
                price = float(price_val)
                shares = _position_size(profile, price, state, rng)
                if shares <= 0:
                    continue
                cost = shares * price + fees_per_trade
                if cost > state.cash:
                    shares = int((state.cash - fees_per_trade) / price)
                    if shares <= 0:
                        continue
                    cost = shares * price + fees_per_trade

                state.cash -= cost
                state.positions.append(OpenPosition(
                    ticker=ticker, shares=shares,
                    entry_price=price, entry_date=date,
                ))
                state.trades.append({
                    "trader_id": trader_id,
                    "ticker": ticker,
                    "action": "BUY",
                    "quantity": shares,
                    "price": round(price, 2),
                    "date": date.strftime("%Y-%m-%d"),
                    "fees": round(fees_per_trade, 2),
                })

    # Force-close remaining
    if state.positions and end_idx < len(trading_dates):
        last_row = market_data.iloc[min(end_idx, len(trading_dates) - 1)]
        last_date = trading_dates[min(end_idx, len(trading_dates) - 1)]
        for pos in list(state.positions):
            cp = last_row.get(f"{pos.ticker}_Close")
            if cp is None or pd.isna(cp):
                continue
            current_price = float(cp)
            proceeds = pos.shares * current_price - fees_per_trade
            state.cash += proceeds
            state.positions.remove(pos)
            state.trades.append({
                "trader_id": trader_id,
                "ticker": pos.ticker,
                "action": "SELL",
                "quantity": pos.shares,
                "price": round(current_price, 2),
                "date": last_date.strftime("%Y-%m-%d"),
                "fees": round(fees_per_trade, 2),
            })

    ground_truth = {
        "trader_id": trader_id,
        **{k: v for k, v in profile.items() if k != "trader_id"},
    }
    return state.trades, ground_truth


def save_trades(trader_id: str, trades: list[dict]) -> Path:
    TRADES_DIR.mkdir(parents=True, exist_ok=True)
    path = TRADES_DIR / f"{trader_id}.csv"
    if not trades:
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["trader_id", "ticker", "action", "quantity", "price", "date", "fees"])
            writer.writeheader()
        return path
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=trades[0].keys())
        writer.writeheader()
        writer.writerows(trades)
    return path


def save_ground_truth(trader_id: str, ground_truth: dict) -> Path:
    GT_DIR.mkdir(parents=True, exist_ok=True)
    path = GT_DIR / f"{trader_id}.json"
    with open(path, "w") as f:
        json.dump(ground_truth, f, indent=2, default=str)
    return path


def save_manifest(profiles: list[dict[str, Any]]) -> Path:
    manifest = [{"trader_id": p["trader_id"], "archetype_weights": p["archetype_weights"]}
                for p in profiles]
    path = DATA_DIR / "manifest.json"
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    return path
