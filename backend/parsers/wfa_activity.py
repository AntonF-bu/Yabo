"""
Wells Fargo Advisors Activity CSV Parser.

WFA activity exports have quirks:
- First few rows are metadata/headers (account name, date range, etc.)
- The real header row starts with "Date" (or similar)
- Dollar amounts use "$" prefix and parentheses for negatives: ($1,234.56)
- Some rows are sub-totals or section dividers (skip them)
- Multiple accounts may appear in one export (separated by blank rows + new header)
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ParsedTransaction:
    """A single normalized transaction from a WFA activity export."""

    date: datetime
    account: str
    account_type: str  # "taxable" | "ira" | "roth_ira" | "401k" | "business" | "unknown"
    action: str  # normalized: buy, sell, dividend, interest, fee, transfer, other
    symbol: str
    description: str
    quantity: float
    price: float
    amount: float  # net dollar amount (negative = outflow)
    fees: float
    raw_action: str  # original action string from CSV
    raw_row: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Account type detection
# ---------------------------------------------------------------------------

_ACCOUNT_TYPE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\broth\s*ira\b", re.IGNORECASE), "roth_ira"),
    (re.compile(r"\bira\b", re.IGNORECASE), "ira"),
    (re.compile(r"\b401\s*[\(\)]?\s*k\b", re.IGNORECASE), "401k"),
    (re.compile(r"\bbusiness\b", re.IGNORECASE), "business"),
    (re.compile(r"\bbrokerage\b", re.IGNORECASE), "taxable"),
    (re.compile(r"\bindividual\b", re.IGNORECASE), "taxable"),
    (re.compile(r"\bjoint\b", re.IGNORECASE), "taxable"),
]


def detect_account_type(account_name: str) -> str:
    """Infer account type from the account name/label string."""
    for pattern, acct_type in _ACCOUNT_TYPE_PATTERNS:
        if pattern.search(account_name):
            return acct_type
    return "unknown"


# ---------------------------------------------------------------------------
# Activity normalization
# ---------------------------------------------------------------------------

_ACTION_MAP: dict[str, str] = {
    # Buys
    "bought": "buy",
    "buy": "buy",
    "purchase": "buy",
    "purchased": "buy",
    "reinvestment": "buy",
    "reinvest": "buy",
    "dividend reinvestment": "buy",
    # Sells
    "sold": "sell",
    "sell": "sell",
    "sale": "sell",
    "redemption": "sell",
    "redeemed": "sell",
    # Dividends / distributions
    "dividend": "dividend",
    "dividends": "dividend",
    "div": "dividend",
    "qualified dividend": "dividend",
    "ordinary dividend": "dividend",
    "non-qualified dividend": "dividend",
    "capital gain": "dividend",
    "capital gains": "dividend",
    "long term capital gain": "dividend",
    "short term capital gain": "dividend",
    "lt cap gain": "dividend",
    "st cap gain": "dividend",
    "return of capital": "dividend",
    "distribution": "dividend",
    # Interest
    "interest": "interest",
    "interest earned": "interest",
    "interest income": "interest",
    "credit interest": "interest",
    "margin interest": "interest",
    # Fees
    "fee": "fee",
    "fees": "fee",
    "commission": "fee",
    "annual fee": "fee",
    "service fee": "fee",
    "advisory fee": "fee",
    "management fee": "fee",
    "account fee": "fee",
    # Transfers
    "transfer": "transfer",
    "journal": "transfer",
    "ach": "transfer",
    "wire": "transfer",
    "deposit": "transfer",
    "withdrawal": "transfer",
    "contribution": "transfer",
    # Options
    "option assignment": "sell",
    "option exercise": "buy",
    "expired": "other",
    "expiration": "other",
    "assigned": "sell",
    "exercised": "buy",
}


def normalize_action(raw: str) -> str:
    """Normalize a WFA action string to a canonical action."""
    cleaned = raw.strip().lower()
    # Direct lookup
    if cleaned in _ACTION_MAP:
        return _ACTION_MAP[cleaned]
    # Substring matching for compound actions
    for key, value in _ACTION_MAP.items():
        if key in cleaned:
            return value
    return "other"


# ---------------------------------------------------------------------------
# Dollar amount parsing
# ---------------------------------------------------------------------------

_DOLLAR_RE = re.compile(
    r"^\s*"
    r"(?P<neg>\(?)?\s*"          # optional opening paren for negative
    r"\$?\s*"                     # optional dollar sign
    r"(?P<num>[\d,]+\.?\d*)"     # digits with commas and optional decimal
    r"\s*(?P<neg2>\)?)?"         # optional closing paren for negative
    r"\s*$"
)


def parse_dollar(value: str) -> float:
    """Parse a dollar string like '$1,234.56' or '($1,234.56)' into a float."""
    if not value or not value.strip():
        return 0.0

    text = value.strip()

    # Handle explicit negative sign
    if text.startswith("-"):
        sign = -1.0
        text = text[1:].strip()
    else:
        sign = 1.0

    m = _DOLLAR_RE.match(text)
    if not m:
        # Last resort: strip everything non-numeric
        nums = re.sub(r"[^\d.\-]", "", value)
        return float(nums) if nums else 0.0

    num_str = m.group("num").replace(",", "")
    result = float(num_str)

    # Parentheses mean negative
    if m.group("neg") == "(" or m.group("neg2") == ")":
        result = -result

    return result * sign


def parse_quantity(value: str) -> float:
    """Parse a quantity string, handling commas and blanks."""
    if not value or not value.strip():
        return 0.0
    cleaned = value.strip().replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# CSV header detection
# ---------------------------------------------------------------------------

# Known header signatures for the real data row
_HEADER_SIGNATURES = [
    {"date", "action", "description", "symbol"},
    {"date", "action", "description", "quantity"},
    {"date", "activity", "description", "symbol"},
    {"date", "type", "description", "symbol"},
    {"date", "transaction", "description", "symbol"},
    {"trade date", "action", "description", "symbol"},
]


def _is_header_row(row: list[str]) -> bool:
    """Check if a CSV row looks like the real column header."""
    lower = {c.strip().lower() for c in row if c.strip()}
    return any(sig.issubset(lower) for sig in _HEADER_SIGNATURES)


def _find_column_index(headers: list[str], *candidates: str) -> Optional[int]:
    """Find the index of a column by trying multiple candidate names."""
    lower_headers = [h.strip().lower() for h in headers]
    for candidate in candidates:
        candidate_lower = candidate.lower()
        for i, h in enumerate(lower_headers):
            if candidate_lower == h or candidate_lower in h:
                return i
    return None


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

class WFAActivityParser:
    """
    Parse a Wells Fargo Advisors activity CSV export.

    Usage:
        parser = WFAActivityParser()
        transactions = parser.parse_csv("path/to/activity.csv")
    """

    def __init__(self) -> None:
        self.transactions: list[ParsedTransaction] = []
        self.accounts: set[str] = set()
        self.skipped_rows: int = 0
        self.total_rows: int = 0

    def parse_csv(self, path: str | Path) -> list[ParsedTransaction]:
        """
        Parse a WFA activity CSV file and return normalized transactions.

        Handles:
        - Metadata/header rows before the real data
        - Multiple account sections in one file
        - Dollar formatting with $, commas, and parentheses
        - Action normalization to canonical types
        """
        path = Path(path)
        content = path.read_text(encoding="utf-8-sig")  # handle BOM
        return self._parse_content(content)

    def parse_string(self, content: str) -> list[ParsedTransaction]:
        """Parse CSV content from a string (useful for testing)."""
        return self._parse_content(content)

    def _parse_content(self, content: str) -> list[ParsedTransaction]:
        self.transactions = []
        self.accounts = set()
        self.skipped_rows = 0
        self.total_rows = 0

        reader = csv.reader(io.StringIO(content))
        all_rows = list(reader)

        if not all_rows:
            return []

        # --- Detect account name from metadata rows ---
        current_account = "Unknown Account"
        headers: list[str] = []
        col_map: dict[str, Optional[int]] = {}
        in_data = False

        for row in all_rows:
            self.total_rows += 1

            # Skip empty rows
            if not any(cell.strip() for cell in row):
                # A blank row after data might signal a new account section
                if in_data:
                    in_data = False
                continue

            # Before we find the header, look for account name clues
            if not in_data:
                joined = " ".join(cell.strip() for cell in row if cell.strip())

                # Check if this is the real header row
                if _is_header_row(row):
                    headers = [c.strip() for c in row]
                    col_map = self._build_column_map(headers)
                    in_data = True
                    continue

                # Try to extract account name from metadata
                # Common patterns: "Account: XXXX-1234 - Brokerage"
                #                  "Account Name,XXXX-1234 IRA"
                acct_match = re.search(
                    r"(?:account\s*(?:name|number)?[:\s,]*)\s*(.+)",
                    joined,
                    re.IGNORECASE,
                )
                if acct_match:
                    current_account = acct_match.group(1).strip().rstrip(",")

                self.skipped_rows += 1
                continue

            # --- Parse data row ---
            txn = self._parse_data_row(row, col_map, current_account)
            if txn:
                self.transactions.append(txn)
                self.accounts.add(txn.account)
            else:
                self.skipped_rows += 1

        return self.transactions

    def _build_column_map(self, headers: list[str]) -> dict[str, Optional[int]]:
        """Map logical column names to their indices in the header row."""
        return {
            "date": _find_column_index(headers, "Date", "Trade Date", "Settlement Date"),
            "account": _find_column_index(headers, "Account", "Account Name", "Acct"),
            "action": _find_column_index(
                headers, "Action", "Activity", "Type", "Transaction", "Transaction Type"
            ),
            "symbol": _find_column_index(headers, "Symbol", "Ticker", "Sym"),
            "description": _find_column_index(
                headers, "Description", "Security", "Security Description", "Name"
            ),
            "quantity": _find_column_index(headers, "Quantity", "Qty", "Shares", "Units"),
            "price": _find_column_index(headers, "Price", "Unit Price", "Trade Price"),
            "amount": _find_column_index(
                headers, "Amount", "Net Amount", "Total", "Principal", "Net"
            ),
            "fees": _find_column_index(
                headers, "Commission", "Fees", "Fee", "Charges", "Commission & Fees"
            ),
        }

    def _parse_data_row(
        self,
        row: list[str],
        col_map: dict[str, Optional[int]],
        account: str,
    ) -> Optional[ParsedTransaction]:
        """Parse a single data row into a ParsedTransaction."""

        def get(key: str) -> str:
            idx = col_map.get(key)
            if idx is not None and idx < len(row):
                return row[idx].strip()
            return ""

        date_str = get("date")
        raw_action = get("action")

        # Skip rows without a parseable date (sub-totals, dividers)
        if not date_str or not raw_action:
            return None

        # Parse date
        dt = self._parse_date(date_str)
        if dt is None:
            return None

        # Skip summary/total rows
        action_lower = raw_action.strip().lower()
        if any(
            skip in action_lower
            for skip in ["total", "subtotal", "sub-total", "balance", "summary"]
        ):
            return None

        # Use per-row account if available, fall back to header metadata
        row_account = get("account")
        effective_account = row_account if row_account else account

        symbol = get("symbol").upper()
        description = get("description")
        quantity = parse_quantity(get("quantity"))
        price = parse_dollar(get("price"))
        amount = parse_dollar(get("amount"))
        fees = abs(parse_dollar(get("fees")))

        # Build raw_row dict for debugging
        raw_row = {}
        for key, idx in col_map.items():
            if idx is not None and idx < len(row):
                raw_row[key] = row[idx].strip()

        return ParsedTransaction(
            date=dt,
            account=effective_account,
            account_type=detect_account_type(effective_account),
            action=normalize_action(raw_action),
            symbol=symbol if symbol else "CASH",
            description=description,
            quantity=quantity,
            price=price,
            amount=amount,
            fees=fees,
            raw_action=raw_action,
            raw_row=raw_row,
        )

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        """Try multiple date formats common in WFA exports."""
        formats = [
            "%m/%d/%Y",
            "%m/%d/%y",
            "%Y-%m-%d",
            "%m-%d-%Y",
            "%m-%d-%y",
            "%b %d, %Y",
            "%B %d, %Y",
            "%m/%d/%Y %H:%M:%S",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None
