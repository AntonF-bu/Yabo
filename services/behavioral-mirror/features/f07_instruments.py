"""Feature group 07 -- Instrument diversity & complexity metrics.

Extracts 14 features describing *what* a trader trades: ticker breadth,
concentration, ETF usage, options activity, leveraged/inverse products, and
how instrument diversity evolves over time.

All features are prefixed ``instrument_``.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import numpy as np
import pandas as pd

from features.utils import (
    compute_trend,
    safe_divide,
)

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trade_value(row: pd.Series) -> float:
    """Dollar value of a single trade row."""
    return abs(float(row["price"]) * float(row["quantity"]))


def _parse_option_ticker(ticker: str) -> dict[str, Any] | None:
    """Try to parse an OCC-style option symbol.

    Expected formats:
        AAPL230120C00150000   (standard OCC)
        AAPL_012023C150       (alternative broker format)

    Returns dict with keys: underlying, expiry, option_type, strike
    or None if parsing fails.
    """
    ticker = ticker.upper().strip()

    # Standard OCC: <underlying><YYMMDD><C|P><strike*1000>
    m = re.match(
        r"^([A-Z]{1,6})(\d{6})([CP])(\d{8})$", ticker
    )
    if m:
        underlying = m.group(1)
        expiry_str = m.group(2)  # YYMMDD
        opt_type = "call" if m.group(3) == "C" else "put"
        strike = int(m.group(4)) / 1000.0
        try:
            expiry = pd.Timestamp(f"20{expiry_str[:2]}-{expiry_str[2:4]}-{expiry_str[4:6]}")
        except Exception:
            expiry = pd.NaT
        return {
            "underlying": underlying,
            "expiry": expiry,
            "option_type": opt_type,
            "strike": strike,
        }

    # Alternative: <TICKER>_<MMDDYY or MMYYYY><C|P><strike>
    m2 = re.match(
        r"^([A-Z]{1,6})[_ ]?(\d{6,8})([CP])(\d+\.?\d*)$", ticker
    )
    if m2:
        underlying = m2.group(1)
        opt_type = "call" if m2.group(3) == "C" else "put"
        try:
            strike = float(m2.group(4))
        except ValueError:
            strike = None
        return {
            "underlying": underlying,
            "expiry": pd.NaT,
            "option_type": opt_type,
            "strike": strike,
        }

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract(
    trades_df: pd.DataFrame,
    positions: pd.DataFrame,
    market_ctx: Any,
) -> dict[str, Any]:
    """Return 14 instrument-diversity features.

    Parameters
    ----------
    trades_df : DataFrame
        Columns: ticker, action, quantity, price, date, fees.
    positions : DataFrame
        Columns: ticker, open_date, close_date, shares, avg_cost,
        close_price, hold_days, return_pct, pnl_usd, is_winner,
        is_partial_close, is_open.
    market_ctx : MarketContext
        Provides price look-ups (used for options moneyness).

    Returns
    -------
    dict  -- keys are ``instrument_*`` feature names.  Values that cannot
    be computed are ``None``.
    """
    result: dict[str, Any] = {
        "instrument_unique_tickers": None,
        "instrument_tickers_per_month": None,
        "instrument_top1_concentration": None,
        "instrument_top3_concentration": None,
        "instrument_etf_pct": None,
        "instrument_etf_as_core": None,
        "instrument_options_pct": None,
        "instrument_options_direction": None,
        "instrument_options_moneyness": None,
        "instrument_options_avg_dte": None,
        "instrument_leveraged_etf": None,
        "instrument_inverse_etf": None,
        "instrument_sector_etf": None,
        "instrument_complexity_trend": None,
    }

    if trades_df is None or trades_df.empty or len(trades_df) < MIN_DATA_POINTS:
        return result

    df = trades_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    if df.empty:
        return result

    df["_value"] = df.apply(_trade_value, axis=1)
    total_value = df["_value"].sum()

    # Classify every ticker once
    df["_type"] = df["ticker"].apply(market_ctx.classify_ticker_type)

    # ------------------------------------------------------------------
    # 1. instrument_unique_tickers
    # ------------------------------------------------------------------
    unique_tickers = df["ticker"].nunique()
    result["instrument_unique_tickers"] = int(unique_tickers)

    # ------------------------------------------------------------------
    # 2. instrument_tickers_per_month
    # ------------------------------------------------------------------
    df["_month"] = df["date"].dt.to_period("M")
    months = df["_month"].unique()
    if len(months) >= 1:
        new_per_month: list[int] = []
        seen: set[str] = set()
        for month in sorted(months):
            month_tickers = set(df.loc[df["_month"] == month, "ticker"].unique())
            new_count = len(month_tickers - seen)
            new_per_month.append(new_count)
            seen |= month_tickers
        result["instrument_tickers_per_month"] = float(
            round(np.mean(new_per_month), 4)
        )

    # ------------------------------------------------------------------
    # 3-4. instrument_top1_concentration, instrument_top3_concentration
    # ------------------------------------------------------------------
    if total_value > 0:
        ticker_values = df.groupby("ticker")["_value"].sum().sort_values(ascending=False)
        result["instrument_top1_concentration"] = float(
            round(ticker_values.iloc[0] / total_value, 4)
        )
        top3_val = ticker_values.iloc[:3].sum()
        result["instrument_top3_concentration"] = float(
            round(top3_val / total_value, 4)
        )

    # ------------------------------------------------------------------
    # 5-6. instrument_etf_pct, instrument_etf_as_core
    # ------------------------------------------------------------------
    etf_mask = df["_type"] == "etf"
    if total_value > 0:
        etf_value = df.loc[etf_mask, "_value"].sum()
        etf_pct = etf_value / total_value
        result["instrument_etf_pct"] = float(round(etf_pct, 4))
        result["instrument_etf_as_core"] = 1 if etf_pct > 0.40 else 0

    # ------------------------------------------------------------------
    # 7. instrument_options_pct  (fraction of trades that are options)
    # ------------------------------------------------------------------
    option_mask = df["_type"] == "option"
    n_options = int(option_mask.sum())
    n_total = len(df)
    result["instrument_options_pct"] = float(round(n_options / n_total, 4)) if n_total > 0 else 0.0

    # ------------------------------------------------------------------
    # 8-10. options detail features (direction, moneyness, avg DTE)
    # ------------------------------------------------------------------
    if n_options > 0:
        option_rows = df.loc[option_mask]
        calls: list[pd.Series] = []
        puts: list[pd.Series] = []
        moneyness_values: list[float] = []
        dte_values: list[float] = []

        for _, row in option_rows.iterrows():
            parsed = _parse_option_ticker(str(row["ticker"]))
            if parsed is None:
                continue
            if parsed["option_type"] == "call":
                calls.append(row)
            else:
                puts.append(row)

            # Moneyness: strike / spot at trade date
            if parsed.get("strike") and market_ctx is not None:
                try:
                    spot = market_ctx.get_price_at_date(
                        parsed["underlying"], row["date"]
                    )
                    if spot and spot > 0 and parsed["strike"] > 0:
                        moneyness_values.append(parsed["strike"] / spot)
                except Exception:
                    pass

            # DTE
            if pd.notna(parsed.get("expiry")) and pd.notna(row["date"]):
                try:
                    dte = (pd.Timestamp(parsed["expiry"]) - pd.Timestamp(row["date"])).days
                    if dte >= 0:
                        dte_values.append(float(dte))
                except Exception:
                    pass

        # Direction
        has_calls = len(calls) > 0
        has_puts = len(puts) > 0
        if has_calls and not has_puts:
            result["instrument_options_direction"] = 1
        elif has_puts and not has_calls:
            result["instrument_options_direction"] = -1
        elif has_calls and has_puts:
            result["instrument_options_direction"] = 0
        # else: stays None (parsed nothing successfully)

        # Moneyness
        if len(moneyness_values) >= MIN_DATA_POINTS:
            result["instrument_options_moneyness"] = float(
                round(np.mean(moneyness_values), 4)
            )

        # Avg DTE
        if len(dte_values) >= MIN_DATA_POINTS:
            result["instrument_options_avg_dte"] = float(round(np.mean(dte_values), 2))
    # If no options, direction/moneyness/dte stay None

    # ------------------------------------------------------------------
    # 11-13. leveraged / inverse / sector ETF flags
    # ------------------------------------------------------------------
    types_present = set(df["_type"].unique())
    result["instrument_leveraged_etf"] = 1 if "leveraged_etf" in types_present else 0
    result["instrument_inverse_etf"] = 1 if "inverse_etf" in types_present else 0

    # Sector ETF: classify_ticker_type lumps sector ETFs into "etf", so we
    # re-check against the known sector-ETF set from MarketDataService.
    sector_etfs = market_ctx.get_sector_etfs() if hasattr(market_ctx, "get_sector_etfs") else set()
    traded_tickers_upper = set(df["ticker"].str.upper())
    result["instrument_sector_etf"] = 1 if traded_tickers_upper & sector_etfs else 0

    # ------------------------------------------------------------------
    # 14. instrument_complexity_trend  (slope of unique tickers/month)
    # ------------------------------------------------------------------
    if len(months) >= 3:
        unique_per_month = (
            df.groupby("_month")["ticker"]
            .nunique()
            .sort_index()
            .values
            .astype(float)
        )
        result["instrument_complexity_trend"] = compute_trend(unique_per_month)

    return result
