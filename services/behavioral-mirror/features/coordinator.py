"""Coordinator: calls all 15 feature modules and merges into one 212-feature vector."""

from __future__ import annotations

import logging
import time
from typing import Any

import pandas as pd

from features.utils import build_position_history

logger = logging.getLogger(__name__)

# Module imports — each has an extract(trades_df, positions, market_data) -> dict
from features import (
    f01_timing,
    f02_sizing,
    f03_holding,
    f04_entry,
    f05_exit,
    f06_psychology,
    f07_instruments,
    f08_sectors,
    f09_portfolio,
    f10_market_awareness,
    f11_risk,
    f12_biases,
    f13_social,
    f14_learning,
    f15_signature,
)

_MODULES: list[tuple[str, Any]] = [
    ("timing", f01_timing),
    ("sizing", f02_sizing),
    ("holding", f03_holding),
    ("entry", f04_entry),
    ("exit", f05_exit),
    ("psych", f06_psychology),
    ("instrument", f07_instruments),
    ("sector", f08_sectors),
    ("portfolio", f09_portfolio),
    ("market", f10_market_awareness),
    ("risk", f11_risk),
    ("bias", f12_biases),
    ("social", f13_social),
    ("learning", f14_learning),
    ("sig", f15_signature),
]


def extract_all_features(
    trades_df: pd.DataFrame,
    market_data: Any = None,
    raw_trades_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Extract all 212 behavioral features from a parsed trades DataFrame.

    Args:
        trades_df: DataFrame with columns: ticker, action, quantity, price, date, fees.
                   The 'date' column should be parseable as datetime.
        market_data: MarketDataService instance. If None, one is created automatically.
        raw_trades_df: Optional unfiltered DataFrame with instrument_type column.
                       Used for options trade counts in sophistication scoring.

    Returns:
        Flat dict with 212 keys, prefixed by dimension (timing_*, sizing_*, etc.).
    """
    t0 = time.time()

    # Ensure date is datetime
    if not pd.api.types.is_datetime64_any_dtype(trades_df["date"]):
        trades_df = trades_df.copy()
        trades_df["date"] = pd.to_datetime(trades_df["date"], errors="coerce")
    trades_df = trades_df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    if len(trades_df) == 0:
        logger.warning("No valid trades in DataFrame")
        return {}

    # Step 1: Initialize MarketDataService if not provided
    if market_data is None:
        try:
            from services.market_data import MarketDataService
            market_data = MarketDataService()
        except Exception as e:
            logger.warning("Failed to create MarketDataService: %s", e)
            # Fall back to legacy MarketContext
            from features.market_context import MarketContext
            market_data = MarketContext()

    # Step 2: Prefetch market data for all tickers + SPY + VIX
    tickers = trades_df["ticker"].unique().tolist()
    start_date = trades_df["date"].min()
    end_date = trades_df["date"].max() + pd.Timedelta(days=1)

    try:
        if hasattr(market_data, "prefetch_tickers"):
            market_data.prefetch_tickers(tickers)
        if hasattr(market_data, "prefetch_price_data"):
            market_data.prefetch_price_data(tickers, start_date, end_date)
        elif hasattr(market_data, "download_price_data"):
            market_data.download_price_data(tickers, start_date, end_date)
    except Exception as e:
        logger.warning("Market data download failed (features will be partial): %s", e)

    # Step 3: Build position history
    positions = build_position_history(trades_df)

    # Step 4: Call each module
    all_features: dict[str, Any] = {}
    module_errors: list[str] = []

    for prefix, module in _MODULES:
        try:
            features = module.extract(trades_df, positions, market_data)
            # Verify all keys have the correct prefix
            for key, value in features.items():
                if not key.startswith(prefix + "_"):
                    key = f"{prefix}_{key}"
                all_features[key] = value
        except Exception as e:
            logger.exception("Module %s failed: %s", prefix, e)
            module_errors.append(f"{prefix}: {e}")

    # Step 5: Summary
    total = len(all_features)
    null_count = sum(1 for v in all_features.values() if v is None)
    computed = total - null_count
    elapsed = time.time() - t0

    logger.info(
        "Computed %d/%d features (%d null due to insufficient data) in %.1fs",
        computed, total, null_count, elapsed,
    )
    if module_errors:
        logger.warning("Module errors: %s", module_errors)

    # Options counts from unfiltered trades (for sophistication scoring)
    if raw_trades_df is not None and "instrument_type" in raw_trades_df.columns:
        total_raw = len(raw_trades_df)
        options_mask = raw_trades_df["instrument_type"] == "options"
        options_count = int(options_mask.sum())
        all_features["portfolio_total_options_trades"] = options_count
        all_features["portfolio_options_pct"] = round(options_count / total_raw, 4) if total_raw > 0 else 0.0
        all_features["portfolio_unique_instrument_types"] = int(raw_trades_df["instrument_type"].nunique())
        logger.info(
            "Raw trades: %d total, %d options (%.1f%%), %d instrument types",
            total_raw, options_count,
            (options_count / total_raw * 100) if total_raw > 0 else 0,
            all_features["portfolio_unique_instrument_types"],
        )

    # Trade count for narrative generator confidence tier
    all_features["portfolio_total_round_trips"] = len(trades_df)

    # Add metadata
    all_features["_meta_total_features"] = total
    all_features["_meta_computed_features"] = computed
    all_features["_meta_null_features"] = null_count
    all_features["_meta_extraction_time_seconds"] = round(elapsed, 2)
    all_features["_meta_module_errors"] = module_errors if module_errors else None

    return all_features


def get_features_grouped(features: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Group a flat feature dict by dimension prefix for structured output."""
    grouped: dict[str, dict[str, Any]] = {}
    for key, value in features.items():
        if key.startswith("_meta_"):
            grouped.setdefault("_meta", {})[key] = value
            continue
        parts = key.split("_", 1)
        if len(parts) == 2:
            prefix, name = parts
            grouped.setdefault(prefix, {})[key] = value
        else:
            grouped.setdefault("other", {})[key] = value
    return grouped
