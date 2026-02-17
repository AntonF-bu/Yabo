"""Timing analysis: holding periods, entry classification, day-of-week patterns."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

logger = logging.getLogger(__name__)


def compute_round_trips(trades_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Match buys to sells (FIFO) and compute round-trip metrics.

    Returns list of dicts with keys:
        ticker, entry_date, exit_date, entry_price, exit_price,
        quantity, hold_days, pnl, pnl_pct
    """
    trips: list[dict[str, Any]] = []
    # Per-ticker FIFO queue
    open_lots: dict[str, list[dict]] = {}

    for _, row in trades_df.iterrows():
        ticker = row["ticker"]
        action = str(row["action"]).upper()
        qty = int(row["quantity"])
        price = float(row["price"])
        date = pd.Timestamp(row["date"])

        if action == "BUY":
            open_lots.setdefault(ticker, []).append({
                "date": date, "price": price, "qty": qty,
            })
        elif action == "SELL":
            lots = open_lots.get(ticker, [])
            remaining = qty
            while remaining > 0 and lots:
                lot = lots[0]
                matched = min(remaining, lot["qty"])
                hold_days = (date - lot["date"]).days
                pnl = (price - lot["price"]) * matched
                pnl_pct = (price - lot["price"]) / lot["price"] if lot["price"] > 0 else 0.0

                trips.append({
                    "ticker": ticker,
                    "entry_date": lot["date"],
                    "exit_date": date,
                    "entry_price": lot["price"],
                    "exit_price": price,
                    "quantity": matched,
                    "hold_days": max(hold_days, 0),
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                })
                remaining -= matched
                lot["qty"] -= matched
                if lot["qty"] <= 0:
                    lots.pop(0)

    return trips


def holding_period_stats(trips: list[dict]) -> dict[str, Any]:
    """Compute holding period distribution statistics."""
    if not trips:
        return {
            "mean_days": 0.0, "median_days": 0.0, "std_days": 0.0,
            "distribution": {
                "intraday": 0.0, "1_5_days": 0.0, "5_20_days": 0.0,
                "20_90_days": 0.0, "90_365_days": 0.0, "365_plus_days": 0.0,
            },
        }

    days = [t["hold_days"] for t in trips]
    arr = np.array(days, dtype=float)
    n = len(arr)

    dist = {
        "intraday": float(np.sum(arr < 1) / n),
        "1_5_days": float(np.sum((arr >= 1) & (arr < 5)) / n),
        "5_20_days": float(np.sum((arr >= 5) & (arr < 20)) / n),
        "20_90_days": float(np.sum((arr >= 20) & (arr < 90)) / n),
        "90_365_days": float(np.sum((arr >= 90) & (arr < 365)) / n),
        "365_plus_days": float(np.sum(arr >= 365) / n),
    }

    return {
        "mean_days": round(float(np.mean(arr)), 2),
        "median_days": round(float(np.median(arr)), 2),
        "std_days": round(float(np.std(arr)), 2),
        "distribution": {k: round(v, 4) for k, v in dist.items()},
    }


