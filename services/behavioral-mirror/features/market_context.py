"""Market data download, caching, and lookup utilities."""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "market_cache"


class MarketContext:
    """Holds downloaded OHLCV data and provides lookup helpers."""

    def __init__(self) -> None:
        self._data: dict[str, pd.DataFrame] = {}  # ticker -> OHLCV DataFrame
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def download_price_data(
        self,
        tickers: list[str],
        start_date: str | pd.Timestamp,
        end_date: str | pd.Timestamp,
    ) -> None:
        """Download daily OHLCV from yfinance. Cache to disk."""
        import yfinance as yf

        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Always include SPY and VIX (^VIX)
        all_tickers = list(set(tickers) | {"SPY", "^VIX"})

        start_str = str(pd.Timestamp(start_date).date())
        end_str = str(pd.Timestamp(end_date).date())

        for ticker in all_tickers:
            safe_name = ticker.replace("^", "_").replace("/", "_")
            cache_path = CACHE_DIR / f"{safe_name}_{start_str}_{end_str}.pkl"

            if cache_path.exists():
                try:
                    with open(cache_path, "rb") as f:
                        df = pickle.load(f)
                    if isinstance(df, pd.DataFrame) and len(df) > 0:
                        self._data[ticker] = df
                        continue
                except Exception:
                    pass

            try:
                # Pad start by 60 days for lookback calculations
                padded_start = str((pd.Timestamp(start_date) - pd.Timedelta(days=60)).date())
                df = yf.download(
                    ticker, start=padded_start, end=end_str,
                    progress=False, auto_adjust=True,
                )
                if isinstance(df, pd.DataFrame) and len(df) > 0:
                    # Flatten MultiIndex columns if present
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    self._data[ticker] = df
                    try:
                        with open(cache_path, "wb") as f:
                            pickle.dump(df, f)
                    except Exception:
                        pass
                else:
                    logger.debug("No data returned for %s", ticker)
            except Exception as e:
                logger.debug("Failed to download %s: %s", ticker, e)

        self._loaded = True
        logger.info(
            "Market context loaded: %d/%d tickers",
            len(self._data), len(all_tickers),
        )

    def _get_df(self, ticker: str) -> pd.DataFrame | None:
        return self._data.get(ticker)

    def get_spy_returns(self, date: pd.Timestamp | str) -> float | None:
        """SPY daily return for a given date."""
        df = self._get_df("SPY")
        if df is None or "Close" not in df.columns:
            return None
        date = pd.Timestamp(date)
        close = df["Close"]
        if date not in close.index:
            # Find nearest prior date
            mask = close.index <= date
            if not mask.any():
                return None
            date = close.index[mask][-1]
        idx = close.index.get_loc(date)
        if idx == 0:
            return None
        return float((close.iloc[idx] - close.iloc[idx - 1]) / close.iloc[idx - 1])

    def get_spy_close(self, date: pd.Timestamp | str) -> float | None:
        df = self._get_df("SPY")
        if df is None:
            return None
        return self._get_close_at(df, date)

    def get_vix_close(self, date: pd.Timestamp | str) -> float | None:
        df = self._get_df("^VIX")
        if df is None:
            return None
        return self._get_close_at(df, date)

    def get_price_at_date(self, ticker: str, date: pd.Timestamp | str) -> float | None:
        df = self._get_df(ticker)
        if df is None:
            return None
        return self._get_close_at(df, date)

    def get_ohlcv_at_date(self, ticker: str, date: pd.Timestamp | str) -> dict | None:
        """Return full OHLCV dict for date."""
        df = self._get_df(ticker)
        if df is None:
            return None
        date = pd.Timestamp(date)
        mask = df.index <= date
        if not mask.any():
            return None
        row = df.loc[df.index[mask][-1]]
        return {
            "open": float(row.get("Open", 0)),
            "high": float(row.get("High", 0)),
            "low": float(row.get("Low", 0)),
            "close": float(row.get("Close", 0)),
            "volume": float(row.get("Volume", 0)),
        }

    def get_20d_high(self, ticker: str, date: pd.Timestamp | str) -> float | None:
        df = self._get_df(ticker)
        if df is None or "High" not in df.columns:
            return None
        date = pd.Timestamp(date)
        mask = df.index <= date
        recent = df.loc[mask].tail(20)
        if len(recent) < 5:
            return None
        return float(recent["High"].max())

    def get_52w_range(self, ticker: str, date: pd.Timestamp | str) -> tuple[float, float] | None:
        df = self._get_df(ticker)
        if df is None or "Close" not in df.columns:
            return None
        date = pd.Timestamp(date)
        start = date - pd.Timedelta(days=365)
        mask = (df.index >= start) & (df.index <= date)
        subset = df.loc[mask]
        if len(subset) < 20:
            return None
        return float(subset["Close"].min()), float(subset["Close"].max())

    def get_20d_ma(self, ticker: str, date: pd.Timestamp | str) -> float | None:
        df = self._get_df(ticker)
        if df is None or "Close" not in df.columns:
            return None
        date = pd.Timestamp(date)
        mask = df.index <= date
        recent = df.loc[mask].tail(20)
        if len(recent) < 10:
            return None
        return float(recent["Close"].mean())

    def get_relative_volume(self, ticker: str, date: pd.Timestamp | str) -> float | None:
        df = self._get_df(ticker)
        if df is None or "Volume" not in df.columns:
            return None
        date = pd.Timestamp(date)
        mask = df.index <= date
        recent = df.loc[mask].tail(21)
        if len(recent) < 5:
            return None
        avg_vol = recent.iloc[:-1]["Volume"].mean()
        if avg_vol == 0:
            return None
        day_vol = recent.iloc[-1]["Volume"]
        return float(day_vol / avg_vol)

    def is_earnings_nearby(self, ticker: str, date: pd.Timestamp | str, window: int = 5) -> bool:
        """Estimate earnings proximity using volatility spikes as proxy."""
        df = self._get_df(ticker)
        if df is None or "Close" not in df.columns or len(df) < 30:
            return False
        date = pd.Timestamp(date)
        close = df["Close"]
        returns = close.pct_change().abs()
        avg_move = returns.rolling(20).mean()

        # Look at window around date
        start = date - pd.Timedelta(days=window)
        end = date + pd.Timedelta(days=window)
        mask = (returns.index >= start) & (returns.index <= end)
        window_returns = returns.loc[mask]
        window_avg = avg_move.loc[mask]

        if len(window_returns) == 0 or window_avg.isna().all():
            return False

        # If any day in window had move > 3x average, likely earnings
        for idx in window_returns.index:
            if idx in window_avg.index:
                ret = window_returns[idx]
                avg = window_avg[idx]
                if pd.notna(ret) and pd.notna(avg) and avg > 0 and ret > 3 * avg:
                    return True
        return False

    def get_spy_20d_return(self, date: pd.Timestamp | str) -> float | None:
        """SPY cumulative return over prior 20 trading days."""
        df = self._get_df("SPY")
        if df is None or "Close" not in df.columns:
            return None
        date = pd.Timestamp(date)
        mask = df.index <= date
        recent = df.loc[mask].tail(21)
        if len(recent) < 21:
            return None
        return float((recent["Close"].iloc[-1] / recent["Close"].iloc[0]) - 1)

    def get_stock_daily_return(self, ticker: str, date: pd.Timestamp | str) -> float | None:
        """Stock's daily return for a given date."""
        df = self._get_df(ticker)
        if df is None or "Close" not in df.columns:
            return None
        date = pd.Timestamp(date)
        mask = df.index <= date
        subset = df.loc[mask].tail(2)
        if len(subset) < 2:
            return None
        return float((subset["Close"].iloc[-1] / subset["Close"].iloc[-2]) - 1)

    def get_overnight_gap(self, ticker: str, date: pd.Timestamp | str) -> float | None:
        """Overnight gap: (Open - previous Close) / previous Close."""
        df = self._get_df(ticker)
        if df is None or "Open" not in df.columns or "Close" not in df.columns:
            return None
        date = pd.Timestamp(date)
        mask = df.index <= date
        subset = df.loc[mask].tail(2)
        if len(subset) < 2:
            return None
        prev_close = subset["Close"].iloc[-2]
        if prev_close == 0:
            return None
        return float((subset["Open"].iloc[-1] - prev_close) / prev_close)

    def _get_close_at(self, df: pd.DataFrame, date: pd.Timestamp | str) -> float | None:
        if "Close" not in df.columns:
            return None
        date = pd.Timestamp(date)
        mask = df.index <= date
        if not mask.any():
            return None
        return float(df.loc[df.index[mask][-1], "Close"])


def download_price_data(
    tickers: list[str],
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
) -> MarketContext:
    """Convenience: create a MarketContext and download data."""
    ctx = MarketContext()
    ctx.download_price_data(tickers, start_date, end_date)
    return ctx
