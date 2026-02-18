"""Feature group 09 -- Portfolio-level construction & risk metrics.

Extracts 12 features describing how a trader's portfolio is *constructed*:
position counts, turnover, diversification, correlation, drawdown dynamics,
income/growth tilt, and estimated beta vs SPY.

All features are prefixed ``portfolio_``.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from features.utils import (
    classify_ticker_type,
    estimate_portfolio_value,
    is_growth,
    is_income,
    is_value,
    safe_divide,
)

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _concurrent_positions_series(positions: pd.DataFrame) -> pd.Series:
    """Build a daily Series of concurrent open-position counts.

    Uses open_date / close_date from the positions DataFrame.  Open positions
    (close_date is NaT) are treated as still open through the last known date.
    """
    rows: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    dates_seen: list[pd.Timestamp] = []

    for _, pos in positions.iterrows():
        od = pd.Timestamp(pos["open_date"]) if pd.notna(pos.get("open_date")) else pd.NaT
        cd = pd.Timestamp(pos["close_date"]) if pd.notna(pos.get("close_date")) else pd.NaT
        if pd.isna(od):
            continue
        dates_seen.append(od)
        if pd.notna(cd):
            dates_seen.append(cd)
        rows.append((od, cd))

    if not dates_seen:
        return pd.Series(dtype=float)

    min_date = min(dates_seen)
    max_date = max(dates_seen)
    date_range = pd.date_range(min_date, max_date, freq="D")

    counts = np.zeros(len(date_range), dtype=int)
    for od, cd in rows:
        end = cd if pd.notna(cd) else max_date
        mask = (date_range >= od) & (date_range <= end)
        counts[mask] += 1

    return pd.Series(counts, index=date_range)


def _holdings_weight_snapshots(
    positions: pd.DataFrame,
    trades_df: pd.DataFrame,
) -> list[dict[str, float]]:
    """Build monthly snapshots of ticker-weight dicts (by dollar value).

    Returns a list of dicts: [{ticker: weight, ...}, ...] one per month.
    """
    if positions.empty:
        return []

    dates_seen: list[pd.Timestamp] = []
    for _, pos in positions.iterrows():
        od = pd.Timestamp(pos["open_date"]) if pd.notna(pos.get("open_date")) else pd.NaT
        cd = pd.Timestamp(pos["close_date"]) if pd.notna(pos.get("close_date")) else pd.NaT
        if pd.notna(od):
            dates_seen.append(od)
        if pd.notna(cd):
            dates_seen.append(cd)

    if not dates_seen:
        return []

    min_date = min(dates_seen)
    max_date = max(dates_seen)
    months = pd.date_range(min_date, max_date, freq="ME")
    if len(months) == 0:
        months = pd.DatetimeIndex([max_date])

    # Build a quick last-price lookup from trades
    tdf = trades_df.copy()
    tdf["date"] = pd.to_datetime(tdf["date"], errors="coerce")
    tdf = tdf.dropna(subset=["date"]).sort_values("date")
    last_prices: dict[str, float] = {}
    for _, row in tdf.iterrows():
        last_prices[str(row["ticker"])] = float(row["price"])

    snapshots: list[dict[str, float]] = []
    for snap_date in months:
        holdings: dict[str, float] = {}  # ticker -> dollar value
        for _, pos in positions.iterrows():
            od = pd.Timestamp(pos["open_date"]) if pd.notna(pos.get("open_date")) else pd.NaT
            cd = pd.Timestamp(pos["close_date"]) if pd.notna(pos.get("close_date")) else pd.NaT
            if pd.isna(od) or od > snap_date:
                continue
            if pd.notna(cd) and cd < snap_date:
                continue
            ticker = str(pos["ticker"])
            shares = float(pos["shares"]) if pd.notna(pos.get("shares")) else 0.0
            # Use avg_cost as price proxy; fall back to last traded price
            price = float(pos["avg_cost"]) if pd.notna(pos.get("avg_cost")) and float(pos["avg_cost"]) > 0 else last_prices.get(ticker, 0.0)
            holdings[ticker] = holdings.get(ticker, 0.0) + shares * price

        total = sum(holdings.values())
        if total > 0:
            snapshots.append({t: v / total for t, v in holdings.items()})

    return snapshots


def _portfolio_daily_returns(
    portfolio_value: pd.Series,
) -> pd.Series:
    """Simple daily percentage returns from a portfolio value series."""
    pv = portfolio_value.sort_index()
    pv = pv[pv > 0]
    if len(pv) < 2:
        return pd.Series(dtype=float)
    return pv.pct_change().dropna()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract(
    trades_df: pd.DataFrame,
    positions: pd.DataFrame,
    market_ctx: Any,
) -> dict[str, Any]:
    """Return 12 portfolio-construction features.

    Parameters
    ----------
    trades_df : DataFrame
        Columns: ticker, action, quantity, price, date, fees.
    positions : DataFrame
        Columns: ticker, open_date, close_date, shares, avg_cost,
        close_price, hold_days, return_pct, pnl_usd, is_winner,
        is_partial_close, is_open.
    market_ctx : MarketContext
        Provides SPY price series for beta estimation.

    Returns
    -------
    dict -- keys are ``portfolio_*`` feature names.
    """
    result: dict[str, Any] = {
        "portfolio_avg_positions": None,
        "portfolio_max_positions": None,
        "portfolio_monthly_turnover": None,
        "portfolio_diversification": None,
        "portfolio_correlation": None,
        "portfolio_long_only": None,
        "portfolio_cash_avg_pct": None,
        "portfolio_max_drawdown": None,
        "portfolio_drawdown_recovery_days": None,
        "portfolio_income_component": None,
        "portfolio_growth_vs_value": None,
        "portfolio_beta_estimate": None,
    }

    if trades_df is None or trades_df.empty or len(trades_df) < MIN_DATA_POINTS:
        return result

    df = trades_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    if len(df) < MIN_DATA_POINTS:
        return result

    pos = positions if positions is not None and not positions.empty else pd.DataFrame()

    # ------------------------------------------------------------------
    # 1-2. portfolio_avg_positions, portfolio_max_positions
    # ------------------------------------------------------------------
    if not pos.empty:
        conc = _concurrent_positions_series(pos)
        if len(conc) >= MIN_DATA_POINTS:
            result["portfolio_avg_positions"] = float(round(conc.mean(), 2))
            result["portfolio_max_positions"] = int(conc.max())

    # ------------------------------------------------------------------
    # 3. portfolio_monthly_turnover (monthly value traded / portfolio value)
    # ------------------------------------------------------------------
    try:
        pv_series = estimate_portfolio_value(df)
    except Exception:
        pv_series = pd.Series(dtype=float)

    if len(pv_series) >= MIN_DATA_POINTS:
        df["_value"] = (df["price"].astype(float) * df["quantity"].astype(float)).abs()
        df["_month"] = df["date"].dt.to_period("M")
        monthly_traded = df.groupby("_month")["_value"].sum()

        # Resample portfolio value to monthly means
        pv_monthly = pv_series.resample("ME").mean()
        pv_monthly = pv_monthly[pv_monthly > 0]

        turnovers: list[float] = []
        for period, traded_val in monthly_traded.items():
            # Find matching month-end in pv_monthly
            month_end = period.to_timestamp(how="end")
            closest_idx = pv_monthly.index.searchsorted(month_end)
            if closest_idx > 0:
                idx = min(closest_idx, len(pv_monthly) - 1)
                pv_val = pv_monthly.iloc[idx]
                if pv_val > 0:
                    turnovers.append(float(traded_val) / pv_val)

        if len(turnovers) >= 2:
            result["portfolio_monthly_turnover"] = float(round(np.mean(turnovers), 4))

    # ------------------------------------------------------------------
    # 4. portfolio_diversification (1 - HHI of holdings snapshots)
    # ------------------------------------------------------------------
    snapshots = _holdings_weight_snapshots(pos, df) if not pos.empty else []
    if len(snapshots) >= MIN_DATA_POINTS:
        hhis: list[float] = []
        for snap in snapshots:
            weights = np.array(list(snap.values()))
            hhi = float(np.sum(weights ** 2))
            hhis.append(hhi)
        avg_hhi = np.mean(hhis)
        result["portfolio_diversification"] = float(round(1.0 - avg_hhi, 4))
    elif len(snapshots) >= 1:
        # Use whatever snapshots we have
        weights = np.array(list(snapshots[0].values()))
        hhi = float(np.sum(weights ** 2))
        result["portfolio_diversification"] = float(round(1.0 - hhi, 4))

    # ------------------------------------------------------------------
    # 5. portfolio_correlation (avg pairwise correlation of held tickers)
    # ------------------------------------------------------------------
    if market_ctx is not None and not pos.empty:
        try:
            held_tickers = list(pos["ticker"].unique())
            # Collect daily close series for tickers that have market data
            price_series: dict[str, pd.Series] = {}
            for ticker in held_tickers:
                ticker_df = market_ctx._get_df(ticker)  # noqa: WPS437
                if ticker_df is not None and "Close" in ticker_df.columns and len(ticker_df) >= 20:
                    price_series[ticker] = ticker_df["Close"]

            if len(price_series) >= 2:
                # Build returns DataFrame aligned by date
                returns_df = pd.DataFrame(
                    {t: s.pct_change() for t, s in price_series.items()}
                ).dropna(how="all")

                # Need enough overlapping data
                overlap = returns_df.dropna()
                if len(overlap) >= MIN_DATA_POINTS and overlap.shape[1] >= 2:
                    corr_matrix = overlap.corr().values
                    # Extract upper-triangle (excluding diagonal)
                    n = corr_matrix.shape[0]
                    upper = []
                    for i in range(n):
                        for j in range(i + 1, n):
                            val = corr_matrix[i, j]
                            if np.isfinite(val):
                                upper.append(val)
                    if len(upper) >= 1:
                        result["portfolio_correlation"] = float(round(np.mean(upper), 4))
        except Exception as exc:
            logger.debug("portfolio_correlation failed: %s", exc)

    # ------------------------------------------------------------------
    # 6. portfolio_long_only (1 if never uses inverse/short ETFs)
    # ------------------------------------------------------------------
    df["_type"] = df["ticker"].apply(classify_ticker_type)
    has_inverse = (df["_type"] == "inverse_etf").any()
    result["portfolio_long_only"] = 0 if has_inverse else 1

    # ------------------------------------------------------------------
    # 7. portfolio_cash_avg_pct (estimated avg cash level)
    # ------------------------------------------------------------------
    if len(pv_series) >= MIN_DATA_POINTS:
        try:
            # Estimate total capital as peak portfolio value (rough proxy)
            peak_value = pv_series.max()
            if peak_value > 0:
                cash_estimates = 1.0 - (pv_series / peak_value)
                cash_estimates = cash_estimates.clip(lower=0.0, upper=1.0)
                avg_cash = float(cash_estimates.mean())
                # Only report if it looks plausible (not trivially 0)
                if 0.0 < avg_cash < 1.0:
                    result["portfolio_cash_avg_pct"] = float(round(avg_cash, 4))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 8-9. portfolio_max_drawdown, portfolio_drawdown_recovery_days
    # ------------------------------------------------------------------
    if len(pv_series) >= MIN_DATA_POINTS:
        pv = pv_series.sort_index()
        pv = pv[pv > 0]
        if len(pv) >= MIN_DATA_POINTS:
            cum_max = pv.cummax()
            drawdown = (cum_max - pv) / cum_max
            drawdown = drawdown.replace([np.inf, -np.inf], 0.0).fillna(0.0)
            max_dd = float(drawdown.max())
            result["portfolio_max_drawdown"] = float(round(min(max_dd, 1.0), 4))

            # Recovery days: find the max-drawdown trough and measure how long
            # until portfolio value recovers to the prior peak.
            try:
                trough_idx = drawdown.idxmax()
                peak_before_trough = cum_max.loc[trough_idx]
                # Slice from trough onwards
                after_trough = pv.loc[trough_idx:]
                recovered = after_trough[after_trough >= peak_before_trough]
                if len(recovered) > 0:
                    recovery_date = recovered.index[0]
                    recovery_days = (recovery_date - trough_idx).days
                    result["portfolio_drawdown_recovery_days"] = max(int(recovery_days), 0)
                # If never recovered, leave as None
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 10. portfolio_income_component (1 if any income/dividend tickers)
    # ------------------------------------------------------------------
    unique_tickers = set(df["ticker"].unique())
    has_income = any(is_income(t) for t in unique_tickers)
    result["portfolio_income_component"] = 1 if has_income else 0

    # ------------------------------------------------------------------
    # 11. portfolio_growth_vs_value  (normalised to [-1, 1])
    # ------------------------------------------------------------------
    growth_count = sum(1 for t in unique_tickers if is_growth(t))
    value_count = sum(1 for t in unique_tickers if is_value(t))
    total_gv = growth_count + value_count
    if total_gv >= 1:
        raw = (growth_count - value_count) / total_gv  # range [-1, 1]
        result["portfolio_growth_vs_value"] = float(round(raw, 4))

    # ------------------------------------------------------------------
    # 12. portfolio_beta_estimate  (correlation of portfolio returns w/ SPY)
    # ------------------------------------------------------------------
    if len(pv_series) >= MIN_DATA_POINTS and market_ctx is not None:
        try:
            port_returns = _portfolio_daily_returns(pv_series)
            spy_df = market_ctx._get_df("SPY")  # noqa: WPS437
            if spy_df is not None and "Close" in spy_df.columns and len(spy_df) >= 20:
                spy_returns = spy_df["Close"].pct_change().dropna()

                # Align on common dates
                common = port_returns.index.intersection(spy_returns.index)
                if len(common) >= MIN_DATA_POINTS:
                    pr = port_returns.loc[common].values.astype(float)
                    sr = spy_returns.loc[common].values.astype(float)

                    # Remove any nan/inf
                    valid = np.isfinite(pr) & np.isfinite(sr)
                    pr = pr[valid]
                    sr = sr[valid]

                    if len(pr) >= MIN_DATA_POINTS:
                        # Beta = Cov(port, spy) / Var(spy)
                        cov_matrix = np.cov(pr, sr)
                        var_spy = cov_matrix[1, 1]
                        if var_spy > 0:
                            beta = cov_matrix[0, 1] / var_spy
                            # Clamp to reasonable range
                            beta = float(np.clip(beta, -5.0, 5.0))
                            result["portfolio_beta_estimate"] = float(round(beta, 4))
        except Exception as exc:
            logger.debug("portfolio_beta_estimate failed: %s", exc)

    return result
