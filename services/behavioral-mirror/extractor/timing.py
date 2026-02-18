"""Timing analysis: holding periods, entry classification, day-of-week patterns."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

logger = logging.getLogger(__name__)


def classify_trades(trades_df: pd.DataFrame) -> dict[str, Any]:
    """Classify each trade before round-trip matching.

    A SELL with no prior BUY in the dataset is NOT a failed trade — it's an exit
    from a position that predates the data window (inherited position).

    Returns dict with:
        normal_trades: DataFrame of trades eligible for round-trip matching
        inherited_exits: list of dicts for sells with no matching buy inventory
        inventory: dict of remaining buy inventory per ticker
    """
    df = trades_df.sort_values("date").copy()

    # Track inventory per ticker: cumulative shares available from BUYs
    inventory: dict[str, float] = {}
    inherited_exits: list[dict[str, Any]] = []
    normal_indices: list[int] = []

    for idx, row in df.iterrows():
        ticker = str(row["ticker"]).upper().strip()
        action = str(row["action"]).upper()
        qty = float(row["quantity"])

        if ticker not in inventory:
            inventory[ticker] = 0.0

        if action == "BUY":
            inventory[ticker] += qty
            normal_indices.append(idx)
        elif action == "SELL":
            if inventory[ticker] >= qty - 1e-6:
                # Full inventory available from buys in this dataset
                inventory[ticker] -= qty
                normal_indices.append(idx)
            elif inventory[ticker] > 1e-6:
                # Partial: some shares from dataset, some inherited
                dataset_qty = inventory[ticker]
                inherited_qty = qty - dataset_qty
                inventory[ticker] = 0.0

                # The dataset portion stays as a normal trade
                normal_indices.append(idx)
                # But we record the inherited portion separately
                inherited_exits.append({
                    "ticker": ticker,
                    "date": pd.Timestamp(row["date"]),
                    "price": float(row["price"]),
                    "quantity": inherited_qty,
                    "total": float(row["price"]) * inherited_qty,
                    "side": "SELL",
                    "classification": "inherited_exit",
                    "note": f"Partial: {dataset_qty:.2f} matched, {inherited_qty:.2f} inherited",
                })
            else:
                # No inventory at all — entirely inherited
                inherited_exits.append({
                    "ticker": ticker,
                    "date": pd.Timestamp(row["date"]),
                    "price": float(row["price"]),
                    "quantity": qty,
                    "total": float(row["price"]) * qty,
                    "side": "SELL",
                    "classification": "inherited_exit",
                })

    normal_trades = df.loc[normal_indices]

    if inherited_exits:
        tickers = sorted(set(e["ticker"] for e in inherited_exits))
        logger.info(
            "Classified trades: %d normal, %d inherited exits (%s)",
            len(normal_trades), len(inherited_exits), ", ".join(tickers),
        )

    return {
        "normal_trades": normal_trades,
        "inherited_exits": inherited_exits,
        "inventory": inventory,
    }


def build_inherited_summary(inherited_exits: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize positions that were exited but entered before the data window.

    These tell us about the trader's LONGER-TERM holdings — what they held
    before this data window began.
    """
    if not inherited_exits:
        return {"count": 0, "tickers": [], "total_proceeds": 0.0, "note": None}

    tickers = sorted(set(e["ticker"] for e in inherited_exits))
    total_proceeds = sum(e["total"] for e in inherited_exits)

    # Group by sector (will be enriched by pipeline with resolved data)
    return {
        "count": len(inherited_exits),
        "tickers": tickers,
        "total_proceeds": round(total_proceeds, 2),
        "avg_exit_size": round(total_proceeds / len(inherited_exits), 2),
        "exits": inherited_exits,  # raw data for sector enrichment in pipeline
        "note": (
            f"{len(inherited_exits)} sells had no matching buy in the data window, "
            f"indicating positions entered before the start of the uploaded data. "
            f"These are excluded from win rate and profit factor calculations."
        ),
    }


def compute_data_completeness(
    closed_count: int,
    open_count: int,
    inherited_count: int,
    total_trades: int,
) -> dict[str, Any]:
    """Score how complete the trading history is.

    High inherited count = partial window (trader uploaded a slice, not full history).
    """
    total_meaningful = closed_count + open_count + inherited_count
    inherited_pct = inherited_count / max(total_meaningful, 1)

    if inherited_pct > 0.4:
        score = "partial"
        note = (
            f"This data appears to be a partial window of a longer trading history. "
            f"{inherited_count} position exits predate the data, suggesting these were "
            f"held before the upload window began. Performance metrics reflect only "
            f"{closed_count} fully-tracked round trips."
        )
    elif inherited_pct > 0.15:
        score = "mostly_complete"
        note = (
            f"Some positions ({inherited_count}) were exited without matching entries "
            f"in the data. Performance metrics are based on fully-tracked trades only."
        )
    else:
        score = "complete"
        note = None

    return {
        "score": score,
        "closed_round_trips": closed_count,
        "open_positions": open_count,
        "inherited_exits": inherited_count,
        "inherited_pct": round(inherited_pct, 3),
        "note": note,
    }


