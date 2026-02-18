"""
Downloads and caches real daily OHLCV data from yfinance.
Stores cached data as pickle files so repeated runs skip the download.
"""

import os
import pickle
import datetime
from typing import List, Dict, Optional

import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SIM_START = datetime.date(2023, 6, 1)
SIM_END = datetime.date(2024, 12, 31)

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def download_market_data(tickers: List[str],
                         cache_dir: Optional[str] = None,
                         verbose: bool = False) -> Dict[str, pd.DataFrame]:
    """
    Download daily OHLCV for every ticker in *tickers*.
    Returns {ticker: DataFrame} with columns [Open, High, Low, Close, Volume].
    Data is cached to disk so repeated runs don't re-download.
    """
    cache_dir = cache_dir or CACHE_DIR
    os.makedirs(cache_dir, exist_ok=True)

    cache_path = os.path.join(cache_dir, "ohlcv_cache.pkl")

    # Load existing cache
    cached: Dict[str, pd.DataFrame] = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as f:
                cached = pickle.load(f)
            if verbose:
                print(f"  Loaded cache with {len(cached)} tickers")
        except Exception:
            cached = {}

    # Figure out which tickers still need downloading
    missing = [t for t in tickers if t not in cached]

    if missing:
        if verbose:
            print(f"  Downloading {len(missing)} tickers: {missing[:10]}{'...' if len(missing) > 10 else ''}")

        # Download in bulk — yfinance supports multi-ticker download
        start_str = (SIM_START - datetime.timedelta(days=60)).isoformat()  # extra lookback
        end_str = (SIM_END + datetime.timedelta(days=5)).isoformat()

        try:
            raw = yf.download(
                tickers=missing,
                start=start_str,
                end=end_str,
                group_by="ticker",
                auto_adjust=True,
                progress=verbose,
                threads=True,
            )
        except Exception as e:
            if verbose:
                print(f"  Bulk download failed ({e}), trying individual downloads")
            raw = None

        if raw is not None and not raw.empty:
            if len(missing) == 1:
                # Single ticker: raw is a simple DataFrame
                ticker = missing[0]
                df = _clean_df(raw)
                if df is not None and not df.empty:
                    cached[ticker] = df
            else:
                # Multiple tickers: raw is a multi-level column DataFrame
                for ticker in missing:
                    try:
                        df = raw[ticker] if ticker in raw.columns.get_level_values(0) else None
                        if df is not None:
                            df = _clean_df(df)
                            if df is not None and not df.empty:
                                cached[ticker] = df
                    except Exception:
                        pass

        # Try individual download for any still missing
        still_missing = [t for t in missing if t not in cached]
        for ticker in still_missing:
            try:
                t = yf.Ticker(ticker)
                df = t.history(start=start_str, end=end_str, auto_adjust=True)
                df = _clean_df(df)
                if df is not None and not df.empty:
                    cached[ticker] = df
                    if verbose:
                        print(f"    Downloaded {ticker}: {len(df)} rows")
            except Exception as e:
                if verbose:
                    print(f"    Failed to download {ticker}: {e}")

        # Save updated cache
        try:
            with open(cache_path, "wb") as f:
                pickle.dump(cached, f)
        except Exception as e:
            if verbose:
                print(f"  Warning: could not save cache: {e}")

    if verbose:
        avail = [t for t in tickers if t in cached]
        print(f"  Market data ready: {len(avail)}/{len(tickers)} tickers available")

    return cached


def get_trading_days(market_data: Dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    """Return sorted trading days within the simulation window."""
    if not market_data:
        # No data available — generate a business-day calendar as fallback
        return pd.bdate_range(SIM_START, SIM_END)
    ref_ticker = "SPY" if "SPY" in market_data else next(iter(market_data))
    df = market_data[ref_ticker]
    mask = (df.index >= pd.Timestamp(SIM_START)) & (df.index <= pd.Timestamp(SIM_END))
    return df.index[mask]


def get_price(market_data: Dict[str, pd.DataFrame],
              ticker: str, date: pd.Timestamp,
              field: str = "Close") -> Optional[float]:
    """Get a price for *ticker* on *date*. Returns None if unavailable."""
    if ticker not in market_data:
        return None
    df = market_data[ticker]
    if date in df.index:
        val = df.loc[date, field]
        if pd.notna(val):
            return float(val)
    # Try nearest prior date (handles holidays / missing data)
    prior = df.index[df.index <= date]
    if len(prior) > 0:
        val = df.loc[prior[-1], field]
        if pd.notna(val):
            return float(val)
    return None


def get_price_history(market_data: Dict[str, pd.DataFrame],
                      ticker: str, end_date: pd.Timestamp,
                      lookback: int = 20) -> Optional[pd.Series]:
    """Return the last *lookback* closing prices up to and including *end_date*."""
    if ticker not in market_data:
        return None
    df = market_data[ticker]
    mask = df.index <= end_date
    subset = df.loc[mask, "Close"].tail(lookback)
    if len(subset) < 2:
        return None
    return subset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_df(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Normalise a yfinance DataFrame to consistent column names."""
    if df is None or df.empty:
        return None
    # Flatten multi-level columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(-1)
    # Keep only OHLCV columns we care about
    want = ["Open", "High", "Low", "Close", "Volume"]
    have = [c for c in want if c in df.columns]
    if "Close" not in have:
        return None
    df = df[have].copy()
    df.dropna(subset=["Close"], inplace=True)
    return df