def entry_classification(trades_df: pd.DataFrame,
                         market_data: pd.DataFrame | None) -> dict[str, Any]:
    """Classify buy entries by market conditions at time of trade."""
    buys = trades_df[trades_df["action"].str.upper() == "BUY"].copy()
    if buys.empty or market_data is None:
        return {
            "breakout_pct": 0.0, "dip_buy_pct": 0.0,
            "earnings_proximity_pct": 0.0, "dca_pattern_detected": False,
            "dca_soft_detected": False,
            "dca_interval_cv": None, "dca_interval_mean_days": None,
            "preferred_day_of_week": None,
            "pct_above_ma20": 0.5, "pct_below_ma20": 0.5,
            "avg_entry_ma20_deviation": 0.0, "avg_rsi_at_entry": 50.0,
            "avg_vol_ratio_at_entry": 1.0,
        }

    n_buys = len(buys)
    breakout_count = 0
    dip_buy_count = 0
    earnings_count = 0
    above_ma_count = 0
    below_ma_count = 0
    rsi_values: list[float] = []
    ma_deviations: list[float] = []
    vol_ratios_at_entry: list[float] = []

    from generator.market_data import get_earnings_dates, _approximate_earnings_dates

    # Pre-compute earnings dates if market data available
    earnings_dates: dict[str, list[pd.Timestamp]] = {}
    if market_data is not None:
        try:
            earnings_dates = get_earnings_dates(market_data)
        except Exception:
            pass

    for _, row in buys.iterrows():
        ticker = row["ticker"]
        date = pd.Timestamp(row["date"])

        # Make date tz-aware if needed to match market_data index
        if date.tz is None and market_data.index.tz is not None:
            date = date.tz_localize("UTC")

        # Find matching row in market data
        idx = market_data.index.searchsorted(date)
        if idx >= len(market_data):
            continue
        mkt_row = market_data.iloc[idx]

        price = float(row["price"])
        ma20 = mkt_row.get(f"{ticker}_MA20")
        vol_ratio = mkt_row.get(f"{ticker}_VolRatio")
        high10 = mkt_row.get(f"{ticker}_High10")
        rsi = mkt_row.get(f"{ticker}_RSI")

        # Track MA-relative entry position
        if not pd.isna(ma20) and float(ma20) > 0:
            deviation = (price - float(ma20)) / float(ma20)
            ma_deviations.append(deviation)
            if price > float(ma20):
                above_ma_count += 1
            else:
                below_ma_count += 1

        # Track RSI at entry
        if not pd.isna(rsi):
            rsi_values.append(float(rsi))

        # Track volume ratio at entry
        if not pd.isna(vol_ratio):
            vol_ratios_at_entry.append(float(vol_ratio))

        # Breakout: price > MA20 and volume above average
        if not pd.isna(ma20) and not pd.isna(vol_ratio):
            if price > float(ma20) and float(vol_ratio) > 1.2:
                breakout_count += 1

        # Dip buy: price dropped from 10-day high, RSI low
        if not pd.isna(high10) and not pd.isna(rsi) and float(high10) > 0:
            drop = (float(high10) - price) / float(high10)
            if drop > 0.03 and float(rsi) < 40:
                dip_buy_count += 1

        # Earnings proximity
        edates = earnings_dates.get(ticker, [])
        for ed in edates:
            diff = abs((ed - date).days)
            if diff <= 5:
                earnings_count += 1
                break

    # DCA detection: two-tier approach + per-ticker analysis
    # IMPORTANT: DCA is a LOW-frequency, regular buying pattern.
    # High-frequency traders (>8/mo) naturally have regular intervals but are NOT DCA.
    buy_dates = pd.to_datetime(buys["date"])
    dca_detected = False
    dca_soft_detected = False
    dca_interval_cv: float | None = None
    dca_interval_mean: float | None = None

    n_days_range = max((buy_dates.max() - buy_dates.min()).days, 1) if len(buy_dates) > 1 else 1
    buys_per_month = len(buy_dates) / max(n_days_range / 30.0, 0.1)

    # Only check DCA for low-frequency traders (< 8 buys/month)
    if len(buy_dates) >= 4 and buys_per_month < 8:
        intervals = buy_dates.sort_values().diff().dropna().dt.days
        if len(intervals) > 3:
            int_mean = float(intervals.mean()) if intervals.mean() > 0 else 0
            int_std = float(intervals.std())
            cv = int_std / int_mean if int_mean > 0 else 999.0
            dca_interval_cv = round(cv, 4)
            dca_interval_mean = round(int_mean, 2)
            if cv < 0.40 and int_mean > 10:
                dca_detected = True
            elif cv < 0.60 and int_mean > 7:
                dca_soft_detected = True

    # Per-ticker DCA detection (only for low-moderate freq)
    if not dca_detected and buys_per_month < 10:
        ticker_groups = buys.groupby("ticker")
        for ticker, group in ticker_groups:
            if len(group) >= 3:
                t_dates = pd.to_datetime(group["date"]).sort_values()
                t_intervals = t_dates.diff().dropna().dt.days
                if len(t_intervals) >= 2:
                    t_mean = float(t_intervals.mean())
                    t_std = float(t_intervals.std())
                    t_cv = t_std / t_mean if t_mean > 0 else 999.0
                    if t_cv < 0.40 and t_mean > 10:
                        dca_detected = True
                        break
                    elif t_cv < 0.60 and t_mean > 7:
                        dca_soft_detected = True

    # Day of week preference
    dow_counts = buy_dates.dt.dayofweek.value_counts()
    preferred_day = None
    if len(buy_dates) >= 10:
        expected = len(buy_dates) / 5.0
        chi2, p_value = sp_stats.chisquare(
            dow_counts.reindex(range(5), fill_value=0).values,
            f_exp=[expected] * 5,
        )
        if p_value < 0.05:
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            preferred_day = day_names[dow_counts.index[0]]

    n_with_ma = above_ma_count + below_ma_count

    return {
        "breakout_pct": round(breakout_count / n_buys, 4) if n_buys > 0 else 0.0,
        "dip_buy_pct": round(dip_buy_count / n_buys, 4) if n_buys > 0 else 0.0,
        "earnings_proximity_pct": round(earnings_count / n_buys, 4) if n_buys > 0 else 0.0,
        "dca_pattern_detected": dca_detected,
        "dca_soft_detected": dca_soft_detected,
        "dca_interval_cv": dca_interval_cv,
        "dca_interval_mean_days": dca_interval_mean,
        "preferred_day_of_week": preferred_day,
        # MA-relative features for momentum vs mean_reversion discrimination
        "pct_above_ma20": round(above_ma_count / n_with_ma, 4) if n_with_ma > 0 else 0.5,
        "pct_below_ma20": round(below_ma_count / n_with_ma, 4) if n_with_ma > 0 else 0.5,
        "avg_entry_ma20_deviation": round(float(np.mean(ma_deviations)), 4) if ma_deviations else 0.0,
        "avg_rsi_at_entry": round(float(np.mean(rsi_values)), 2) if rsi_values else 50.0,
        "avg_vol_ratio_at_entry": round(float(np.mean(vol_ratios_at_entry)), 4) if vol_ratios_at_entry else 1.0,
    }


