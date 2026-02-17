"""Download, cache and enrich daily OHLCV data via yfinance (with synthetic fallback)."""

from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    yf = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_DIR = DATA_DIR / "cache"

TICKERS: list[str] = [
    # Tech
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AMD", "INTC", "AVGO",
    # Finance
    "JPM", "GS", "BAC", "MS", "V",
    # Healthcare
    "JNJ", "UNH", "PFE", "ABBV", "LLY",
    # Energy
    "XOM", "CVX", "COP", "SLB", "OXY",
    # Consumer
    "KO", "PG", "WMT", "COST", "MCD",
    # Utilities
    "NEE", "DUK", "SO",
    # Indices / ETFs
    "SPY", "QQQ", "IWM",
]

TICKER_SECTOR: dict[str, str] = {
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology",
    "GOOGL": "Technology", "AMZN": "Technology", "META": "Technology",
    "TSLA": "Technology", "AMD": "Technology", "INTC": "Technology",
    "AVGO": "Technology",
    "JPM": "Financials", "GS": "Financials", "BAC": "Financials",
    "MS": "Financials", "V": "Financials",
    "JNJ": "Healthcare", "UNH": "Healthcare", "PFE": "Healthcare",
    "ABBV": "Healthcare", "LLY": "Healthcare",
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy",
    "SLB": "Energy", "OXY": "Energy",
    "KO": "Consumer", "PG": "Consumer", "WMT": "Consumer",
    "COST": "Consumer", "MCD": "Consumer",
    "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities",
    "SPY": "Index", "QQQ": "Index", "IWM": "Index",
}

START_DATE = "2024-06-01"
END_DATE = "2025-12-31"

# Approximate quarterly earnings months per ticker (month numbers)
# Most US large-caps report Jan/Apr/Jul/Oct
_DEFAULT_EARNINGS_MONTHS = [1, 4, 7, 10]
_EARNINGS_OVERRIDES: dict[str, list[int]] = {
    # Some companies report on slightly different schedules
    "COST": [3, 6, 9, 12],
    "NKE": [3, 6, 9, 12],
}


def _approximate_earnings_dates(ticker: str, trading_dates: pd.DatetimeIndex) -> list[pd.Timestamp]:
    """Return approximate earnings dates within the trading window."""
    months = _EARNINGS_OVERRIDES.get(ticker, _DEFAULT_EARNINGS_MONTHS)
    dates: list[pd.Timestamp] = []
    for year in range(2024, 2027):
        for month in months:
            # Approximate: 3rd week of the month
            candidate = pd.Timestamp(year=year, month=month, day=20, tz="UTC")
            # snap to nearest trading day
            idx = trading_dates.searchsorted(candidate)
            if 0 <= idx < len(trading_dates):
                dates.append(trading_dates[idx])
    return dates


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def download_and_cache(force: bool = False) -> pd.DataFrame:
    """Download OHLCV for all tickers, compute indicators, cache to parquet.

    Returns a multi-indexed DataFrame: index=(Date), columns are MultiIndex (ticker, field).
    We flatten to a single-level column like 'AAPL_Close', 'AAPL_RSI', etc.
    """
    cache_path = CACHE_DIR / "market_data.parquet"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if cache_path.exists() and not force:
        logger.info("Loading cached market data from %s", cache_path)
        return pd.read_parquet(cache_path)

    if yf is None:
        logger.warning("yfinance not installed – using synthetic data")
        return _generate_synthetic_data(cache_path)

    logger.info("Downloading market data for %d tickers …", len(TICKERS))

    frames: dict[str, pd.DataFrame] = {}
    for ticker in TICKERS:
        try:
            df = yf.download(
                ticker, start=START_DATE, end=END_DATE,
                progress=False, auto_adjust=True,
            )
            if df.empty:
                logger.warning("No data for %s – skipping", ticker)
                continue
            # yfinance may return MultiIndex columns for single ticker
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            frames[ticker] = df
        except Exception:
            logger.exception("Failed to download %s", ticker)

    if not frames:
        logger.warning("No data from yfinance – falling back to synthetic market data")
        return _generate_synthetic_data(cache_path)

    # Build a unified dataframe with prefixed columns
    all_cols: dict[str, pd.Series] = {}

    # Make sure we have a common date index (business days present in SPY)
    spy_dates = frames.get("SPY")
    if spy_dates is None:
        raise RuntimeError("SPY data required but missing")
    base_index = spy_dates.index

    for ticker, df in frames.items():
        # Reindex to base_index, forward-fill small gaps
        df = df.reindex(base_index).ffill(limit=3)

        all_cols[f"{ticker}_Open"] = df["Open"]
        all_cols[f"{ticker}_High"] = df["High"]
        all_cols[f"{ticker}_Low"] = df["Low"]
        all_cols[f"{ticker}_Close"] = df["Close"]
        all_cols[f"{ticker}_Volume"] = df["Volume"]

        close = df["Close"]
        volume = df["Volume"]

        # Moving averages
        all_cols[f"{ticker}_MA20"] = close.rolling(20).mean()
        all_cols[f"{ticker}_MA50"] = close.rolling(50).mean()

        # RSI(14)
        all_cols[f"{ticker}_RSI"] = _compute_rsi(close)

        # Volume ratio vs 20-day avg
        vol_ma20 = volume.rolling(20).mean()
        all_cols[f"{ticker}_VolRatio"] = volume / vol_ma20.replace(0, np.nan)

        # Daily returns
        all_cols[f"{ticker}_Return"] = close.pct_change()

        # 10-day high (for dip-buy detection)
        all_cols[f"{ticker}_High10"] = close.rolling(10).max()

    result = pd.DataFrame(all_cols, index=base_index)
    result.index.name = "Date"

    # Ensure index is tz-aware UTC
    if result.index.tz is None:
        result.index = result.index.tz_localize("UTC")

    result.to_parquet(cache_path)
    logger.info("Cached market data to %s  (%d rows, %d cols)", cache_path, len(result), len(result.columns))
    return result


