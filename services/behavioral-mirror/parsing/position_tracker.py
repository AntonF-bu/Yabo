"""Position inventory tracker — tracks running positions per account+ticker.

Processes transactions chronologically and answers: "at the time of this
transaction, what did this account already hold?"

This module is GENERAL-PURPOSE — works for any brokerage, any instrument.
All rules/thresholds that could change are loaded from Supabase at startup.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Running inventory for a single account+ticker."""

    ticker: str
    account: str
    quantity: float = 0.0
    cost_basis: float = 0.0
    instrument_type: str = "equity"  # equity | options | bond | unknown
    last_updated_idx: int = -1

    @property
    def direction(self) -> str:
        if self.quantity > 0:
            return "long"
        if self.quantity < 0:
            return "short"
        return "flat"


class PositionTracker:
    """Track running position inventory as transactions are processed.

    Usage::

        tracker = PositionTracker()
        for txn in sorted_transactions:
            enrichment = tracker.process_transaction(txn)
            # enrichment has is_closing, is_opening, prior_position_qty, etc.
    """

    def __init__(self) -> None:
        # {(account, ticker): Position}
        self._positions: dict[tuple[str, str], Position] = {}
        self._txn_count = 0
        self._accounts: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_transaction(self, txn: dict[str, Any]) -> dict[str, Any]:
        """Process one transaction and return position-context enrichment.

        Parameters
        ----------
        txn : dict
            Must have at least: action, symbol (or ticker), quantity.
            Optional: account, instrument_type, price, amount.

        Returns
        -------
        dict with keys:
            is_closing, is_opening, prior_position_qty,
            remaining_position_qty, position_direction
        """
        account = txn.get("account", txn.get("account_id", "default"))
        ticker = (txn.get("ticker") or txn.get("symbol") or "").upper().strip()
        action = (txn.get("action") or "").lower()
        raw_qty = float(txn.get("quantity", 0) or 0)
        inst_type = (txn.get("instrument_type") or "equity").lower()

        self._accounts.add(account)
        self._txn_count += 1

        # Non-trade actions don't affect position inventory
        if action not in ("buy", "sell"):
            return self._no_change_enrichment(account, ticker)

        key = (account, ticker)
        pos = self._positions.get(key)
        if pos is None:
            pos = Position(ticker=ticker, account=account, instrument_type=inst_type)
            self._positions[key] = pos

        prior_qty = pos.quantity
        prior_direction = pos.direction

        # Determine signed delta:
        #   buy  → positive qty added
        #   sell → negative qty removed
        qty = abs(raw_qty)
        if action == "buy":
            signed_delta = qty
        else:  # sell
            signed_delta = -qty

        # Update position
        pos.quantity += signed_delta
        pos.last_updated_idx = self._txn_count

        # Update cost basis (simple average)
        price = float(txn.get("price", 0) or 0)
        if action == "buy" and price > 0 and qty > 0:
            pos.cost_basis = (
                (pos.cost_basis * max(prior_qty, 0) + price * qty)
                / max(pos.quantity, 1)
            )

        remaining_qty = pos.quantity
        new_direction = pos.direction

        # Classify the trade
        is_closing = False
        is_opening = False
        partial_close_short_open = False

        if action == "sell":
            if prior_qty > 0:
                # Had a long position
                if qty <= prior_qty:
                    # Selling within existing long → closing
                    is_closing = True
                else:
                    # Selling more than we hold → partial close + possible short
                    is_closing = True
                    partial_close_short_open = True
            elif prior_qty <= 0:
                # No long position or already short → opening short
                is_opening = True
        elif action == "buy":
            if prior_qty < 0:
                # Had a short → buying to cover
                if qty <= abs(prior_qty):
                    is_closing = True
                else:
                    is_closing = True
                    partial_close_short_open = True
            elif prior_qty >= 0:
                # No short → opening or adding to long
                is_opening = True

        return {
            "is_closing": is_closing,
            "is_opening": is_opening,
            "prior_position_qty": prior_qty,
            "remaining_position_qty": remaining_qty,
            "position_direction": new_direction,
            "prior_direction": prior_direction,
            "partial_close_short_open": partial_close_short_open,
        }

    def get_position(self, account: str, ticker: str) -> dict[str, Any]:
        """Return current position for account+ticker."""
        key = (account, ticker.upper().strip())
        pos = self._positions.get(key)
        if pos is None:
            return {"ticker": ticker, "account": account, "quantity": 0, "direction": "flat"}
        return {
            "ticker": pos.ticker,
            "account": pos.account,
            "quantity": pos.quantity,
            "cost_basis": pos.cost_basis,
            "direction": pos.direction,
            "instrument_type": pos.instrument_type,
        }

    def get_all_positions(self, account: Optional[str] = None) -> dict[str, Any]:
        """Return all positions, optionally filtered by account.

        Returns
        -------
        dict keyed by ``(account, ticker)`` tuples with position info.
        """
        result: dict[str, Any] = {}
        for (acct, ticker), pos in self._positions.items():
            if account is not None and acct != account:
                continue
            label = f"{acct}:{ticker}"
            result[label] = {
                "ticker": pos.ticker,
                "account": pos.account,
                "quantity": pos.quantity,
                "cost_basis": pos.cost_basis,
                "direction": pos.direction,
                "instrument_type": pos.instrument_type,
            }
        return result

    def get_equity_positions(self, account: str) -> dict[str, float]:
        """Return {ticker: qty} of non-zero equity positions for an account."""
        result: dict[str, float] = {}
        for (acct, ticker), pos in self._positions.items():
            if acct != account:
                continue
            if pos.instrument_type in ("equity", "etf") and pos.quantity != 0:
                result[ticker] = pos.quantity
        return result

    def get_option_positions(self, account: str) -> list[dict[str, Any]]:
        """Return option positions for an account."""
        result: list[dict[str, Any]] = []
        for (acct, ticker), pos in self._positions.items():
            if acct != account or pos.instrument_type != "options":
                continue
            if pos.quantity != 0:
                result.append({
                    "ticker": ticker,
                    "quantity": pos.quantity,
                    "direction": pos.direction,
                    "cost_basis": pos.cost_basis,
                })
        return result

    @property
    def stats(self) -> dict[str, Any]:
        """Summary statistics for logging."""
        non_zero = sum(1 for p in self._positions.values() if p.quantity != 0)
        return {
            "transactions_processed": self._txn_count,
            "accounts": len(self._accounts),
            "unique_positions": len(self._positions),
            "non_zero_positions": non_zero,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _no_change_enrichment(self, account: str, ticker: str) -> dict[str, Any]:
        """Return enrichment for non-trade transactions."""
        key = (account, ticker)
        pos = self._positions.get(key)
        qty = pos.quantity if pos else 0
        direction = pos.direction if pos else "flat"
        return {
            "is_closing": False,
            "is_opening": False,
            "prior_position_qty": qty,
            "remaining_position_qty": qty,
            "position_direction": direction,
            "prior_direction": direction,
            "partial_close_short_open": False,
        }
