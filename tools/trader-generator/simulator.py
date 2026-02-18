"""
Simulates trading decisions for each trader personality against real
daily OHLCV price data.  Walks through every trading day and applies
the personality-driven decision model, emotional state machine, and
life-event calendar.
"""

import datetime
import math
import random
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from market_data import get_price, get_price_history, get_trading_days
from personalities import TRENDING_BY_PERIOD

# ---------------------------------------------------------------------------
# Emotional state machine
# ---------------------------------------------------------------------------

EMOTIONAL_STATES = [
    "neutral", "confident", "overconfident", "reckless",
    "cautious", "fearful", "frozen", "revenge_mode",
]

STATE_MULTIPLIERS = {
    #                   freq   size   new_ticker_willingness  stop_tightness
    "neutral":         (1.0,   1.0,   0.5,                    0.5),
    "confident":       (1.2,   1.15,  0.6,                    0.4),
    "overconfident":   (1.5,   1.4,   0.8,                    0.25),
    "reckless":        (1.8,   1.7,   0.95,                   0.15),
    "cautious":        (0.7,   0.8,   0.3,                    0.65),
    "fearful":         (0.4,   0.5,   0.1,                    0.85),
    "frozen":          (0.1,   0.3,   0.0,                    1.0),
    "revenge_mode":    (2.0,   1.8,   0.9,                    0.1),
}


def _update_emotional_state(state: str, consec_wins: int, consec_losses: int,
                            drawdown_pct: float, last_trade_pnl_pct: float,
                            personality: Dict[str, Any],
                            rng: random.Random) -> str:
    """Transition the emotional state based on recent performance."""
    overconf = personality["overconfidence_after_wins"]
    revenge = personality["revenge_trade_tendency"]
    discipline = personality["discipline"]

    # Positive path: neutral -> confident -> overconfident -> reckless
    if state in ("neutral", "confident") and consec_wins >= 3:
        if rng.random() < overconf * (1.0 - discipline * 0.5):
            return "confident" if state == "neutral" else "overconfident"
    if state == "overconfident" and consec_wins >= 5:
        if rng.random() < overconf * 0.6:
            return "reckless"

    # Negative path: neutral -> cautious -> fearful -> frozen | revenge_mode
    if state in ("neutral", "confident", "overconfident", "reckless"):
        if consec_losses >= 2 or drawdown_pct < -0.10:
            return "cautious"
    if state == "cautious":
        if consec_losses >= 4 or drawdown_pct < -0.20:
            if rng.random() < revenge:
                return "revenge_mode"
            return "fearful"
    if state == "fearful" and drawdown_pct < -0.30:
        if rng.random() < 0.5:
            return "frozen"
        if rng.random() < revenge:
            return "revenge_mode"

    # Recovery paths
    if state in ("fearful", "frozen", "revenge_mode") and consec_wins >= 2:
        return "cautious"
    if state == "cautious" and consec_wins >= 1 and drawdown_pct > -0.05:
        return "neutral"
    if state == "reckless" and consec_losses >= 1:
        return "overconfident"

    # Mean reversion with discipline
    if state in ("overconfident", "reckless") and rng.random() < discipline * 0.05:
        return "neutral"
    if state == "revenge_mode" and rng.random() < discipline * 0.1:
        return "cautious"

    return state


# ---------------------------------------------------------------------------
# Time availability → trading probability per day
# ---------------------------------------------------------------------------

TIME_AVAILABILITY_PROBS = {
    "very_low":  0.10,   # ~1 day every 2 weeks
    "low":       0.25,   # ~1 day per week
    "medium":    0.50,   # ~half the days
    "high":      0.75,   # most days
    "full_time": 0.95,   # almost every day
}


# ---------------------------------------------------------------------------
# Trade record structure
# ---------------------------------------------------------------------------

def _make_trade(action: str, ticker: str, shares: float, price: float,
                date: pd.Timestamp, is_option: bool = False,
                option_type: str = "", option_expiry: str = "",
                result_gbp: float = 0.0,
                order_type: str = "Market") -> Dict[str, Any]:
    return {
        "action": action,           # "buy" or "sell"
        "order_type": order_type,   # "Market" or "Limit"
        "ticker": ticker,
        "shares": round(shares, 6),
        "price": round(price, 4),
        "date": date,
        "is_option": is_option,
        "option_type": option_type,
        "option_expiry": option_expiry,
        "result_gbp": round(result_gbp, 2),
    }


