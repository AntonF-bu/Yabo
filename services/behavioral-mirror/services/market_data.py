"""Centralized market data and ticker classification service.

Replaces MarketContext (yfinance price data) and hardcoded lookup dicts
in utils.py.  Uses Supabase as persistent cache, yfinance as data source.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MarketDataService:
    """Central service for ALL market/reference data lookups.

    Lifecycle:
        1. __init__(supabase_client) — loads reference data from Supabase
        2. prefetch_tickers(tickers) — loads ticker metadata
        3. prefetch_price_data(tickers, start, end) — downloads OHLCV
        4. Use lookup methods throughout feature extraction
    """

    def __init__(self, supabase_client=None):
        self._client = supabase_client
        # Price data cache (in-memory)
        self._price_data: dict[str, pd.DataFrame] = {}
        # Ticker metadata cache
        self._ticker_meta: dict[str, dict] = {}
        # Classification lists: list_name -> set of tickers
        self._classifications: dict[str, set[str]] = {}
        # Classification metadata: list_name -> {ticker: metadata_dict}
        self._classification_meta: dict[str, dict[str, dict]] = {}
        # Economic calendar
        self._fomc_dates: set[str] = set()
        self._cpi_dates: set[str] = set()
        # Analysis config
        self._config: dict[str, Any] = {}
        # Sector int map (from config)
        self._sector_int_map: dict[str, int] = {
            "Technology": 0, "Healthcare": 1, "Financials": 2,
            "Consumer Discretionary": 3, "Consumer Staples": 4,
            "Energy": 5, "Industrials": 6, "Communication Services": 7,
            "Materials": 8, "Utilities": 9, "Real Estate": 10, "unknown": 11,
        }
        self._loaded = False

        # Load reference data from Supabase
        self._load_reference_data()

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ── Reference data loading ───────────────────────────────────────

    def _load_reference_data(self) -> None:
        """Load classifications, economic calendar, and config from Supabase."""
        if not self._client:
            logger.warning("No Supabase client — MarketDataService running without persistent cache")
            return

        try:
            # 1. Load ticker_classifications
            resp = self._client.table("ticker_classifications").select("list_name, ticker, metadata").execute()
            for row in (resp.data or []):
                ln = row["list_name"]
                tk = row["ticker"]
                self._classifications.setdefault(ln, set()).add(tk)
                meta = row.get("metadata")
                if meta and meta != {}:
                    self._classification_meta.setdefault(ln, {})[tk] = meta
            logger.info("Loaded %d classification lists from Supabase", len(self._classifications))
        except Exception as e:
            logger.warning("Failed to load ticker_classifications: %s", e)

        try:
            # 2. Load economic_calendar
            resp = self._client.table("economic_calendar").select("event_type, event_date").execute()
            for row in (resp.data or []):
                date_str = str(row["event_date"])
                if row["event_type"] == "FOMC":
                    self._fomc_dates.add(date_str)
                elif row["event_type"] == "CPI":
                    self._cpi_dates.add(date_str)
            logger.info("Loaded %d FOMC + %d CPI dates", len(self._fomc_dates), len(self._cpi_dates))
        except Exception as e:
            logger.warning("Failed to load economic_calendar: %s", e)

        try:
            # 3. Load analysis_config
            resp = self._client.table("analysis_config").select("key, value").execute()
            for row in (resp.data or []):
                self._config[row["key"]] = row["value"]
            # Update sector_int_map from config
            if "sector_int_map" in self._config:
                sim = self._config["sector_int_map"]
                if isinstance(sim, dict):
                    self._sector_int_map = {k: int(v) for k, v in sim.items()}
            logger.info("Loaded %d config entries", len(self._config))
        except Exception as e:
            logger.warning("Failed to load analysis_config: %s", e)

    # ── Ticker metadata ──────────────────────────────────────────────

    # Regex for option symbols: letters followed by 4+ digits, a letter, then more digits
    # e.g. APP2620C780, TSLA2821A710
    _OPTION_RE = re.compile(r"^[A-Z]+\d{4,}[A-Z]\d+$")
    # Money market tickers typically end in XX (e.g. FRSXX, SPAXX)
    _MONEY_MARKET_RE = re.compile(r"^[A-Z]{3,5}XX$")

    @classmethod
    def _is_garbage_ticker(cls, ticker: str) -> bool:
        """Return True if ticker should NOT be sent to yfinance."""
        if ticker.startswith("CUSIP-"):
            return True
        if cls._OPTION_RE.match(ticker):
            return True
        if cls._MONEY_MARKET_RE.match(ticker):
            return True
        return False

    def prefetch_tickers(self, tickers: list[str]) -> None:
        """Load ticker metadata from Supabase cache, fetch missing from yfinance."""
        if not tickers:
            return

        unique_tickers = list(set(t.upper() for t in tickers))
        # Filter out garbage tickers that yfinance can't resolve
        garbage = [t for t in unique_tickers if self._is_garbage_ticker(t)]
        if garbage:
            logger.debug("Filtering %d garbage tickers from prefetch: %s", len(garbage), garbage[:5])
            for t in garbage:
                self._ticker_meta[t] = {"ticker": t, "sector": "unknown"}
            unique_tickers = [t for t in unique_tickers if not self._is_garbage_ticker(t)]
        if not unique_tickers:
            return

        # Check Supabase cache
        if self._client:
            try:
                # Supabase IN filter has a limit, batch in chunks of 100
                for i in range(0, len(unique_tickers), 100):
                    chunk = unique_tickers[i:i+100]
                    resp = (self._client.table("ticker_metadata")
                            .select("*")
                            .in_("ticker", chunk)
                            .execute())
                    for row in (resp.data or []):
                        self._ticker_meta[row["ticker"]] = row
            except Exception as e:
                logger.warning("Failed to load ticker_metadata from Supabase: %s", e)

        # Fetch missing tickers from yfinance
        missing = [t for t in unique_tickers if t not in self._ticker_meta]
        if missing:
            self._fetch_tickers_yfinance(missing)

    def _fetch_tickers_yfinance(self, tickers: list[str]) -> None:
        """Fetch ticker metadata from yfinance and cache to Supabase."""
        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not available for metadata fetch")
            return

        for ticker in tickers:
            try:
                info = yf.Ticker(ticker).info or {}
                raw_cap = info.get("marketCap")
                meta = {
                    "ticker": ticker,
                    "sector": info.get("sector", "unknown") or "unknown",
                    "industry": info.get("industry"),
                    "market_cap_category": self._categorize_market_cap(raw_cap),
                }
                self._ticker_meta[ticker] = meta

                # Persist to Supabase
                if self._client:
                    try:
                        self._client.table("ticker_metadata").upsert({
                            "ticker": ticker,
                            "sector": meta["sector"],
                            "industry": meta.get("industry"),
                            "market_cap_category": meta.get("market_cap_category"),
                            "data_source": "yfinance",
                        }).execute()
                    except Exception:
                        pass
            except Exception as e:
                logger.debug("Failed to fetch metadata for %s: %s", ticker, e)
                # Store a minimal entry so we don't retry
                self._ticker_meta[ticker] = {"ticker": ticker, "sector": "unknown"}

    @staticmethod
    def _categorize_market_cap(market_cap: int | float | None) -> str | None:
        if market_cap is None:
            return None
        try:
            mc = float(market_cap)
        except (ValueError, TypeError):
            return None
        if mc >= 200_000_000_000:
            return "mega"
        if mc >= 10_000_000_000:
            return "large"
        if mc >= 2_000_000_000:
            return "mid"
        if mc >= 300_000_000:
            return "small"
        return "micro"

    # ── Classification lookups ───────────────────────────────────────

    def get_sector(self, ticker: str) -> str:
        """Return GICS sector for a ticker, 'unknown' if not found."""
        t = ticker.upper()
        meta = self._ticker_meta.get(t)
        if meta and meta.get("sector") and meta["sector"] != "unknown":
            return meta["sector"]
        return "unknown"

    def get_sector_int(self, sector_name: str) -> int:
        """Return integer encoding for a sector name."""
        return self._sector_int_map.get(sector_name, self._sector_int_map.get("unknown", 11))

    def classify_ticker_type(self, ticker: str) -> str:
        """Classify ticker as stock, etf, option, leveraged_etf, inverse_etf, sector_etf."""
        t = ticker.upper()
        if t in self._classifications.get("leveraged_etfs", set()):
            return "leveraged_etf"
        if t in self._classifications.get("inverse_etfs", set()):
            return "inverse_etf"
        if t in self._classifications.get("sector_etfs", set()):
            return "etf"
        if t in self._classifications.get("etfs", set()):
            return "etf"
        # Heuristic for options: tickers with digits or > 6 chars
        if any(c.isdigit() for c in t) and len(t) > 5:
            return "option"
        return "stock"

    def is_etf(self, ticker: str) -> bool:
        t = ticker.upper()
        return (t in self._classifications.get("etfs", set())
                or t in self._classifications.get("sector_etfs", set())
                or t in self._classifications.get("leveraged_etfs", set())
                or t in self._classifications.get("inverse_etfs", set()))

    def is_leveraged_etf(self, ticker: str) -> bool:
        return ticker.upper() in self._classifications.get("leveraged_etfs", set())

    def is_inverse_etf(self, ticker: str) -> bool:
        return ticker.upper() in self._classifications.get("inverse_etfs", set())

    def get_leverage_factor(self, ticker: str) -> int:
        """Return leverage multiplier (1, 2, or 3). 1 for non-leveraged."""
        t = ticker.upper()
        meta = self._classification_meta.get("leveraged_etfs", {}).get(t)
        if meta and "leverage" in meta:
            return int(meta["leverage"])
        # Check inverse_etfs too (1x inverse)
        if t in self._classifications.get("inverse_etfs", set()):
            inv_meta = self._classification_meta.get("leveraged_etfs", {}).get(t)
            if inv_meta and "leverage" in inv_meta:
                return int(inv_meta["leverage"])
            return 1
        return 1

    def is_mega_cap(self, ticker: str) -> bool:
        return ticker.upper() in self._classifications.get("mega_cap", set())

    def is_small_cap(self, ticker: str) -> bool:
        return ticker.upper() in self._classifications.get("small_cap", set())

    def is_meme_stock(self, ticker: str) -> bool:
        return ticker.upper() in self._classifications.get("meme_stocks", set())

    def is_recent_ipo(self, ticker: str) -> bool:
        return ticker.upper() in self._classifications.get("recent_ipos", set())

    def is_growth(self, ticker: str) -> bool:
        return ticker.upper() in self._classifications.get("growth", set())

    def is_value(self, ticker: str) -> bool:
        return ticker.upper() in self._classifications.get("value", set())

    def is_income(self, ticker: str) -> bool:
        return ticker.upper() in self._classifications.get("income", set())

    def get_meme_stocks(self) -> set[str]:
        return set(self._classifications.get("meme_stocks", set()))

    def get_top_retail_stocks(self) -> set[str]:
        return set(self._classifications.get("top_retail", set()))

    def get_sector_etfs(self) -> set[str]:
        return set(self._classifications.get("sector_etfs", set()))

    # ── Economic calendar ────────────────────────────────────────────

    def get_fomc_dates(self) -> set[str]:
        return set(self._fomc_dates)

    def get_cpi_dates(self) -> set[str]:
        return set(self._cpi_dates)

    # ── Config ───────────────────────────────────────────────────────

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a config value from analysis_config."""
        return self._config.get(key, default)

    # ── Price data ───────────────────────────────────────────────────

    def prefetch_price_data(
        self,
        tickers: list[str],
        start_date: str | pd.Timestamp,
        end_date: str | pd.Timestamp,
    ) -> None:
        """Download daily OHLCV for tickers + SPY + VIX.

        Checks Supabase price_cache first, falls back to yfinance.
        """
        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not available for price data")
            return

        all_tickers = list(set(tickers) | {"SPY", "^VIX"})
        start_str = str(pd.Timestamp(start_date).date())
        end_str = str(pd.Timestamp(end_date).date())
        padded_start = str((pd.Timestamp(start_date) - pd.Timedelta(days=60)).date())

        # Try to load from Supabase cache first
        tickers_to_fetch: list[str] = []
        if self._client:
            try:
                safe_tickers = [t for t in all_tickers if t not in self._price_data]
                if safe_tickers:
                    for i in range(0, len(safe_tickers), 50):
                        chunk = safe_tickers[i:i+50]
                        resp = (self._client.table("price_cache")
                                .select("ticker, start_date, end_date, ohlcv_json")
                                .in_("ticker", chunk)
                                .execute())
                        for row in (resp.data or []):
                            try:
                                tk = row["ticker"]
                                cached_start = str(row["start_date"])
                                cached_end = str(row["end_date"])
                                # Use cache if it covers our date range
                                if cached_start <= padded_start and cached_end >= end_str:
                                    df = self._deserialize_ohlcv(row["ohlcv_json"])
                                    if df is not None and len(df) > 0:
                                        self._price_data[tk] = df
                            except Exception:
                                pass
            except Exception as e:
                logger.debug("Failed to check price_cache: %s", e)

        tickers_to_fetch = [t for t in all_tickers if t not in self._price_data]

        # Download missing from yfinance
        for ticker in tickers_to_fetch:
            try:
                df = yf.download(
                    ticker, start=padded_start, end=end_str,
                    progress=False, auto_adjust=True,
                )
                if isinstance(df, pd.DataFrame) and len(df) > 0:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    self._price_data[ticker] = df

                    # Cache to Supabase
                    if self._client:
                        try:
                            ohlcv_json = self._serialize_ohlcv(df)
                            self._client.table("price_cache").upsert({
                                "ticker": ticker,
                                "start_date": padded_start,
                                "end_date": end_str,
                                "ohlcv_json": ohlcv_json,
                                "row_count": len(df),
                            }).execute()
                        except Exception:
                            pass
                else:
                    logger.debug("No price data returned for %s", ticker)
            except Exception as e:
                logger.debug("Failed to download %s: %s", ticker, e)

        self._loaded = True
        logger.info(
            "Price data loaded: %d/%d tickers",
            len(self._price_data), len(all_tickers),
        )

    # For backward compat with coordinator.py calling download_price_data
    def download_price_data(
        self,
        tickers: list[str],
        start_date: str | pd.Timestamp,
        end_date: str | pd.Timestamp,
    ) -> None:
        """Alias for prefetch_price_data (backward compatibility)."""
        self.prefetch_price_data(tickers, start_date, end_date)

    @staticmethod
    def _serialize_ohlcv(df: pd.DataFrame) -> dict:
        """Serialize a DataFrame to a JSON-safe dict."""
        return {
            "dates": df.index.strftime("%Y-%m-%d").tolist(),
            "Open": [float(x) if pd.notna(x) else None for x in df.get("Open", [])],
            "High": [float(x) if pd.notna(x) else None for x in df.get("High", [])],
            "Low": [float(x) if pd.notna(x) else None for x in df.get("Low", [])],
            "Close": [float(x) if pd.notna(x) else None for x in df.get("Close", [])],
            "Volume": [float(x) if pd.notna(x) else None for x in df.get("Volume", [])],
        }

    @staticmethod
    def _deserialize_ohlcv(data: dict) -> pd.DataFrame | None:
        """Deserialize OHLCV dict back to DataFrame."""
        try:
            dates = pd.to_datetime(data["dates"])
            cols = {}
            for col in ("Open", "High", "Low", "Close", "Volume"):
                if col in data:
                    cols[col] = data[col]
            df = pd.DataFrame(cols, index=dates)
            df.index.name = "Date"
            return df
        except Exception:
            return None

    # ── Price lookup methods ─────────────────────────────────────────

    def get_price_df(self, ticker: str) -> pd.DataFrame | None:
        """Return the full OHLCV DataFrame for a ticker (public version of _get_df)."""
        return self._price_data.get(ticker)

    # Keep _get_df for backward compat (used by f10, f09)
    def _get_df(self, ticker: str) -> pd.DataFrame | None:
        return self._price_data.get(ticker)

    def get_spy_returns(self, date: pd.Timestamp | str) -> float | None:
        """SPY daily return for a given date."""
        df = self._price_data.get("SPY")
        if df is None or "Close" not in df.columns:
            return None
        date = pd.Timestamp(date)
        close = df["Close"]
        if date not in close.index:
            mask = close.index <= date
            if not mask.any():
                return None
            date = close.index[mask][-1]
        idx = close.index.get_loc(date)
        if idx == 0:
            return None
        return float((close.iloc[idx] - close.iloc[idx - 1]) / close.iloc[idx - 1])

    def get_spy_close(self, date: pd.Timestamp | str) -> float | None:
        df = self._price_data.get("SPY")
        if df is None:
            return None
        return self._get_close_at(df, date)

    def get_vix_close(self, date: pd.Timestamp | str) -> float | None:
        df = self._price_data.get("^VIX")
        if df is None:
            return None
        return self._get_close_at(df, date)

    def get_price_at_date(self, ticker: str, date: pd.Timestamp | str) -> float | None:
        df = self._price_data.get(ticker)
        if df is None:
            return None
        return self._get_close_at(df, date)

    def get_ohlcv_at_date(self, ticker: str, date: pd.Timestamp | str) -> dict | None:
        """Return full OHLCV dict for date."""
        df = self._price_data.get(ticker)
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
        df = self._price_data.get(ticker)
        if df is None or "High" not in df.columns:
            return None
        date = pd.Timestamp(date)
        mask = df.index <= date
        recent = df.loc[mask].tail(20)
        if len(recent) < 5:
            return None
        return float(recent["High"].max())

    def get_52w_range(self, ticker: str, date: pd.Timestamp | str) -> tuple[float, float] | None:
        df = self._price_data.get(ticker)
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
        df = self._price_data.get(ticker)
        if df is None or "Close" not in df.columns:
            return None
        date = pd.Timestamp(date)
        mask = df.index <= date
        recent = df.loc[mask].tail(20)
        if len(recent) < 10:
            return None
        return float(recent["Close"].mean())

    def get_relative_volume(self, ticker: str, date: pd.Timestamp | str) -> float | None:
        df = self._price_data.get(ticker)
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
        df = self._price_data.get(ticker)
        if df is None or "Close" not in df.columns or len(df) < 30:
            return False
        date = pd.Timestamp(date)
        close = df["Close"]
        returns = close.pct_change().abs()
        avg_move = returns.rolling(20).mean()

        start = date - pd.Timedelta(days=window)
        end = date + pd.Timedelta(days=window)
        mask = (returns.index >= start) & (returns.index <= end)
        window_returns = returns.loc[mask]
        window_avg = avg_move.loc[mask]

        if len(window_returns) == 0 or window_avg.isna().all():
            return False

        for idx in window_returns.index:
            if idx in window_avg.index:
                ret = window_returns[idx]
                avg = window_avg[idx]
                if pd.notna(ret) and pd.notna(avg) and avg > 0 and ret > 3 * avg:
                    return True
        return False

    def get_spy_20d_return(self, date: pd.Timestamp | str) -> float | None:
        """SPY cumulative return over prior 20 trading days."""
        df = self._price_data.get("SPY")
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
        df = self._price_data.get(ticker)
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
        df = self._price_data.get(ticker)
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
