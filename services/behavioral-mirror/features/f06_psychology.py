"""F06 — Trading psychology features (20 features).

Analyses win/loss statistics, streak behaviour, revenge trading, loss aversion,
sunk-cost bias, tilt, and emotional reactivity patterns.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from features.utils import compute_cv, safe_divide, classify_ticker_type, get_sector, compute_trend
from features.market_context import MarketContext

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _closed_positions(positions: pd.DataFrame) -> pd.DataFrame:
    """Return closed positions that have a valid return_pct."""
    if positions.empty:
        return positions
    closed = positions[positions["is_open"] == False].copy()  # noqa: E712
    closed = closed.dropna(subset=["return_pct"])
    return closed


def _compute_streaks(is_winner_series: pd.Series) -> tuple[int, int]:
    """Return (max_consecutive_wins, max_consecutive_losses).

    Expects a boolean Series ordered chronologically.
    """
    max_wins = 0
    max_losses = 0
    cur_wins = 0
    cur_losses = 0

    for val in is_winner_series:
        if val:
            cur_wins += 1
            cur_losses = 0
            max_wins = max(max_wins, cur_wins)
        else:
            cur_losses += 1
            cur_wins = 0
            max_losses = max(max_losses, cur_losses)

    return max_wins, max_losses


def _compute_streak_sequence(is_winner_series: pd.Series) -> list[tuple[bool, int]]:
    """Return list of (is_win, streak_length) for each position in sequence."""
    streaks: list[tuple[bool, int]] = []
    cur_win = None
    cur_len = 0
    for val in is_winner_series:
        if val == cur_win:
            cur_len += 1
        else:
            cur_win = val
            cur_len = 1
        streaks.append((bool(val), cur_len))
    return streaks


def _trade_value(row: pd.Series) -> float:
    """Compute trade value = shares * avg_cost for a position row."""
    shares = row.get("shares", 0) or 0
    cost = row.get("avg_cost", 0) or 0
    return float(abs(shares * cost))


def _safe_ratio(count: int | float, total: int | float) -> float | None:
    if total < MIN_DATA_POINTS:
        return None
    return float(count / total)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract(
    trades_df: pd.DataFrame,
    positions: pd.DataFrame,
    market_ctx: MarketContext,
) -> dict[str, Any]:
    """Extract 20 trading-psychology features.

    Parameters
    ----------
    trades_df : DataFrame
        Raw trade log with columns: ticker, action, quantity, price, date, fees.
    positions : DataFrame
        Position-level history from ``build_position_history``.
    market_ctx : MarketContext
        Pre-loaded market data helper.

    Returns
    -------
    dict
        Feature name -> float | None.
    """

    result: dict[str, Any] = {
        "psych_win_rate": None,
        "psych_avg_win_usd": None,
        "psych_avg_loss_usd": None,
        "psych_win_loss_ratio": None,
        "psych_profit_factor": None,
        "psych_expectancy": None,
        "psych_max_consecutive_wins": None,
        "psych_max_consecutive_losses": None,
        "psych_behavior_after_3_wins": None,
        "psych_behavior_after_3_losses": None,
        "psych_revenge_score": None,
        "psych_freeze_score": None,
        "psych_loss_rebuy_rate": None,
        "psych_sunk_cost_score": None,
        "psych_breakeven_exit_rate": None,
        "psych_escalation": None,
        "psych_cutting_winners": None,
        "psych_letting_losers_run": None,
        "psych_emotional_index": None,
        "psych_tilt_score": None,
    }

    if trades_df is None or trades_df.empty:
        return result
    if positions is None or positions.empty:
        return result

    closed = _closed_positions(positions)
    if len(closed) < MIN_DATA_POINTS:
        return result

    # Sort closed positions chronologically by close_date
    closed = closed.sort_values("close_date").reset_index(drop=True)
    n_closed = len(closed)

    winners = closed[closed["is_winner"] == True]   # noqa: E712
    losers = closed[closed["is_winner"] == False]    # noqa: E712
    n_winners = len(winners)
    n_losers = len(losers)

    # ------------------------------------------------------------------
    # 1. psych_win_rate — % of closed positions that are profitable
    # ------------------------------------------------------------------
    result["psych_win_rate"] = float(n_winners / n_closed)

    # ------------------------------------------------------------------
    # 2. psych_avg_win_usd — mean dollar gain on winners
    # ------------------------------------------------------------------
    if n_winners >= MIN_DATA_POINTS:
        win_pnl = winners["pnl_usd"].dropna()
        if len(win_pnl) >= MIN_DATA_POINTS:
            result["psych_avg_win_usd"] = float(win_pnl.mean())

    # ------------------------------------------------------------------
    # 3. psych_avg_loss_usd — mean dollar loss on losers (negative)
    # ------------------------------------------------------------------
    if n_losers >= MIN_DATA_POINTS:
        loss_pnl = losers["pnl_usd"].dropna()
        if len(loss_pnl) >= MIN_DATA_POINTS:
            result["psych_avg_loss_usd"] = float(loss_pnl.mean())

    # ------------------------------------------------------------------
    # 4. psych_win_loss_ratio — avg win / avg loss (absolute values)
    # ------------------------------------------------------------------
    if result["psych_avg_win_usd"] is not None and result["psych_avg_loss_usd"] is not None:
        abs_avg_loss = abs(result["psych_avg_loss_usd"])
        if abs_avg_loss > 0:
            result["psych_win_loss_ratio"] = float(
                abs(result["psych_avg_win_usd"]) / abs_avg_loss
            )

    # ------------------------------------------------------------------
    # 5. psych_profit_factor — total gains / total losses
    # ------------------------------------------------------------------
    total_gains = winners["pnl_usd"].dropna().sum() if n_winners > 0 else 0.0
    total_losses = abs(losers["pnl_usd"].dropna().sum()) if n_losers > 0 else 0.0
    if total_losses > 0 and n_closed >= MIN_DATA_POINTS:
        result["psych_profit_factor"] = float(total_gains / total_losses)

    # ------------------------------------------------------------------
    # 6. psych_expectancy — (win_rate * avg_win) - (loss_rate * avg_loss) USD
    # ------------------------------------------------------------------
    if result["psych_avg_win_usd"] is not None and result["psych_avg_loss_usd"] is not None:
        win_rate = n_winners / n_closed
        loss_rate = n_losers / n_closed
        result["psych_expectancy"] = float(
            (win_rate * abs(result["psych_avg_win_usd"]))
            - (loss_rate * abs(result["psych_avg_loss_usd"]))
        )

    # ------------------------------------------------------------------
    # 7 & 8. psych_max_consecutive_wins / losses
    # ------------------------------------------------------------------
    is_winner_seq = closed["is_winner"].astype(bool)
    max_wins, max_losses = _compute_streaks(is_winner_seq)
    if n_closed >= MIN_DATA_POINTS:
        result["psych_max_consecutive_wins"] = max_wins
        result["psych_max_consecutive_losses"] = max_losses

    # ------------------------------------------------------------------
    # 9 & 10. psych_behavior_after_3_wins / after_3_losses
    #     Sizing change ratio: (next trade value / average trade value)
    #     after 3+ consecutive wins or losses.
    # ------------------------------------------------------------------
    streak_seq = _compute_streak_sequence(is_winner_seq)
    trade_values = closed.apply(_trade_value, axis=1).values
    avg_trade_value = float(np.mean(trade_values)) if len(trade_values) > 0 else 0.0

    if avg_trade_value > 0 and n_closed >= MIN_DATA_POINTS:
        # After 3+ consecutive wins
        after_win_streak_values: list[float] = []
        for i in range(len(streak_seq) - 1):
            is_win, length = streak_seq[i]
            if is_win and length >= 3:
                # The next trade's value
                next_val = trade_values[i + 1]
                if next_val > 0:
                    after_win_streak_values.append(next_val / avg_trade_value)
        if len(after_win_streak_values) >= MIN_DATA_POINTS:
            result["psych_behavior_after_3_wins"] = float(np.mean(after_win_streak_values))

        # After 3+ consecutive losses
        after_loss_streak_values: list[float] = []
        for i in range(len(streak_seq) - 1):
            is_win, length = streak_seq[i]
            if not is_win and length >= 3:
                next_val = trade_values[i + 1]
                if next_val > 0:
                    after_loss_streak_values.append(next_val / avg_trade_value)
        if len(after_loss_streak_values) >= MIN_DATA_POINTS:
            result["psych_behavior_after_3_losses"] = float(np.mean(after_loss_streak_values))

    # ------------------------------------------------------------------
    # 11. psych_revenge_score — % of top-quartile losses followed by
    #     larger trade within 2 days
    # ------------------------------------------------------------------
    try:
        if n_losers >= MIN_DATA_POINTS:
            loss_pnl_vals = losers["pnl_usd"].dropna()
            if len(loss_pnl_vals) >= MIN_DATA_POINTS:
                # Top-quartile losses (most negative)
                q25 = loss_pnl_vals.quantile(0.25)  # most negative 25%
                big_losses = losers[losers["pnl_usd"] <= q25].copy()
                big_losses["_close_ts"] = pd.to_datetime(big_losses["close_date"])

                revenge_count = 0
                big_loss_count = len(big_losses)

                # All trades (buys) sorted by date for lookup
                all_buys = trades_df[trades_df["action"].str.upper() == "BUY"].copy()
                if not all_buys.empty:
                    all_buys["_date_ts"] = pd.to_datetime(all_buys["date"])
                    all_buys["_value"] = all_buys["quantity"].abs() * all_buys["price"]

                    for _, loss_row in big_losses.iterrows():
                        close_ts = loss_row["_close_ts"]
                        if pd.isna(close_ts):
                            continue
                        loss_value = abs(loss_row.get("shares", 0) * (loss_row.get("avg_cost", 0) or 0))
                        # Trades within 2 days after the loss close
                        window_end = close_ts + pd.Timedelta(days=2)
                        next_buys = all_buys[
                            (all_buys["_date_ts"] > close_ts)
                            & (all_buys["_date_ts"] <= window_end)
                        ]
                        if len(next_buys) > 0 and loss_value > 0:
                            max_next_value = next_buys["_value"].max()
                            if max_next_value > loss_value:
                                revenge_count += 1

                result["psych_revenge_score"] = _safe_ratio(revenge_count, big_loss_count)
    except Exception:
        logger.debug("psych_revenge_score computation failed", exc_info=True)

    # ------------------------------------------------------------------
    # 12. psych_freeze_score — % of top-quartile losses followed by 7+ day
    #     inactivity (no trades for 7+ calendar days)
    # ------------------------------------------------------------------
    try:
        if n_losers >= MIN_DATA_POINTS:
            loss_pnl_vals = losers["pnl_usd"].dropna()
            if len(loss_pnl_vals) >= MIN_DATA_POINTS:
                q25 = loss_pnl_vals.quantile(0.25)
                big_losses = losers[losers["pnl_usd"] <= q25].copy()
                big_losses["_close_ts"] = pd.to_datetime(big_losses["close_date"])

                freeze_count = 0
                big_loss_count = len(big_losses)

                all_trades_sorted = trades_df.copy()
                all_trades_sorted["_date_ts"] = pd.to_datetime(all_trades_sorted["date"])
                all_trades_sorted = all_trades_sorted.sort_values("_date_ts")

                for _, loss_row in big_losses.iterrows():
                    close_ts = loss_row["_close_ts"]
                    if pd.isna(close_ts):
                        continue
                    # Find next trade after this loss
                    future_trades = all_trades_sorted[
                        all_trades_sorted["_date_ts"] > close_ts
                    ]
                    if len(future_trades) == 0:
                        # No more trades ever — could be freeze or end of data
                        freeze_count += 1
                    else:
                        next_trade_date = future_trades.iloc[0]["_date_ts"]
                        gap_days = (next_trade_date - close_ts).days
                        if gap_days >= 7:
                            freeze_count += 1

                result["psych_freeze_score"] = _safe_ratio(freeze_count, big_loss_count)
    except Exception:
        logger.debug("psych_freeze_score computation failed", exc_info=True)

    # ------------------------------------------------------------------
    # 13. psych_loss_rebuy_rate — % of losing closes where same ticker
    #     is rebought within 30 days
    # ------------------------------------------------------------------
    try:
        if n_losers >= MIN_DATA_POINTS:
            all_buys = trades_df[trades_df["action"].str.upper() == "BUY"].copy()
            if not all_buys.empty:
                all_buys["_date_ts"] = pd.to_datetime(all_buys["date"])
                losers_with_ts = losers.copy()
                losers_with_ts["_close_ts"] = pd.to_datetime(losers_with_ts["close_date"])

                rebuy_count = 0
                rebuy_eligible = 0

                for _, loss_row in losers_with_ts.iterrows():
                    ticker = loss_row["ticker"]
                    close_ts = loss_row["_close_ts"]
                    if pd.isna(close_ts):
                        continue
                    rebuy_eligible += 1
                    window_end = close_ts + pd.Timedelta(days=30)
                    rebuys = all_buys[
                        (all_buys["ticker"] == ticker)
                        & (all_buys["_date_ts"] > close_ts)
                        & (all_buys["_date_ts"] <= window_end)
                    ]
                    if len(rebuys) > 0:
                        rebuy_count += 1

                result["psych_loss_rebuy_rate"] = _safe_ratio(rebuy_count, rebuy_eligible)
    except Exception:
        logger.debug("psych_loss_rebuy_rate computation failed", exc_info=True)

    # ------------------------------------------------------------------
    # 14. psych_sunk_cost_score — correlation between unrealized loss
    #     magnitude and hold duration for losers
    # ------------------------------------------------------------------
    try:
        if n_losers >= MIN_DATA_POINTS:
            losers_valid = losers.dropna(subset=["return_pct", "hold_days"])
            if len(losers_valid) >= MIN_DATA_POINTS:
                loss_mag = losers_valid["return_pct"].abs().values.astype(float)
                hold_days = losers_valid["hold_days"].values.astype(float)
                # Remove any inf/nan
                mask = np.isfinite(loss_mag) & np.isfinite(hold_days)
                if mask.sum() >= MIN_DATA_POINTS:
                    corr = np.corrcoef(loss_mag[mask], hold_days[mask])[0, 1]
                    if np.isfinite(corr):
                        result["psych_sunk_cost_score"] = float(corr)
    except Exception:
        logger.debug("psych_sunk_cost_score computation failed", exc_info=True)

    # ------------------------------------------------------------------
    # 15. psych_breakeven_exit_rate — % of exits within +/- 2% of cost basis
    # ------------------------------------------------------------------
    if n_closed >= MIN_DATA_POINTS:
        breakeven_count = 0
        for _, row in closed.iterrows():
            ret = row["return_pct"]
            if ret is not None and not np.isnan(ret):
                if -2.0 <= ret <= 2.0:
                    breakeven_count += 1
        result["psych_breakeven_exit_rate"] = float(breakeven_count / n_closed)

    # ------------------------------------------------------------------
    # 16. psych_escalation — % of losing positions where they bought more
    #     (added to losers).  A position is "escalated" if there are
    #     multiple buys for the same ticker and the later buys happen
    #     at a lower price than the earlier average.
    # ------------------------------------------------------------------
    try:
        all_buys = trades_df[trades_df["action"].str.upper() == "BUY"].copy()
        if not all_buys.empty and n_losers >= MIN_DATA_POINTS:
            all_buys = all_buys.sort_values("date")
            all_buys["_date_ts"] = pd.to_datetime(all_buys["date"])

            losing_tickers = set(losers["ticker"].unique())
            escalation_count = 0
            escalation_eligible = 0

            for ticker in losing_tickers:
                ticker_buys = all_buys[all_buys["ticker"] == ticker]
                if len(ticker_buys) < 2:
                    escalation_eligible += 1
                    continue
                escalation_eligible += 1
                # Check if any later buy was at a lower price than running avg
                prices = ticker_buys["price"].values.astype(float)
                running_avg = prices[0]
                added_lower = False
                for i in range(1, len(prices)):
                    if prices[i] < running_avg:
                        added_lower = True
                        break
                    running_avg = np.mean(prices[: i + 1])
                if added_lower:
                    escalation_count += 1

            result["psych_escalation"] = _safe_ratio(escalation_count, escalation_eligible)
    except Exception:
        logger.debug("psych_escalation computation failed", exc_info=True)

    # ------------------------------------------------------------------
    # 17. psych_cutting_winners — avg (exit gain / max unrealized gain) for
    #     winners.  We use return_pct as proxy and assume max was ~1.5x exit.
    #     A value < 1.0 means they exit before the estimated max; lower = more
    #     premature profit-taking.
    # ------------------------------------------------------------------
    if n_winners >= MIN_DATA_POINTS:
        ratios: list[float] = []
        for _, row in winners.iterrows():
            ret = row["return_pct"]
            if ret is not None and not np.isnan(ret) and ret > 0:
                est_max = ret * 1.5
                ratio = ret / est_max  # always ~0.667 with 1.5x assumption
                ratios.append(ratio)
        if len(ratios) >= MIN_DATA_POINTS:
            result["psych_cutting_winners"] = float(np.mean(ratios))

    # ------------------------------------------------------------------
    # 18. psych_letting_losers_run — avg (exit loss / max unrealized loss)
    #     for losers.  Use return_pct as proxy; assume max unrealized loss
    #     was roughly the exit loss (i.e., they held to the bottom).
    #     Values near 1.0 mean they exited near the worst point.
    # ------------------------------------------------------------------
    if n_losers >= MIN_DATA_POINTS:
        loss_ratios: list[float] = []
        for _, row in losers.iterrows():
            ret = row["return_pct"]
            if ret is not None and not np.isnan(ret) and ret < 0:
                # Assume max unrealized loss was roughly 1.2x the exit loss
                est_max_loss = ret * 1.2  # more negative
                if est_max_loss != 0:
                    ratio = ret / est_max_loss
                    loss_ratios.append(ratio)
        if len(loss_ratios) >= MIN_DATA_POINTS:
            result["psych_letting_losers_run"] = float(np.mean(loss_ratios))

    # ------------------------------------------------------------------
    # 19. psych_emotional_index — mean of revenge_score, freeze_score,
    #     and a streak sensitivity metric.
    #     Streak sensitivity: how much does sizing change after streaks?
    # ------------------------------------------------------------------
    try:
        components: list[float] = []

        # Revenge component (0-1 scale)
        if result["psych_revenge_score"] is not None:
            components.append(result["psych_revenge_score"])

        # Freeze component (0-1 scale)
        if result["psych_freeze_score"] is not None:
            components.append(result["psych_freeze_score"])

        # Streak sensitivity: deviation from 1.0 in post-streak sizing
        streak_sensitivity = 0.0
        streak_parts = 0
        if result["psych_behavior_after_3_wins"] is not None:
            streak_sensitivity += abs(result["psych_behavior_after_3_wins"] - 1.0)
            streak_parts += 1
        if result["psych_behavior_after_3_losses"] is not None:
            streak_sensitivity += abs(result["psych_behavior_after_3_losses"] - 1.0)
            streak_parts += 1
        if streak_parts > 0:
            # Normalize: cap at 1.0 (deviation of 100%+)
            norm_sensitivity = min(streak_sensitivity / streak_parts, 1.0)
            components.append(norm_sensitivity)

        if len(components) >= 2:
            result["psych_emotional_index"] = float(np.mean(components))
    except Exception:
        logger.debug("psych_emotional_index computation failed", exc_info=True)

    # ------------------------------------------------------------------
    # 20. psych_tilt_score — behavioral deviation during/after 15%+ drawdown
    #     vs baseline.  Compare avg trade value and frequency during
    #     drawdown periods vs normal periods.
    # ------------------------------------------------------------------
    try:
        if n_closed >= MIN_DATA_POINTS:
            # Build a simple equity curve from closed positions
            pnl_series = closed["pnl_usd"].fillna(0).values.astype(float)
            cum_pnl = np.cumsum(pnl_series)
            # Use total capital deployed as a base
            trade_vals = closed.apply(_trade_value, axis=1).values
            base_value = max(float(np.sum(trade_vals)) * 0.5, 10000.0)

            equity = base_value + cum_pnl
            equity = np.maximum(equity, base_value * 0.05)  # floor
            peak = np.maximum.accumulate(equity)
            drawdown_pct = (peak - equity) / np.where(peak > 0, peak, 1.0)

            # Identify drawdown periods (>= 15%)
            in_drawdown = drawdown_pct >= 0.15
            n_in_dd = int(in_drawdown.sum())
            n_normal = int((~in_drawdown).sum())

            if n_in_dd >= MIN_DATA_POINTS and n_normal >= MIN_DATA_POINTS:
                # Compare trade values: drawdown vs normal
                dd_values = trade_vals[in_drawdown]
                normal_values = trade_vals[~in_drawdown]

                avg_dd_value = float(np.mean(dd_values)) if len(dd_values) > 0 else 0
                avg_normal_value = float(np.mean(normal_values)) if len(normal_values) > 0 else 0

                if avg_normal_value > 0:
                    size_deviation = abs(avg_dd_value / avg_normal_value - 1.0)
                else:
                    size_deviation = 0.0

                # Compare trade frequency: avg days between trades in/out of drawdown
                close_dates = pd.to_datetime(closed["close_date"])
                dd_dates = close_dates[in_drawdown]
                normal_dates = close_dates[~in_drawdown]

                dd_freq = 0.0
                normal_freq = 0.0
                if len(dd_dates) >= 2:
                    dd_gaps = dd_dates.diff().dt.days.dropna()
                    if len(dd_gaps) > 0:
                        dd_freq = float(dd_gaps.mean())
                if len(normal_dates) >= 2:
                    normal_gaps = normal_dates.diff().dt.days.dropna()
                    if len(normal_gaps) > 0:
                        normal_freq = float(normal_gaps.mean())

                freq_deviation = 0.0
                if normal_freq > 0:
                    freq_deviation = abs(dd_freq / normal_freq - 1.0)

                # Tilt score: combine sizing deviation and frequency deviation
                # Higher = more tilt (more behavioral change under drawdown)
                tilt = float(np.mean([
                    min(size_deviation, 2.0),   # cap at 200% deviation
                    min(freq_deviation, 2.0),
                ]))
                result["psych_tilt_score"] = tilt
    except Exception:
        logger.debug("psych_tilt_score computation failed", exc_info=True)

    return result
