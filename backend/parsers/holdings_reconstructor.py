"""
Holdings reconstructor: rebuild position history from parsed transactions.

Takes a list of ParsedTransaction objects and produces:
- Per-symbol position tracking (quantity, cost basis, dividends, fees)
- Detection of pre-existing positions (sells without prior buys)
- Account-level summaries (total invested, total withdrawn, fees, dividends)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .instrument_classifier import InstrumentClassification, classify
from .wfa_activity import ParsedTransaction


@dataclass
class PositionRecord:
    """Tracks a single position (symbol) through time."""

    symbol: str
    description: str
    instrument: InstrumentClassification
    account: str
    account_type: str

    # Running totals
    quantity: float = 0.0
    cost_basis: float = 0.0  # total $ spent buying
    realized_proceeds: float = 0.0  # total $ received from sells
    dividends: float = 0.0
    interest: float = 0.0
    fees: float = 0.0

    # Transaction counts
    buy_count: int = 0
    sell_count: int = 0
    dividend_count: int = 0

    # Timing
    first_transaction: Optional[datetime] = None
    last_transaction: Optional[datetime] = None

    # Pre-existing flag: True if we saw a sell before any buy
    pre_existing: bool = False

    # Transaction log
    transactions: list[ParsedTransaction] = field(default_factory=list)

    @property
    def realized_pnl(self) -> float:
        """Realized P&L from closed positions."""
        return self.realized_proceeds - self.cost_basis

    @property
    def total_return(self) -> float:
        """Total return including dividends and interest, minus fees."""
        return self.realized_pnl + self.dividends + self.interest - self.fees

    def _update_timestamps(self, dt: datetime) -> None:
        if self.first_transaction is None or dt < self.first_transaction:
            self.first_transaction = dt
        if self.last_transaction is None or dt > self.last_transaction:
            self.last_transaction = dt


@dataclass
class AccountSummary:
    """Aggregate stats for one account."""

    account: str
    account_type: str
    total_bought: float = 0.0
    total_sold: float = 0.0
    total_dividends: float = 0.0
    total_interest: float = 0.0
    total_fees: float = 0.0
    total_transfers_in: float = 0.0
    total_transfers_out: float = 0.0
    transaction_count: int = 0
    unique_symbols: int = 0
    first_date: Optional[datetime] = None
    last_date: Optional[datetime] = None

    @property
    def net_investment(self) -> float:
        return self.total_bought - self.total_sold

    @property
    def net_transfers(self) -> float:
        return self.total_transfers_in - self.total_transfers_out


@dataclass
class HoldingsSnapshot:
    """Complete output of the holdings reconstruction."""

    positions: dict[str, PositionRecord]  # keyed by "account|symbol"
    accounts: dict[str, AccountSummary]
    pre_existing_positions: list[PositionRecord]
    instrument_breakdown: dict[str, int]  # instrument_type -> count of positions
    total_transactions: int = 0
    date_range: tuple[Optional[datetime], Optional[datetime]] = (None, None)


# ---------------------------------------------------------------------------
# Main reconstruction
# ---------------------------------------------------------------------------

def reconstruct(transactions: list[ParsedTransaction]) -> HoldingsSnapshot:
    """
    Reconstruct holdings from a chronologically-sorted list of transactions.

    Returns a HoldingsSnapshot with per-position tracking, account summaries,
    and pre-existing position detection.
    """
    # Sort by date to ensure chronological processing
    sorted_txns = sorted(transactions, key=lambda t: t.date)

    positions: dict[str, PositionRecord] = {}
    accounts: dict[str, AccountSummary] = {}
    instrument_counts: dict[str, int] = defaultdict(int)

    earliest: Optional[datetime] = None
    latest: Optional[datetime] = None

    for txn in sorted_txns:
        # Update global date range
        if earliest is None or txn.date < earliest:
            earliest = txn.date
        if latest is None or txn.date > latest:
            latest = txn.date

        # Get or create account summary
        acct = _get_or_create_account(accounts, txn)
        acct.transaction_count += 1
        _update_account_dates(acct, txn.date)

        # Get or create position
        pos_key = f"{txn.account}|{txn.symbol}"
        pos = _get_or_create_position(positions, pos_key, txn)
        pos.transactions.append(txn)
        pos._update_timestamps(txn.date)

        # Process by action type
        if txn.action == "buy":
            _process_buy(pos, acct, txn)
        elif txn.action == "sell":
            _process_sell(pos, acct, txn)
        elif txn.action == "dividend":
            _process_dividend(pos, acct, txn)
        elif txn.action == "interest":
            _process_interest(pos, acct, txn)
        elif txn.action == "fee":
            _process_fee(pos, acct, txn)
        elif txn.action == "transfer":
            _process_transfer(acct, txn)

        # Always accumulate fees from the fee column
        if txn.fees > 0:
            pos.fees += txn.fees
            acct.total_fees += txn.fees

    # Count unique symbols per account
    symbols_per_account: dict[str, set[str]] = defaultdict(set)
    for key, pos in positions.items():
        symbols_per_account[pos.account].add(pos.symbol)
        instrument_counts[pos.instrument.instrument_type] += 1

    for acct_name, syms in symbols_per_account.items():
        if acct_name in accounts:
            accounts[acct_name].unique_symbols = len(syms)

    # Identify pre-existing positions
    pre_existing = [p for p in positions.values() if p.pre_existing]

    return HoldingsSnapshot(
        positions=positions,
        accounts=accounts,
        pre_existing_positions=pre_existing,
        instrument_breakdown=dict(instrument_counts),
        total_transactions=len(sorted_txns),
        date_range=(earliest, latest),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_account(
    accounts: dict[str, AccountSummary], txn: ParsedTransaction
) -> AccountSummary:
    if txn.account not in accounts:
        accounts[txn.account] = AccountSummary(
            account=txn.account,
            account_type=txn.account_type,
        )
    return accounts[txn.account]


def _get_or_create_position(
    positions: dict[str, PositionRecord],
    key: str,
    txn: ParsedTransaction,
) -> PositionRecord:
    if key not in positions:
        inst = classify(txn.symbol, txn.description, txn.raw_action)
        positions[key] = PositionRecord(
            symbol=txn.symbol,
            description=txn.description,
            instrument=inst,
            account=txn.account,
            account_type=txn.account_type,
        )
    return positions[key]


def _update_account_dates(acct: AccountSummary, dt: datetime) -> None:
    if acct.first_date is None or dt < acct.first_date:
        acct.first_date = dt
    if acct.last_date is None or dt > acct.last_date:
        acct.last_date = dt


def _process_buy(pos: PositionRecord, acct: AccountSummary, txn: ParsedTransaction) -> None:
    pos.quantity += abs(txn.quantity)
    pos.cost_basis += abs(txn.amount)
    pos.buy_count += 1
    acct.total_bought += abs(txn.amount)


def _process_sell(pos: PositionRecord, acct: AccountSummary, txn: ParsedTransaction) -> None:
    # Detect pre-existing position: selling something we never bought
    if pos.buy_count == 0 and pos.quantity == 0:
        pos.pre_existing = True

    pos.quantity -= abs(txn.quantity)
    pos.realized_proceeds += abs(txn.amount)
    pos.sell_count += 1
    acct.total_sold += abs(txn.amount)


def _process_dividend(pos: PositionRecord, acct: AccountSummary, txn: ParsedTransaction) -> None:
    pos.dividends += abs(txn.amount)
    pos.dividend_count += 1
    acct.total_dividends += abs(txn.amount)


def _process_interest(pos: PositionRecord, acct: AccountSummary, txn: ParsedTransaction) -> None:
    pos.interest += abs(txn.amount)
    acct.total_interest += abs(txn.amount)


def _process_fee(pos: PositionRecord, acct: AccountSummary, txn: ParsedTransaction) -> None:
    pos.fees += abs(txn.amount)
    acct.total_fees += abs(txn.amount)


def _process_transfer(acct: AccountSummary, txn: ParsedTransaction) -> None:
    if txn.amount >= 0:
        acct.total_transfers_in += abs(txn.amount)
    else:
        acct.total_transfers_out += abs(txn.amount)