# ---------------------------------------------------------------------------
# Simulator
# ---------------------------------------------------------------------------

class TraderSimulator:
    """Simulates one trader through the full date window."""

    def __init__(self, personality: Dict[str, Any],
                 market_data: Dict[str, pd.DataFrame],
                 rng: random.Random, verbose: bool = False):
        self.p = personality
        self.md = market_data
        self.rng = rng
        self.verbose = verbose

        # Portfolio state
        self.cash: float = personality["account_size"]
        self.initial_cash: float = personality["account_size"]
        self.positions: Dict[str, float] = {}        # ticker -> shares held
        self.cost_basis: Dict[str, float] = {}        # ticker -> avg cost per share
        self.trades: List[Dict[str, Any]] = []

        # Options tracking
        self.open_options: List[Dict[str, Any]] = []  # open option contracts

        # Emotional state
        self.emotional_state: str = "neutral"
        self.consec_wins: int = 0
        self.consec_losses: int = 0
        self.recent_pnl: List[float] = []   # last 30 trades P&L
        self.peak_portfolio: float = personality["account_size"]

        # Life event calendar (pre-computed trading-day offsets)
        self.vacation_ranges: List[Tuple[int, int]] = []
        self.burnout_ranges: List[Tuple[int, int]] = []
        self.bonus_days: Dict[int, float] = {}
        self.fomo_days: set = set()
        self.tax_loss_years: set = set()
        self.resolution_range: Optional[Tuple[int, int]] = None
        self._compile_life_events()

        # Confidence spiral tracking
        self._spiral_active = False
        self._spiral_end_day = -1

    # ----- life event compilation -----

    def _compile_life_events(self):
        for ev in self.p["life_events"]:
            t = ev["type"]
            if t == "vacation_gap":
                s = ev["start_day_offset"]
                self.vacation_ranges.append((s, s + ev["duration_days"]))
            elif t == "burnout":
                s = ev["start_day_offset"]
                self.burnout_ranges.append((s, s + ev["duration_days"]))
            elif t == "bonus_deposit":
                self.bonus_days[ev["day_offset"]] = ev["bump_pct"]
            elif t == "fomo_event":
                self.fomo_days.add(ev["day_offset"])
            elif t == "tax_loss_harvesting":
                self.tax_loss_years.add(ev["year"])
            elif t == "new_years_resolution":
                # Map to rough trading-day offset for Jan of that year
                # 2024-01-02 is approximately day 150 from 2023-06-01
                jan_start = 150 if ev["year"] == 2024 else 0
                self.resolution_range = (jan_start, jan_start + ev["duration_days"])

    def _is_vacation(self, day_idx: int) -> bool:
        return any(s <= day_idx < e for s, e in self.vacation_ranges)

    def _is_burnout(self, day_idx: int) -> bool:
        return any(s <= day_idx < e for s, e in self.burnout_ranges)

    def _discipline_boost(self, day_idx: int) -> float:
        """Return bonus discipline during New Year's resolution."""
        if self.resolution_range and self.resolution_range[0] <= day_idx < self.resolution_range[1]:
            return 0.3
        return 0.0

    # ----- portfolio helpers -----

    def _portfolio_value(self, date: pd.Timestamp) -> float:
        val = self.cash
        for ticker, shares in self.positions.items():
            price = get_price(self.md, ticker, date)
            if price:
                val += shares * price
        return val

    def _drawdown(self, date: pd.Timestamp) -> float:
        pv = self._portfolio_value(date)
        if self.peak_portfolio <= 0:
            return 0.0
        return (pv - self.peak_portfolio) / self.peak_portfolio

    def _update_peak(self, date: pd.Timestamp):
        pv = self._portfolio_value(date)
        if pv > self.peak_portfolio:
            self.peak_portfolio = pv

    # ----- order execution -----

    def _buy(self, ticker: str, date: pd.Timestamp, fraction_of_cash: float,
             order_type: str = "Market"):
        price = get_price(self.md, ticker, date)
        if price is None or price <= 0:
            return
        # Add slippage
        slippage = self.rng.uniform(-0.005, 0.005)
        exec_price = price * (1.0 + slippage)
        if exec_price <= 0:
            return

        budget = self.cash * max(0.01, min(1.0, fraction_of_cash))
        if budget < 1.0:
            return

        shares = budget / exec_price

        # Fractional share handling
        use_fractional = self.rng.random() < self.p["instrument_comfort"]["fractional_shares"]
        if not use_fractional:
            shares = math.floor(shares)
        else:
            shares = round(shares, 6)

        if shares <= 0:
            return
        cost = shares * exec_price
        if cost > self.cash:
            shares = self.cash / exec_price
            if not use_fractional:
                shares = math.floor(shares)
            cost = shares * exec_price

        if shares <= 0 or cost < 1.0:
            return

        # Update portfolio
        self.cash -= cost
        prev_shares = self.positions.get(ticker, 0.0)
        prev_cost = self.cost_basis.get(ticker, 0.0)
        total_shares = prev_shares + shares
        if total_shares > 0:
            self.cost_basis[ticker] = (prev_cost * prev_shares + exec_price * shares) / total_shares
        self.positions[ticker] = total_shares

        # Generate time within market hours
        trade_time = self._random_market_time(date)

        self.trades.append(_make_trade(
            action="buy", ticker=ticker, shares=shares,
            price=exec_price, date=trade_time,
            order_type=order_type,
        ))

        if self.verbose:
            print(f"    BUY  {shares:.4f} {ticker} @ ${exec_price:.2f} "
                  f"(${cost:.2f}) | cash=${self.cash:.2f}")

    def _sell(self, ticker: str, date: pd.Timestamp, fraction: float = 1.0,
              order_type: str = "Market"):
        if ticker not in self.positions or self.positions[ticker] <= 0:
            return
        price = get_price(self.md, ticker, date)
        if price is None or price <= 0:
            return

        slippage = self.rng.uniform(-0.005, 0.005)
        exec_price = price * (1.0 + slippage)
        if exec_price <= 0:
            return

        shares_held = self.positions[ticker]
        shares_to_sell = shares_held * max(0.01, min(1.0, fraction))

        use_fractional = self.rng.random() < self.p["instrument_comfort"]["fractional_shares"]
        if not use_fractional and shares_to_sell < shares_held:
            shares_to_sell = math.floor(shares_to_sell)
        else:
            shares_to_sell = round(shares_to_sell, 6)

        if shares_to_sell <= 0:
            shares_to_sell = shares_held  # sell all if rounding to 0

        proceeds = shares_to_sell * exec_price
        cost_per = self.cost_basis.get(ticker, exec_price)
        pnl = (exec_price - cost_per) * shares_to_sell

        self.cash += proceeds
        self.positions[ticker] -= shares_to_sell
        if self.positions[ticker] < 1e-8:
            del self.positions[ticker]
            if ticker in self.cost_basis:
                del self.cost_basis[ticker]

        # Track wins/losses
        if pnl > 0:
            self.consec_wins += 1
            self.consec_losses = 0
        elif pnl < 0:
            self.consec_losses += 1
            self.consec_wins = 0
        self.recent_pnl.append(pnl)
        if len(self.recent_pnl) > 30:
            self.recent_pnl.pop(0)

        trade_time = self._random_market_time(date)

        self.trades.append(_make_trade(
            action="sell", ticker=ticker, shares=shares_to_sell,
            price=exec_price, date=trade_time,
            result_gbp=pnl, order_type=order_type,
        ))

        if self.verbose:
            print(f"    SELL {shares_to_sell:.4f} {ticker} @ ${exec_price:.2f} "
                  f"(PnL ${pnl:.2f}) | cash=${self.cash:.2f}")

    def _buy_option(self, ticker: str, date: pd.Timestamp,
                    option_type: str = "call", weeks_to_expiry: int = 4):
        """Simplified option purchase: long call or long put."""
        price = get_price(self.md, ticker, date)
        if price is None or price <= 0:
            return

        # Premium estimate: ~3-8% of stock price for near-the-money
        premium_pct = self.rng.uniform(0.03, 0.08)
        premium_per_contract = price * premium_pct * 100  # 100 shares per contract

        budget = self.cash * self.p["risk_appetite"] * 0.05  # small allocation
        if budget < premium_per_contract or budget < 50:
            return

        contracts = max(1, int(budget / premium_per_contract))
        cost = contracts * premium_per_contract
        if cost > self.cash:
            contracts = max(1, int(self.cash / premium_per_contract))
            cost = contracts * premium_per_contract
        if cost > self.cash:
            return

        self.cash -= cost

        expiry_date = date + pd.Timedelta(weeks=weeks_to_expiry)
        strike = round(price * (1.02 if option_type == "call" else 0.98), 2)

        self.open_options.append({
            "ticker": ticker,
            "type": option_type,
            "strike": strike,
            "contracts": contracts,
            "premium_paid": cost,
            "entry_date": date,
            "expiry_date": expiry_date,
        })

        trade_time = self._random_market_time(date)
        opt_label = f"{ticker} {strike}{option_type[0].upper()} {expiry_date.strftime('%m/%d')}"

        self.trades.append(_make_trade(
            action="buy", ticker=opt_label, shares=contracts,
            price=round(cost / contracts, 4), date=trade_time,
            is_option=True, option_type=option_type,
            option_expiry=expiry_date.strftime("%Y-%m-%d"),
        ))

        if self.verbose:
            print(f"    BUY OPTION {contracts}x {option_type} {ticker} "
                  f"strike=${strike} exp={expiry_date.date()} cost=${cost:.2f}")

    def _check_option_expiry(self, date: pd.Timestamp):
        """Close any options that have expired."""
        still_open = []
        for opt in self.open_options:
            if date >= opt["expiry_date"]:
                # Determine if ITM
                price = get_price(self.md, opt["ticker"], date)
                if price is None:
                    price = opt["strike"]  # assume worthless

                if opt["type"] == "call":
                    intrinsic = max(0, price - opt["strike"])
                else:
                    intrinsic = max(0, opt["strike"] - price)

                payout = intrinsic * 100 * opt["contracts"]
                pnl = payout - opt["premium_paid"]
                self.cash += payout

                if pnl > 0:
                    self.consec_wins += 1
                    self.consec_losses = 0
                else:
                    self.consec_losses += 1
                    self.consec_wins = 0
                self.recent_pnl.append(pnl)

                trade_time = self._random_market_time(date)
                opt_label = (f"{opt['ticker']} {opt['strike']}"
                             f"{opt['type'][0].upper()} "
                             f"{opt['expiry_date'].strftime('%m/%d')}")

                if payout > 0:
                    self.trades.append(_make_trade(
                        action="sell", ticker=opt_label,
                        shares=opt["contracts"],
                        price=round(payout / opt["contracts"], 4),
                        date=trade_time, is_option=True,
                        option_type=opt["type"],
                        result_gbp=pnl,
                    ))
                else:
                    # Expired worthless — record as sell at 0
                    self.trades.append(_make_trade(
                        action="sell", ticker=opt_label,
                        shares=opt["contracts"], price=0.0,
                        date=trade_time, is_option=True,
                        option_type=opt["type"],
                        result_gbp=-opt["premium_paid"],
                    ))

                if self.verbose:
                    status = "ITM" if payout > 0 else "WORTHLESS"
                    print(f"    OPTION EXPIRY {status}: {opt_label} PnL=${pnl:.2f}")
            else:
                still_open.append(opt)
        self.open_options = still_open

    # ----- signal scanning -----

    def _scan_signals(self, date: pd.Timestamp) -> List[Dict[str, Any]]:
        """Scan the trader's watchlist for actionable signals."""
        signals = []
        for ticker in self.p["core_watchlist"]:
            hist = get_price_history(self.md, ticker, date, lookback=20)
            if hist is None or len(hist) < 5:
                continue

            current = hist.iloc[-1]
            five_day_ret = (current / hist.iloc[-5] - 1.0) if hist.iloc[-5] > 0 else 0.0
            twenty_day_high = hist.max()
            twenty_day_low = hist.min()

            # Check held position P&L
            held = ticker in self.positions and self.positions[ticker] > 0
            position_pnl_pct = 0.0
            if held and ticker in self.cost_basis and self.cost_basis[ticker] > 0:
                position_pnl_pct = current / self.cost_basis[ticker] - 1.0

            if five_day_ret < -0.05:
                signals.append({
                    "ticker": ticker,
                    "type": "dip",
                    "magnitude": five_day_ret,
                    "held": held,
                    "position_pnl_pct": position_pnl_pct,
                })

            if current >= twenty_day_high * 0.99:
                signals.append({
                    "ticker": ticker,
                    "type": "breakout",
                    "magnitude": five_day_ret,
                    "held": held,
                    "position_pnl_pct": position_pnl_pct,
                })

            if held:
                if position_pnl_pct > 0.15:
                    signals.append({
                        "ticker": ticker,
                        "type": "profit_target",
                        "magnitude": position_pnl_pct,
                        "held": True,
                        "position_pnl_pct": position_pnl_pct,
                    })
                if position_pnl_pct < -0.08:
                    signals.append({
                        "ticker": ticker,
                        "type": "stop_loss",
                        "magnitude": position_pnl_pct,
                        "held": True,
                        "position_pnl_pct": position_pnl_pct,
                    })

        return signals

    # ----- decision engine -----

    def _decide_on_signal(self, signal: Dict[str, Any], date: pd.Timestamp,
                          day_idx: int):
        """Apply personality to a single signal and maybe execute a trade."""
        p = self.p
        ticker = signal["ticker"]
        sig_type = signal["type"]
        held = signal["held"]
        pnl_pct = signal["position_pnl_pct"]

        freq_mult, size_mult, _, stop_tight = STATE_MULTIPLIERS[self.emotional_state]
        discipline = min(1.0, p["discipline"] + self._discipline_boost(day_idx))
        order_type = "Limit" if self.rng.random() < discipline * 0.6 else "Market"

        # Base position size as fraction of cash
        base_size = p["risk_appetite"] * self.rng.uniform(0.02, 0.15)
        base_size *= size_mult
        # conviction concentrates
        base_size *= (0.5 + p["conviction"])
        # noise: humans aren't precise
        base_size *= self.rng.uniform(0.8, 1.2)
        base_size = max(0.01, min(0.5, base_size))

        if sig_type == "dip":
            if held:
                # Existing position is down and stock dipped more
                if p["loss_aversion"] > 0.6 and pnl_pct < -0.10:
                    # Panic sell
                    if self.rng.random() < p["loss_aversion"] * (1.0 - p["patience"]):
                        self._sell(ticker, date, fraction=1.0, order_type=order_type)
                        return
                # High conviction: average down
                if p["conviction"] > 0.6 and discipline > 0.4:
                    if self.rng.random() < p["conviction"] * 0.5:
                        self._buy(ticker, date, base_size * 0.5, order_type=order_type)
                        return
            else:
                # Not held — dip buy opportunity
                if p["patience"] > 0.5:
                    if self.rng.random() < p["patience"] * 0.6:
                        self._buy(ticker, date, base_size, order_type=order_type)
                        return

        elif sig_type == "breakout":
            if not held:
                # FOMO chase
                fomo_prob = p["fomo_susceptibility"] * freq_mult * 0.4
                if self.rng.random() < fomo_prob:
                    self._buy(ticker, date, base_size, order_type=order_type)
                    return
            else:
                # Hold through breakout if patient
                pass  # do nothing, which is itself a decision

        elif sig_type == "profit_target":
            # Disposition effect: most traders sell winners too fast
            sell_prob = (1.0 - p["patience"]) * 0.5
            # Discipline partially overrides disposition
            sell_prob *= (1.0 - discipline * 0.3)
            # Round number targets
            if pnl_pct > 0.20 or pnl_pct > 0.50 or pnl_pct > 1.0:
                sell_prob += 0.2
            if self.rng.random() < sell_prob:
                frac = self.rng.uniform(0.3, 1.0)
                self._sell(ticker, date, fraction=frac, order_type=order_type)
                return

        elif sig_type == "stop_loss":
            # Disposition effect: hold losers too long (default)
            sell_prob = p["loss_aversion"] * stop_tight * 0.4
            # Mental stop losses at round numbers
            if pnl_pct < -0.10:
                sell_prob += 0.1
            if pnl_pct < -0.15:
                sell_prob += 0.1
            if pnl_pct < -0.20:
                sell_prob += 0.15
            # Discipline helps enforce stops
            sell_prob *= (0.5 + discipline * 0.5)
            sell_prob = min(sell_prob, 0.9)
            if self.rng.random() < sell_prob:
                self._sell(ticker, date, fraction=1.0, order_type=order_type)
                return

    def _maybe_fomo_trade(self, date: pd.Timestamp, day_idx: int):
        """Chase a trending ticker outside the normal watchlist."""
        # Determine which quarter we're in
        dt = date.to_pydatetime() if hasattr(date, "to_pydatetime") else date
        year = dt.year
        quarter = (dt.month - 1) // 3 + 1
        period_key = f"{year}-Q{quarter}"
        trending = TRENDING_BY_PERIOD.get(period_key, [])
        if not trending:
            return

        # Pick one not already on watchlist
        outside = [t for t in trending if t not in self.p["core_watchlist"]]
        if not outside:
            outside = trending
        ticker = self.rng.choice(outside)

        fomo_prob = self.p["fomo_susceptibility"] * 0.7
        if self.rng.random() < fomo_prob:
            size = self.p["risk_appetite"] * self.rng.uniform(0.03, 0.12)
            self._buy(ticker, date, size, order_type="Market")
            if self.verbose:
                print(f"    FOMO chase: {ticker}")

    def _maybe_random_sell(self, date: pd.Timestamp):
        """Occasional random sell — needed cash, got bored, saw scary headline."""
        if not self.positions:
            return
        if self.rng.random() < 0.02:  # 2% daily chance
            ticker = self.rng.choice(list(self.positions.keys()))
            frac = self.rng.uniform(0.2, 1.0)
            if self.verbose:
                print(f"    Random sell (no clear reason): {ticker}")
            self._sell(ticker, date, fraction=frac, order_type="Market")

    def _maybe_etf_flight(self, date: pd.Timestamp):
        """During uncertain periods (fearful/cautious), buy index ETFs."""
        if self.emotional_state in ("cautious", "fearful"):
            etf_comfort = self.p["instrument_comfort"]["etfs"]
            if self.rng.random() < etf_comfort * 0.15:
                etf = self.rng.choice(["SPY", "QQQ", "VTI"])
                size = self.rng.uniform(0.05, 0.15)
                if self.verbose:
                    print(f"    Flight to index: {etf}")
                self._buy(etf, date, size, order_type="Market")

    def _maybe_option_trade(self, date: pd.Timestamp):
        """Occasionally buy options if the trader has options comfort."""
        call_comfort = self.p["instrument_comfort"]["options_calls"]
        put_comfort = self.p["instrument_comfort"]["options_puts"]

        if call_comfort <= 0 and put_comfort <= 0:
            return

        # Options are infrequent: ~5-20% of trades for those who use them
        if self.rng.random() > 0.03:  # low daily probability
            return

        if self.rng.random() < call_comfort / (call_comfort + put_comfort + 0.01):
            # Bullish call
            ticker = self.rng.choice(self.p["core_watchlist"])
            weeks = self.rng.randint(2, 8)
            self._buy_option(ticker, date, "call", weeks)
        elif put_comfort > 0:
            # Protective put on a held position
            held_tickers = [t for t in self.positions if self.positions[t] > 0]
            if held_tickers:
                ticker = self.rng.choice(held_tickers)
                weeks = self.rng.randint(2, 8)
                self._buy_option(ticker, date, "put", weeks)

    def _tax_loss_harvest(self, date: pd.Timestamp):
        """Sell losing positions in December for tax purposes."""
        losers = []
        for ticker, shares in self.positions.items():
            if shares <= 0:
                continue
            price = get_price(self.md, ticker, date)
            if price and ticker in self.cost_basis:
                if price < self.cost_basis[ticker]:
                    losers.append(ticker)
        # Sell 1-3 losers
        if losers:
            self.rng.shuffle(losers)
            for ticker in losers[:self.rng.randint(1, min(3, len(losers)))]:
                if self.verbose:
                    print(f"    Tax-loss harvest: selling {ticker}")
                self._sell(ticker, date, fraction=1.0, order_type="Market")

    # ----- time helpers -----

    def _random_market_time(self, date: pd.Timestamp) -> pd.Timestamp:
        """Generate a random time during US market hours (9:30-16:00 ET)."""
        hour = self.rng.randint(9, 15)
        minute = self.rng.randint(0, 59)
        second = self.rng.randint(0, 59)
        if hour == 9:
            minute = max(30, minute)
        return date.replace(hour=hour, minute=minute, second=second)

    # ----- main simulation loop -----

    def run(self) -> List[Dict[str, Any]]:
        """Run the full simulation. Returns the trade log."""
        trading_days = get_trading_days(self.md)

        if self.verbose:
            print(f"\n=== Simulating trader #{self.p['trader_id']} ===")
            print(f"  Account: ${self.cash:,.2f} | "
                  f"Sector: {self.p['job_sector']} | "
                  f"Time: {self.p['time_availability']} | "
                  f"Experience: {self.p['experience_years']}yr")
            print(f"  Watchlist: {self.p['core_watchlist']}")

        base_trade_prob = TIME_AVAILABILITY_PROBS[self.p["time_availability"]]

        for day_idx, date in enumerate(trading_days):
            # --- Life events ---
            if self._is_vacation(day_idx):
                continue

            # Bonus deposit
            if day_idx in self.bonus_days:
                bump = self.cash * self.bonus_days[day_idx]
                self.cash += bump
                self.initial_cash += bump
                if self.verbose:
                    print(f"  Day {day_idx} ({date.date()}): BONUS DEPOSIT +${bump:,.2f}")

            # Skip day? (time availability + burnout)
            active_prob = base_trade_prob
            if self._is_burnout(day_idx):
                active_prob *= 0.15
            freq_mult = STATE_MULTIPLIERS[self.emotional_state][0]
            active_prob *= freq_mult

            if self.rng.random() > active_prob:
                # Still check option expiry even on inactive days
                self._check_option_expiry(date)
                continue

            # --- Tax loss harvesting in December ---
            dt = date.to_pydatetime() if hasattr(date, "to_pydatetime") else date
            if dt.month == 12 and dt.year in self.tax_loss_years:
                if dt.day >= 15 and self.rng.random() < 0.3:
                    self._tax_loss_harvest(date)

            # --- Update emotional state ---
            dd = self._drawdown(date)
            last_pnl_pct = 0.0
            if self.recent_pnl:
                last_pnl_pct = self.recent_pnl[-1] / max(1, self.initial_cash)
            self.emotional_state = _update_emotional_state(
                self.emotional_state, self.consec_wins, self.consec_losses,
                dd, last_pnl_pct, self.p, self.rng,
            )

            # Confidence spiral
            if self.consec_wins >= 5 and not self._spiral_active:
                self._spiral_active = True
                self._spiral_end_day = day_idx + self.rng.randint(10, 20)
            if self._spiral_active and day_idx >= self._spiral_end_day:
                self._spiral_active = False
                self.emotional_state = "neutral"

            # --- Check option expiry ---
            self._check_option_expiry(date)

            # --- Scan signals and decide ---
            signals = self._scan_signals(date)
            self.rng.shuffle(signals)
            # Process up to a few signals per day
            max_actions = self.rng.randint(1, 3)
            actions_taken = 0
            for sig in signals:
                if actions_taken >= max_actions:
                    break
                prev_count = len(self.trades)
                self._decide_on_signal(sig, date, day_idx)
                if len(self.trades) > prev_count:
                    actions_taken += 1

            # --- FOMO event? ---
            if day_idx in self.fomo_days:
                self._maybe_fomo_trade(date, day_idx)

            # --- Random sell ---
            self._maybe_random_sell(date)

            # --- ETF flight to safety ---
            self._maybe_etf_flight(date)

            # --- Options ---
            self._maybe_option_trade(date)

            # --- Update peak ---
            self._update_peak(date)

        # --- End of simulation: close all remaining positions ---
        if trading_days is not None and len(trading_days) > 0:
            last_day = trading_days[-1]
            for ticker in list(self.positions.keys()):
                if self.positions[ticker] > 0:
                    self._sell(ticker, last_day, fraction=1.0, order_type="Market")
            # Expire remaining options
            self._check_option_expiry(last_day + pd.Timedelta(days=1))

        if self.verbose:
            print(f"  Total trades: {len(self.trades)} | "
                  f"Final cash: ${self.cash:,.2f}")

        return self.trades


def simulate_trader(personality: Dict[str, Any],
                    market_data: Dict[str, pd.DataFrame],
                    seed: int, verbose: bool = False) -> List[Dict[str, Any]]:
    """Convenience wrapper: simulate a single trader and return trades."""
    rng = random.Random(seed + personality["trader_id"])
    sim = TraderSimulator(personality, market_data, rng, verbose=verbose)
    return sim.run()