def compute_round_trips(
    trades_df: pd.DataFrame,
    as_of_date: pd.Timestamp | None = None,
) -> dict[str, Any]:
    """Match buys to sells (FIFO) and compute round-trip metrics.

    First classifies trades to detect inherited exits (sells with no matching
    buy in the dataset). Round trips are computed ONLY from normal trades.

    Args:
        trades_df: Normalized trades DataFrame.
        as_of_date: Reference date for open position age. Defaults to the
            last trade date in the data, making results deterministic.

    Returns dict with:
        closed: list of completed round-trip dicts
        open_positions: list of unmatched buy lots still held
        inherited: summary of inherited position exits
        data_completeness: data quality assessment
        total_trades, closed_count, open_count, open_pct
    """
    # Step 1: Classify trades — separate inherited exits
    classified = classify_trades(trades_df)
    normal_df = classified["normal_trades"]
    inherited_exits = classified["inherited_exits"]

    # Step 2: FIFO matching on normal trades only
    trips: list[dict[str, Any]] = []
    open_lots: dict[str, list[dict]] = {}

    total_buys = 0
    for _, row in normal_df.iterrows():
        ticker = row["ticker"]
        action = str(row["action"]).upper()
        qty = float(row["quantity"])
        price = float(row["price"])
        date = pd.Timestamp(row["date"])

        if action == "BUY":
            total_buys += 1
            open_lots.setdefault(ticker, []).append({
                "ticker": ticker, "date": date, "price": price, "qty": qty,
            })
        elif action == "SELL":
            lots = open_lots.get(ticker, [])
            remaining = qty
            while remaining > 1e-6 and lots:
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
                if lot["qty"] <= 1e-6:
                    lots.pop(0)

    # Collect open positions (unmatched buy lots)
    # Use as_of_date (last trade date) instead of wall-clock time for determinism
    if as_of_date is None:
        as_of_date = pd.Timestamp(normal_df["date"].max()) if not normal_df.empty else pd.Timestamp.now()
    if hasattr(as_of_date, "tz") and as_of_date.tz is not None:
        as_of_date = as_of_date.tz_localize(None)
    open_positions: list[dict[str, Any]] = []
    for ticker, lots in open_lots.items():
        for lot in lots:
            if lot["qty"] > 1e-6:
                entry_date = lot["date"]
                if hasattr(entry_date, "tz") and entry_date.tz is not None:
                    entry_date = entry_date.tz_localize(None)
                days = max((as_of_date - entry_date).days, 0)
                open_positions.append({
                    "ticker": ticker,
                    "entry_date": lot["date"],
                    "entry_price": lot["price"],
                    "quantity": lot["qty"],
                    "total_cost": lot["price"] * lot["qty"],
                    "days_held": days,
                })

    open_count = len(open_positions)
    closed_count = len(trips)
    inherited_count = len(inherited_exits)
    total_trades = len(trades_df)

    # Build summaries
    inherited_summary = build_inherited_summary(inherited_exits)
    data_completeness = compute_data_completeness(
        closed_count, open_count, inherited_count, total_trades,
    )

    logger.info(
        "Round trips: %d closed, %d open, %d inherited exits "
        "(data completeness: %s, %.0f%% inherited)",
        closed_count, open_count, inherited_count,
        data_completeness["score"], data_completeness["inherited_pct"] * 100,
    )

    return {
        "closed": trips,
        "open_positions": open_positions,
        "inherited": inherited_summary,
        "data_completeness": data_completeness,
        "total_trades": total_trades,
        "closed_count": closed_count,
        "open_count": open_count,
        "open_pct": round(open_count / max(total_buys, 1), 4),
    }


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
        if market_data is None:
            logger.warning("[MARKET DATA] No market data available — entry patterns will be flat")
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

    # Normalize market data index timezone for consistent lookups
    mkt_index = market_data.index
    if not isinstance(mkt_index, pd.DatetimeIndex):
        try:
            market_data.index = pd.to_datetime(mkt_index)
            mkt_index = market_data.index
        except Exception:
            logger.warning("[MARKET DATA] Index is not DatetimeIndex and cannot be converted")
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
    mkt_tz = mkt_index.tz

    # Log market data coverage for debugging
    logger.info(
        "[MARKET DATA] Entry classification: %d columns, %d rows, "
        "index tz=%s, range %s to %s",
        len(market_data.columns), len(market_data), mkt_tz,
        mkt_index.min(), mkt_index.max(),
    )

    n_matched = 0
    n_no_ticker_data = 0

    for _, row in buys.iterrows():
        ticker = row["ticker"]
        date = pd.Timestamp(row["date"])

        # Align timezone: make trade date match market data index
        if date.tz is None and mkt_tz is not None:
            date = date.tz_localize("UTC")
        elif date.tz is not None and mkt_tz is None:
            date = date.tz_localize(None)

        # Check if this ticker has ANY data in market_data
        ma20_col = f"{ticker}_MA20"
        if ma20_col not in market_data.columns:
            n_no_ticker_data += 1
            continue

        # Find matching row in market data (closest date on or before trade date)
        idx = mkt_index.searchsorted(date, side="right") - 1
        if idx < 0:
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
    # IMPORTANT: True DCA requires REPEATED BUYS OF THE SAME TICKER at
    # roughly regular intervals.  A trader who buys AAPL on June 2,
    # BA on June 9, META on June 15, GD on June 22 is stock-picking on
    # a regular schedule, NOT doing DCA, even though overall interval CV
    # is low.  Therefore the overall interval check can only flag
    # dca_soft_detected; hard dca_detected requires per-ticker evidence.
    buy_dates = pd.to_datetime(buys["date"])
    dca_detected = False
    dca_soft_detected = False
    dca_interval_cv: float | None = None
    dca_interval_mean: float | None = None

    n_days_range = max((buy_dates.max() - buy_dates.min()).days, 1) if len(buy_dates) > 1 else 1
    buys_per_month = len(buy_dates) / max(n_days_range / 30.0, 0.1)

    # Overall interval regularity — can only set SOFT, not hard
    if len(buy_dates) >= 4 and buys_per_month < 8:
        intervals = buy_dates.sort_values().diff().dropna().dt.days
        if len(intervals) > 3:
            int_mean = float(intervals.mean()) if intervals.mean() > 0 else 0
            int_std = float(intervals.std())
            cv = int_std / int_mean if int_mean > 0 else 999.0
            dca_interval_cv = round(cv, 4)
            dca_interval_mean = round(int_mean, 2)
            if cv < 0.60 and int_mean > 7:
                dca_soft_detected = True

    # Per-ticker DCA detection — the ONLY path to dca_detected = True.
    # At least one ticker must have 3+ buys at regular intervals.
    if buys_per_month < 10:
        ticker_groups = buys.groupby("ticker")
        for ticker, group in ticker_groups:
            if len(group) >= 3:
                t_dates = pd.to_datetime(group["date"]).sort_values()
                t_intervals = t_dates.diff().dropna().dt.days
                if len(t_intervals) >= 2:
                    t_mean = float(t_intervals.mean())
                    t_std = float(t_intervals.std())
                    t_cv = t_std / t_mean if t_mean > 0 else 999.0
                    if t_cv < 0.50 and t_mean > 7:
                        dca_detected = True
                        break
                    elif t_cv < 0.65 and t_mean > 7:
                        dca_soft_detected = True

    # Day of week preference (weekdays only: 0=Mon..4=Fri)
    weekday_buys = buy_dates[buy_dates.dt.dayofweek < 5]
    dow_counts = weekday_buys.dt.dayofweek.value_counts()
    preferred_day = None
    if len(weekday_buys) >= 10:
        observed = dow_counts.reindex(range(5), fill_value=0).values
        n_weekday = int(observed.sum())
        if n_weekday > 0:
            expected = n_weekday / 5.0
            chi2, p_value = sp_stats.chisquare(observed, f_exp=[expected] * 5)
            if p_value < 0.05:
                day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                top_day_idx = dow_counts.index[0]
                if top_day_idx < 5:
                    preferred_day = day_names[top_day_idx]

    n_with_ma = above_ma_count + below_ma_count

    # Log match statistics
    n_matched = n_with_ma  # trades where we could check MA20
    logger.info(
        "[MARKET DATA] Entry classification: %d/%d buys matched to market data "
        "(%d had no ticker data in market_data columns)",
        n_matched, n_buys, n_no_ticker_data,
    )

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