def inter_trade_timing(trades_df: pd.DataFrame, trips: list[dict]) -> dict[str, float]:
    """Analyze timing between trades for clustering (revenge trading) and gaps."""
    all_dates = pd.to_datetime(trades_df["date"]).sort_values()
    if len(all_dates) < 3:
        return {"post_loss_frequency_change": 0.0}

    intervals = all_dates.diff().dropna().dt.days.values

    # Look at timing after losses vs after wins
    losing_trips = [t for t in trips if t["pnl"] < 0]
    winning_trips = [t for t in trips if t["pnl"] >= 0]

    post_loss_intervals: list[float] = []
    post_win_intervals: list[float] = []

    trade_dates_list = all_dates.tolist()

    for trip in losing_trips:
        exit_date = trip["exit_date"]
        # Find next trade after this exit
        for td in trade_dates_list:
            diff = (td - exit_date).days
            if diff > 0:
                post_loss_intervals.append(diff)
                break

    for trip in winning_trips:
        exit_date = trip["exit_date"]
        for td in trade_dates_list:
            diff = (td - exit_date).days
            if diff > 0:
                post_win_intervals.append(diff)
                break

    avg_post_loss = np.mean(post_loss_intervals) if post_loss_intervals else 0
    avg_post_win = np.mean(post_win_intervals) if post_win_intervals else 0

    if avg_post_win > 0:
        freq_change = (avg_post_win - avg_post_loss) / avg_post_win
    else:
        freq_change = 0.0

    return {"post_loss_frequency_change": round(float(freq_change), 4)}
