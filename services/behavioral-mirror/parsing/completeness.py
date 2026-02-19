"""Portfolio completeness assessment — detects signals of missing data.

After all transactions are parsed and positions tracked, this module
scans for evidence that more data exists than what was uploaded.

CRITICAL: This module does NOT estimate or guess the total portfolio
value. It identifies what's missing and asks the user to provide it.
We only analyse what we can actually see.

Signal types and their weights are loaded from Supabase
``completeness_signal_types`` table, with hardcoded fallbacks.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Module-level cache
_cached_signal_types: dict[str, dict[str, Any]] | None = None


# ---------------------------------------------------------------------------
# Hardcoded fallback signal types
# ---------------------------------------------------------------------------

_FALLBACK_SIGNAL_TYPES: dict[str, dict[str, Any]] = {
    "dividend_no_buy": {
        "signal_name": "Dividend from untraded position",
        "description": "Dividends received for a ticker with no buy in the CSV window",
        "weight": 1.0,
    },
    "interest_no_buy": {
        "signal_name": "Interest from untraded bond",
        "description": "Bond interest for a CUSIP not purchased in the CSV window",
        "weight": 1.0,
    },
    "option_no_underlying": {
        "signal_name": "Options on unseen underlying",
        "description": "Option activity on an underlying not in the position tracker",
        "weight": 0.8,
    },
    "advisory_fee_implies_aum": {
        "signal_name": "Advisory fee implies larger AUM",
        "description": "Advisory fee proportional to a larger AUM than reconstructed",
        "weight": 1.5,
    },
    "wire_transfer": {
        "signal_name": "Wire / external transfer",
        "description": "Wire or ACH transfer suggesting external holdings",
        "weight": 0.5,
    },
    "inter_account_transfer": {
        "signal_name": "Inter-account transfer",
        "description": "Position existed before the CSV window (transferred between accounts)",
        "weight": 0.7,
    },
}


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def load_signal_types() -> dict[str, dict[str, Any]]:
    """Load completeness signal type definitions from Supabase."""
    global _cached_signal_types
    if _cached_signal_types is not None:
        return _cached_signal_types

    try:
        from storage.supabase_client import _get_client

        client = _get_client()
        if client is None:
            raise RuntimeError("Supabase not configured")

        resp = (
            client.table("completeness_signal_types")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        if resp.data:
            _cached_signal_types = {
                row["signal_key"]: row for row in resp.data
            }
            logger.info(
                "[COMPLETENESS] Loaded %d signal types from Supabase",
                len(_cached_signal_types),
            )
            return _cached_signal_types
    except Exception:
        logger.debug(
            "[COMPLETENESS] Supabase unavailable, using fallback signal types",
            exc_info=True,
        )

    _cached_signal_types = _FALLBACK_SIGNAL_TYPES
    return _cached_signal_types


def reset_cache() -> None:
    """Clear the cached signal types (for testing)."""
    global _cached_signal_types
    _cached_signal_types = None


# ---------------------------------------------------------------------------
# Main assessment
# ---------------------------------------------------------------------------


def assess_completeness(
    transactions: list[dict[str, Any]],
    positions: dict[str, Any],
    reconstructed_value: float,
) -> dict[str, Any]:
    """Assess portfolio data completeness.

    Parameters
    ----------
    transactions : list[dict]
        Parsed transactions. Each must have at least: action, symbol/ticker,
        amount, description.
    positions : dict
        All positions from PositionTracker.get_all_positions().
    reconstructed_value : float
        Sum of absolute amounts for buy/sell transactions — the value
        we can directly see.

    Returns
    -------
    dict with:
        completeness_confidence, reconstructed_value, invisible_holdings,
        signals, prompt_for_more_data, user_message
    """
    signal_types = load_signal_types()
    signals: list[dict[str, Any]] = []

    # Track which tickers had buy activity
    bought_tickers: set[str] = set()
    sold_tickers: set[str] = set()
    option_underlyings: set[str] = set()
    dividend_tickers: dict[str, float] = {}
    interest_cusips: dict[str, float] = {}
    wire_transfers: list[dict[str, Any]] = []
    advisory_fees: list[dict[str, Any]] = []
    inter_account_transfers: list[dict[str, Any]] = []

    for txn in transactions:
        action = (txn.get("action") or "").lower()
        ticker = (txn.get("ticker") or txn.get("symbol") or "").upper().strip()
        amount = float(txn.get("amount", 0) or 0)
        description = (txn.get("description") or "").lower()
        inst_type = (txn.get("instrument_type") or "").lower()

        if action == "buy":
            bought_tickers.add(ticker)
        elif action == "sell":
            sold_tickers.add(ticker)

        if action == "dividend":
            dividend_tickers[ticker] = dividend_tickers.get(ticker, 0) + abs(amount)

        if action == "interest" and ticker.startswith("CUSIP-"):
            interest_cusips[ticker] = interest_cusips.get(ticker, 0) + abs(amount)

        if inst_type == "options":
            # Extract underlying from option ticker
            underlying = _extract_underlying(ticker)
            if underlying:
                option_underlyings.add(underlying)

        if action == "transfer":
            desc_lower = description.lower()
            if "wire" in desc_lower or "ach" in desc_lower:
                wire_transfers.append({"ticker": ticker, "amount": amount, "description": description})
            elif "journal" in desc_lower:
                inter_account_transfers.append({"ticker": ticker, "amount": amount})

        if action == "fee" and "advisory" in description:
            advisory_fees.append({"amount": abs(amount), "description": description})

    invisible_equity: list[str] = []
    invisible_bonds: list[str] = []

    # Signal 1: Dividends from tickers with NO buy activity
    if "dividend_no_buy" in signal_types:
        for ticker, div_amount in dividend_tickers.items():
            if ticker not in bought_tickers and ticker != "CASH":
                signals.append({
                    "type": "dividend_no_buy",
                    "ticker": ticker,
                    "amount": div_amount,
                })
                invisible_equity.append(ticker)

    # Signal 2: Interest from bonds not purchased in window
    if "interest_no_buy" in signal_types:
        for cusip, int_amount in interest_cusips.items():
            if cusip not in bought_tickers:
                signals.append({
                    "type": "interest_no_buy",
                    "cusip": cusip,
                    "amount": int_amount,
                })
                invisible_bonds.append(cusip)

    # Signal 3: Options on underlyings not in position tracker
    if "option_no_underlying" in signal_types:
        for underlying in option_underlyings:
            if underlying not in bought_tickers and underlying not in sold_tickers:
                # Check if it exists in positions
                has_position = any(
                    underlying in key for key in positions
                )
                if not has_position:
                    signals.append({
                        "type": "option_no_underlying",
                        "underlying": underlying,
                    })
                    if underlying not in invisible_equity:
                        invisible_equity.append(underlying)

    # Signal 4: Wire transfers
    if "wire_transfer" in signal_types:
        for wt in wire_transfers:
            if abs(wt["amount"]) > 0:
                signals.append({
                    "type": "wire_transfer",
                    "source": wt.get("description", ""),
                    "amount": wt["amount"],
                })

    # Signal 5: Advisory fees implying larger AUM
    if "advisory_fee_implies_aum" in signal_types:
        for fee_item in advisory_fees:
            fee_amount = fee_item["amount"]
            if fee_amount > 0:
                # Typical advisory fee is ~1% annually (0.25% quarterly)
                implied_aum = fee_amount / 0.0025  # quarterly fee
                if implied_aum > reconstructed_value * 1.5:
                    signals.append({
                        "type": "advisory_fee_implies_aum",
                        "fee": fee_amount,
                        "implied_aum": round(implied_aum, 2),
                    })

    # Signal 6: Inter-account transfers
    if "inter_account_transfer" in signal_types:
        for iat in inter_account_transfers:
            signals.append({
                "type": "inter_account_transfer",
                "ticker": iat["ticker"],
                "amount": iat["amount"],
            })

    # Determine completeness
    total_invisible = len(invisible_equity) + len(invisible_bonds)
    prompt_for_more = total_invisible > 0 or any(
        s["type"] == "advisory_fee_implies_aum" for s in signals
    )

    if total_invisible == 0 and not prompt_for_more:
        completeness = "full"
    else:
        completeness = "partial"

    # Build user message
    user_message = None
    if prompt_for_more:
        parts = []
        if reconstructed_value > 0:
            parts.append(
                f"Your activity shows trades worth ~${reconstructed_value:,.0f}"
            )
        if total_invisible > 0:
            parts.append(
                f"but dividend and interest data suggest {total_invisible} "
                f"additional positions not visible in this export"
            )
        aum_signals = [s for s in signals if s["type"] == "advisory_fee_implies_aum"]
        if aum_signals:
            implied = aum_signals[0].get("implied_aum", 0)
            parts.append(
                f"and advisory fees suggest a total portfolio around "
                f"${implied:,.0f}"
            )
        if parts:
            user_message = (
                ". ".join(parts) + ". "
                "Upload a holdings screenshot to unlock your complete profile."
            )

    return {
        "completeness_confidence": completeness,
        "reconstructed_value": round(reconstructed_value, 2),
        "invisible_holdings": {
            "equity_tickers": invisible_equity,
            "bond_cusips": invisible_bonds,
            "count": total_invisible,
        },
        "signals": signals,
        "prompt_for_more_data": prompt_for_more,
        "user_message": user_message,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_underlying(option_ticker: str) -> str | None:
    """Extract the equity underlying from an option symbol.

    WFA format: {TICKER}{YY}{DD}{MONTH_CODE}{STRIKE}
    e.g. NVDA2620C240 → NVDA
    """
    import re

    m = re.match(r"^([A-Z]+)\d{2}\d{2}[A-X]\d+$", option_ticker)
    if m:
        return m.group(1)
    # OCC format: AAPL240119C00150000
    m = re.match(r"^([A-Z]+)\d{6}[CP]\d+$", option_ticker)
    if m:
        return m.group(1)
    return None
