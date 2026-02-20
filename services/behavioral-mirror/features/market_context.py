"""Backward-compatible MarketContext — delegates to MarketDataService.

All price-data and classification logic now lives in
``services.market_data.MarketDataService``.  This module re-exports the
class under the old ``MarketContext`` name so that any remaining imports
continue to work.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from services.market_data import MarketDataService

    # Alias: code that does ``from features.market_context import MarketContext``
    # now gets the new service transparently.
    MarketContext = MarketDataService
except ImportError:
    logger.warning(
        "services.market_data not available — falling back to stub MarketContext"
    )

    class MarketContext:  # type: ignore[no-redef]
        """Minimal stub when MarketDataService is not importable."""

        def __init__(self) -> None:
            self._loaded = False

        @property
        def is_loaded(self) -> bool:
            return self._loaded

        def download_price_data(self, *a, **kw) -> None:
            self._loaded = True

        def __getattr__(self, name: str):
            # Return None-returning callable for any lookup method
            return lambda *a, **kw: None


def download_price_data(tickers, start_date, end_date):
    """Convenience: create a MarketContext and download data."""
    ctx = MarketContext()
    if hasattr(ctx, "prefetch_price_data"):
        ctx.prefetch_price_data(tickers, start_date, end_date)
    elif hasattr(ctx, "download_price_data"):
        ctx.download_price_data(tickers, start_date, end_date)
    return ctx
