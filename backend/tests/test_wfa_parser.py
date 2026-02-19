"""
Test script for WFA Activity Parser pipeline.

Usage:
    # From project root, with a CSV in backend/test-data/:
    python -m backend.tests.test_wfa_parser

    # Or point at any CSV:
    python -m backend.tests.test_wfa_parser /path/to/activity.csv
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from backend.parsers.wfa_activity import WFAActivityParser
from backend.parsers.instrument_classifier import classify, parse_option_symbol
from backend.parsers.holdings_reconstructor import reconstruct


def find_csv() -> Path:
    """Find a test CSV file, checking args first, then test-data/ folder."""
    # Check command-line argument
    if len(sys.argv) > 1:
        p = Path(sys.argv[1])
        if p.exists():
            return p
        print(f"ERROR: File not found: {p}")
        sys.exit(1)

    # Check test-data folder
    test_data = Path(__file__).resolve().parent.parent / "test-data"
    csvs = sorted(test_data.glob("*.csv"))
    if csvs:
        return csvs[0]

    print("ERROR: No CSV file found.")
    print(f"  - Place a WFA activity CSV in: {test_data}/")
    print(f"  - Or pass a path: python -m backend.tests.test_wfa_parser /path/to/file.csv")
    sys.exit(1)


def fmt_dollar(amount: float) -> str:
    """Format a dollar amount with sign."""
    if amount < 0:
        return f"-${abs(amount):,.2f}"
    return f"${amount:,.2f}"


def main() -> None:
    csv_path = find_csv()

    print("=" * 70)
    print(f"  WFA Activity Parser - Test Run")
    print(f"  File: {csv_path.name}")
    print("=" * 70)

    # ----- Step 1: Parse -----
    parser = WFAActivityParser()
    transactions = parser.parse_csv(csv_path)

    print(f"\n{'PARSING RESULTS':=^70}")
    print(f"  Total rows scanned:    {parser.total_rows}")
    print(f"  Transactions parsed:   {len(transactions)}")
    print(f"  Rows skipped:          {parser.skipped_rows}")
    print(f"  Accounts found:        {len(parser.accounts)}")

    if not transactions:
        print("\n  No transactions found. Check CSV format.")
        return

    # ----- Step 2: Transaction summary -----
    action_counts: dict[str, int] = defaultdict(int)
    action_amounts: dict[str, float] = defaultdict(float)

    for txn in transactions:
        action_counts[txn.action] += 1
        action_amounts[txn.action] += txn.amount

    print(f"\n{'TRANSACTION BREAKDOWN':=^70}")
    print(f"  {'Action':<15} {'Count':>8} {'Total Amount':>18}")
    print(f"  {'-' * 43}")
    for action in sorted(action_counts.keys()):
        print(f"  {action:<15} {action_counts[action]:>8} {fmt_dollar(action_amounts[action]):>18}")

    # ----- Step 3: Accounts -----
    print(f"\n{'ACCOUNTS':=^70}")
    accounts_seen: dict[str, dict] = {}
    for txn in transactions:
        if txn.account not in accounts_seen:
            accounts_seen[txn.account] = {
                "type": txn.account_type,
                "count": 0,
                "first": txn.date,
                "last": txn.date,
            }
        info = accounts_seen[txn.account]
        info["count"] += 1
        if txn.date < info["first"]:
            info["first"] = txn.date
        if txn.date > info["last"]:
            info["last"] = txn.date

    for name, info in accounts_seen.items():
        print(f"\n  Account: {name}")
        print(f"    Type:         {info['type']}")
        print(f"    Transactions: {info['count']}")
        print(f"    Date range:   {info['first'].strftime('%Y-%m-%d')} to {info['last'].strftime('%Y-%m-%d')}")

    # ----- Step 4: Instrument classification -----
    print(f"\n{'INSTRUMENT BREAKDOWN':=^70}")
    symbols_seen: dict[str, set] = defaultdict(set)
    for txn in transactions:
        if txn.symbol and txn.symbol != "CASH":
            cls = classify(txn.symbol, txn.description, txn.raw_action)
            symbols_seen[cls.instrument_type].add(txn.symbol)

    print(f"  {'Type':<18} {'Unique Symbols':>16}")
    print(f"  {'-' * 36}")
    for itype in sorted(symbols_seen.keys()):
        syms = symbols_seen[itype]
        print(f"  {itype:<18} {len(syms):>16}")
        # Show first few symbols
        preview = sorted(syms)[:8]
        print(f"    {', '.join(preview)}{'...' if len(syms) > 8 else ''}")

    # ----- Step 4b: Option symbol parsing verification -----
    _MONTH_NAMES = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
                    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
    option_symbols = sorted({txn.symbol for txn in transactions
                             if txn.symbol != "CASH"
                             and classify(txn.symbol, txn.description, txn.raw_action).instrument_type == "options"})
    if option_symbols:
        print(f"\n{'OPTION SYMBOL PARSING':=^70}")
        print(f"  {'Symbol':<18} {'Underlying':<8} {'Type':<6} {'Strike':>8} {'Expiry':>14}")
        print(f"  {'-' * 56}")
        for sym in option_symbols:
            opt = parse_option_symbol(sym)
            if opt:
                expiry = f"{_MONTH_NAMES[opt.expiry_month]} {opt.expiry_day}, {opt.expiry_year}"
                print(f"  {sym:<18} {opt.underlying:<8} {opt.option_type:<6} ${opt.strike:>7.0f} {expiry:>14}")
            else:
                print(f"  {sym:<18} (could not parse)")

    # ----- Step 5: Holdings reconstruction -----
    print(f"\n{'HOLDINGS RECONSTRUCTION':=^70}")
    snapshot = reconstruct(transactions)

    print(f"  Total positions tracked: {len(snapshot.positions)}")
    print(f"  Pre-existing positions:  {len(snapshot.pre_existing_positions)}")

    if snapshot.date_range[0] and snapshot.date_range[1]:
        print(f"  Date range:              {snapshot.date_range[0].strftime('%Y-%m-%d')} to {snapshot.date_range[1].strftime('%Y-%m-%d')}")

    # Instrument breakdown from reconstruction
    print(f"\n  Instrument types:")
    for itype, count in sorted(snapshot.instrument_breakdown.items()):
        print(f"    {itype:<18} {count:>4} positions")

    # ----- Step 6: Pre-existing positions -----
    if snapshot.pre_existing_positions:
        print(f"\n{'PRE-EXISTING POSITIONS':=^70}")
        print(f"  (Sold without prior buys in this dataset)")
        print(f"  {'Symbol':<10} {'Account':<30} {'Sells':>6} {'Proceeds':>14}")
        print(f"  {'-' * 62}")
        for pos in sorted(snapshot.pre_existing_positions, key=lambda p: p.symbol):
            print(f"  {pos.symbol:<10} {pos.account[:28]:<30} {pos.sell_count:>6} {fmt_dollar(pos.realized_proceeds):>14}")

    # ----- Step 7: Account summaries -----
    print(f"\n{'ACCOUNT SUMMARIES':=^70}")
    for name, acct in snapshot.accounts.items():
        print(f"\n  {name}")
        print(f"    Type:            {acct.account_type}")
        print(f"    Transactions:    {acct.transaction_count}")
        print(f"    Unique symbols:  {acct.unique_symbols}")
        print(f"    Total bought:    {fmt_dollar(acct.total_bought)}")
        print(f"    Total sold:      {fmt_dollar(acct.total_sold)}")
        print(f"    Net investment:  {fmt_dollar(acct.net_investment)}")
        print(f"    Dividends:       {fmt_dollar(acct.total_dividends)}")
        print(f"    Interest:        {fmt_dollar(acct.total_interest)}")
        print(f"    Fees:            {fmt_dollar(acct.total_fees)}")
        print(f"    Transfers in:    {fmt_dollar(acct.total_transfers_in)}")
        print(f"    Transfers out:   {fmt_dollar(acct.total_transfers_out)}")
        if acct.first_date and acct.last_date:
            print(f"    Date range:      {acct.first_date.strftime('%Y-%m-%d')} to {acct.last_date.strftime('%Y-%m-%d')}")

    # ----- Step 8: Top positions by activity -----
    print(f"\n{'TOP 10 MOST ACTIVE POSITIONS':=^70}")
    sorted_positions = sorted(
        snapshot.positions.values(),
        key=lambda p: len(p.transactions),
        reverse=True,
    )[:10]

    print(f"  {'Symbol':<10} {'Type':<14} {'Txns':>6} {'Qty':>10} {'Cost Basis':>14} {'Dividends':>12}")
    print(f"  {'-' * 68}")
    for pos in sorted_positions:
        print(
            f"  {pos.symbol:<10} "
            f"{pos.instrument.instrument_type:<14} "
            f"{len(pos.transactions):>6} "
            f"{pos.quantity:>10.2f} "
            f"{fmt_dollar(pos.cost_basis):>14} "
            f"{fmt_dollar(pos.dividends):>12}"
        )

    print(f"\n{'=' * 70}")
    print(f"  Done. {len(transactions)} transactions processed across {len(snapshot.accounts)} accounts.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