# Approximate starting prices for realistic synthetic data
_SEED_PRICES: dict[str, float] = {
    "AAPL": 195.0, "MSFT": 420.0, "NVDA": 125.0, "GOOGL": 175.0,
    "AMZN": 185.0, "META": 500.0, "TSLA": 180.0, "AMD": 165.0,
    "INTC": 31.0, "AVGO": 1400.0,
    "JPM": 200.0, "GS": 450.0, "BAC": 38.0, "MS": 95.0, "V": 280.0,
    "JNJ": 150.0, "UNH": 500.0, "PFE": 28.0, "ABBV": 170.0, "LLY": 800.0,
    "XOM": 115.0, "CVX": 160.0, "COP": 120.0, "SLB": 52.0, "OXY": 62.0,
    "KO": 62.0, "PG": 165.0, "WMT": 170.0, "COST": 720.0, "MCD": 260.0,
    "NEE": 75.0, "DUK": 100.0, "SO": 75.0,
    "SPY": 530.0, "QQQ": 455.0, "IWM": 205.0,
}

# Annualised drift & vol per sector for realism
_SECTOR_PARAMS: dict[str, tuple[float, float]] = {
    "Technology": (0.15, 0.28),
    "Financials": (0.10, 0.22),
    "Healthcare": (0.08, 0.24),
    "Energy": (0.06, 0.30),
    "Consumer": (0.07, 0.18),
    "Utilities": (0.05, 0.16),
    "Index": (0.10, 0.16),
}


def _generate_synthetic_data(cache_path: Path) -> pd.DataFrame:
    """Generate realistic synthetic OHLCV data when yfinance is unavailable."""
    logger.info("Generating synthetic market data for %d tickers …", len(TICKERS))
    rng = np.random.RandomState(2024)

    # Build business-day date range
    dates = pd.bdate_range(start=START_DATE, end=END_DATE, tz="UTC")
    n_days = len(dates)

    all_cols: dict[str, pd.Series] = {}

    for ticker in TICKERS:
        sector = TICKER_SECTOR.get(ticker, "Index")
        annual_drift, annual_vol = _SECTOR_PARAMS.get(sector, (0.08, 0.22))
        daily_drift = annual_drift / 252
        daily_vol = annual_vol / np.sqrt(252)
        start_price = _SEED_PRICES.get(ticker, 100.0)

        # Geometric Brownian Motion
        returns = rng.normal(daily_drift, daily_vol, n_days)
        # Add some autocorrelation (momentum) and mean-reversion
        ar_coeff = rng.uniform(-0.05, 0.10)
        for i in range(1, len(returns)):
            returns[i] += ar_coeff * returns[i - 1]

        prices = start_price * np.exp(np.cumsum(returns))
        # Add occasional large moves (earnings-like)
        for i in range(0, n_days, rng.randint(50, 70)):
            shock = rng.normal(0, daily_vol * 3)
            prices[i:] *= np.exp(shock)

        close = pd.Series(prices, index=dates)
        high = close * (1 + rng.uniform(0.002, 0.02, n_days))
        low = close * (1 - rng.uniform(0.002, 0.02, n_days))
        open_ = low + (high - low) * rng.uniform(0.2, 0.8, n_days)
        volume = pd.Series(
            rng.lognormal(mean=16, sigma=0.5, size=n_days).astype(int),
            index=dates,
        )

        all_cols[f"{ticker}_Open"] = open_
        all_cols[f"{ticker}_High"] = high
        all_cols[f"{ticker}_Low"] = low
        all_cols[f"{ticker}_Close"] = close
        all_cols[f"{ticker}_Volume"] = volume

        # Indicators
        all_cols[f"{ticker}_MA20"] = close.rolling(20).mean()
        all_cols[f"{ticker}_MA50"] = close.rolling(50).mean()
        all_cols[f"{ticker}_RSI"] = _compute_rsi(close)
        vol_ma20 = volume.rolling(20).mean()
        all_cols[f"{ticker}_VolRatio"] = volume / vol_ma20.replace(0, np.nan)
        all_cols[f"{ticker}_Return"] = close.pct_change()
        all_cols[f"{ticker}_High10"] = close.rolling(10).max()

    result = pd.DataFrame(all_cols, index=dates)
    result.index.name = "Date"
    result.to_parquet(cache_path)
    logger.info("Cached synthetic market data to %s  (%d rows, %d cols)",
                cache_path, len(result), len(result.columns))
    return result


def get_spy_returns(market_data: pd.DataFrame) -> pd.Series:
    """Extract SPY daily returns series."""
    return market_data["SPY_Return"].dropna()


def get_earnings_dates(market_data: pd.DataFrame) -> dict[str, list[pd.Timestamp]]:
    """Return dict of ticker -> list of approximate earnings dates."""
    trading_dates = market_data.index
    result: dict[str, list[pd.Timestamp]] = {}
    for ticker in TICKERS:
        if f"{ticker}_Close" in market_data.columns:
            result[ticker] = _approximate_earnings_dates(ticker, trading_dates)
    return result


def get_trading_dates(market_data: pd.DataFrame) -> pd.DatetimeIndex:
    """Return the DatetimeIndex of all trading days."""
    return market_data.index
