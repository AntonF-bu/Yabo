"""Multi-format CSV parsing and normalization for the behavioral mirror backend.

Supports: Trading212, Robinhood, Schwab, and generic CSV formats.
All parsers normalize to a standard schema: ticker, action, quantity, price, date, fees.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Canonical output columns
CANONICAL_COLUMNS = ["ticker", "action", "quantity", "price", "date", "fees"]

# Supported format names
SUPPORTED_FORMATS = [
    {"name": "trading212_new", "description": "Trading212 (2024+ format)"},
    {"name": "trading212_classic", "description": "Trading212 (classic format)"},
    {"name": "robinhood", "description": "Robinhood CSV export"},
    {"name": "schwab", "description": "Charles Schwab CSV export"},
    {"name": "yabo_internal", "description": "Yabo synthetic trader format"},
    {"name": "generic", "description": "Auto-detected generic CSV"},
]

# Column name patterns for generic detection
_DATE_PATTERNS = re.compile(
    r"^(date|trade.?date|execution.?date|time|timestamp|settlement.?date|trans.?date)$", re.I
)
_TICKER_PATTERNS = re.compile(
    r"^(ticker|symbol|stock.?symbol|instrument|security|name|stock)$", re.I
)
_ACTION_PATTERNS = re.compile(
    r"^(action|type|transaction.?type|side|trade.?type|order.?type|trans.?type|activity)$", re.I
)
_QUANTITY_PATTERNS = re.compile(
    r"^(quantity|qty|shares|no\.?\s*of\s*shares|units|amount|size|number)$", re.I
)
_PRICE_PATTERNS = re.compile(
    r"^(price|price.?per.?share|unit.?price|avg.?price|execution.?price|fill.?price|cost.?basis)$", re.I
)
_FEES_PATTERNS = re.compile(
    r"^(fees|commission|fee|charges|transaction.?fee)$", re.I
)


def _parse_number(value: Any) -> float:
    """Parse a number that may have currency prefixes, commas, or dollar signs."""
    if pd.isna(value):
        return 0.0
    s = str(value).strip()
    # Strip currency code prefix (e.g., "USD 158.50", "GBP 42.00")
    s = re.sub(r"^[A-Z]{2,4}\s+", "", s, flags=re.IGNORECASE)
    # Strip dollar signs, commas
    s = s.replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _normalize_action(value: str) -> str | None:
    """Normalize action to BUY or SELL. Returns None for non-trade rows."""
    v = str(value).upper().strip()

    # Direct matches
    if v in ("BUY", "B"):
        return "BUY"
    if v in ("SELL", "S"):
        return "SELL"

    # Compound actions (e.g., "BUY - MARKET", "SELL - LIMIT")
    if "BUY" in v:
        return "BUY"
    if "SELL" in v:
        return "SELL"

    # Non-trade rows
    return None


def detect_format(df: pd.DataFrame) -> str:
    """Detect CSV format from column headers."""
    cols = set(c.strip() for c in df.columns)
    cols_lower = set(c.lower() for c in cols)

    # Yabo internal format
    if {"trader_id", "ticker", "action", "quantity", "price", "date"} <= cols_lower:
        return "yabo_internal"

    # Trading212 new format (2024+): "Date", "Ticker", "Type", "Quantity", "Price per share"
    if "Ticker" in cols and "Price per share" in cols:
        return "trading212_new"
    if "ticker" in cols_lower and "price per share" in cols_lower:
        return "trading212_new"

    # Trading212 classic format: "Time", "Ticker", "No. of shares", "Price / share"
    if "Time" in cols and "No. of shares" in cols:
        return "trading212_classic"
    if "time" in cols_lower and "no. of shares" in cols_lower:
        return "trading212_classic"

    # Robinhood: "Activity Date", "Instrument", "Trans Code", "Quantity", "Price"
    if "Activity Date" in cols and "Instrument" in cols and "Trans Code" in cols:
        return "robinhood"

    # Schwab: "Date", "Action", "Symbol", "Quantity", "Price"
    if "Symbol" in cols and "Action" in cols and "Quantity" in cols:
        if "Amount" in cols or "Fees & Comm" in cols:
            return "schwab"

    return "generic"


def parse_trading212_new(df: pd.DataFrame) -> pd.DataFrame:
    """Parse Trading212 new format (2024+).

    Columns: Date, Ticker, Type, Quantity, Price per share, Total Amount, Currency, FX Rate, ...
    """
    # Find actual column names (case-insensitive)
    col_map: dict[str, str] = {}
    for c in df.columns:
        cl = c.strip().lower()
        if cl == "date":
            col_map["date"] = c
        elif cl == "ticker":
            col_map["ticker"] = c
        elif cl == "type":
            col_map["action"] = c
        elif cl == "quantity":
            col_map["quantity"] = c
        elif cl in ("price per share", "price/share"):
            col_map["price"] = c

    if not all(k in col_map for k in ("date", "ticker", "action", "quantity", "price")):
        raise ValueError("Trading212 new format missing required columns")

    result = pd.DataFrame()
    result["date"] = pd.to_datetime(df[col_map["date"]])
    result["ticker"] = df[col_map["ticker"]].astype(str).str.strip()
    result["quantity"] = df[col_map["quantity"]].apply(_parse_number)
    result["price"] = df[col_map["price"]].apply(_parse_number)

    # Normalize actions, filter non-trade rows
    result["action"] = df[col_map["action"]].apply(_normalize_action)
    result["fees"] = 0.0

    # Drop non-trade rows (dividends, deposits, etc.)
    result = result.dropna(subset=["action"])
    # Drop rows with zero quantity or price
    result = result[(result["quantity"] > 0) & (result["price"] > 0)]

    return result[CANONICAL_COLUMNS].reset_index(drop=True)


def parse_trading212_classic(df: pd.DataFrame) -> pd.DataFrame:
    """Parse Trading212 classic format.

    Columns: Time, Ticker, Type, No. of shares, Price / share, ...
    """
    col_map: dict[str, str] = {}
    for c in df.columns:
        cl = c.strip().lower()
        if cl == "time":
            col_map["date"] = c
        elif cl == "ticker":
            col_map["ticker"] = c
        elif cl == "type":
            col_map["action"] = c
        elif cl in ("no. of shares", "no.of shares", "shares"):
            col_map["quantity"] = c
        elif cl in ("price / share", "price/share"):
            col_map["price"] = c

    if not all(k in col_map for k in ("date", "ticker", "action", "quantity", "price")):
        raise ValueError("Trading212 classic format missing required columns")

    result = pd.DataFrame()
    result["date"] = pd.to_datetime(df[col_map["date"]])
    result["ticker"] = df[col_map["ticker"]].astype(str).str.strip()
    result["quantity"] = df[col_map["quantity"]].apply(_parse_number)
    result["price"] = df[col_map["price"]].apply(_parse_number)
    result["action"] = df[col_map["action"]].apply(_normalize_action)
    result["fees"] = 0.0

    result = result.dropna(subset=["action"])
    result = result[(result["quantity"] > 0) & (result["price"] > 0)]

    return result[CANONICAL_COLUMNS].reset_index(drop=True)


def parse_robinhood(df: pd.DataFrame) -> pd.DataFrame:
    """Parse Robinhood CSV export.

    Columns: Activity Date, Settle Date, Instrument, Description, Trans Code,
    Quantity, Price, Amount
    """
    result = pd.DataFrame()
    result["date"] = pd.to_datetime(df["Activity Date"])
    result["ticker"] = df["Instrument"].astype(str).str.strip()
    result["quantity"] = df["Quantity"].apply(_parse_number).abs()
    result["price"] = df["Price"].apply(_parse_number)

    # Trans Code mapping
    def _rh_action(code: str) -> str | None:
        c = str(code).upper().strip()
        if c in ("BUY", "B"):
            return "BUY"
        if c in ("SELL", "SLD", "S"):
            return "SELL"
        return None

    result["action"] = df["Trans Code"].apply(_rh_action)
    result["fees"] = 0.0

    result = result.dropna(subset=["action"])
    result = result[(result["quantity"] > 0) & (result["price"] > 0)]

    return result[CANONICAL_COLUMNS].reset_index(drop=True)


def parse_schwab(df: pd.DataFrame) -> pd.DataFrame:
    """Parse Charles Schwab CSV export.

    Columns: Date, Action, Symbol, Description, Quantity, Price, Fees & Comm, Amount
    """
    result = pd.DataFrame()
    result["date"] = pd.to_datetime(df["Date"], errors="coerce")
    result["ticker"] = df["Symbol"].astype(str).str.strip()
    result["quantity"] = df["Quantity"].apply(_parse_number).abs()
    result["price"] = df["Price"].apply(_parse_number)

    def _schwab_action(action: str) -> str | None:
        a = str(action).upper().strip()
        if "BUY" in a:
            return "BUY"
        if "SELL" in a:
            return "SELL"
        return None

    result["action"] = df["Action"].apply(_schwab_action)

    fees_col = "Fees & Comm" if "Fees & Comm" in df.columns else None
    result["fees"] = df[fees_col].apply(_parse_number) if fees_col else 0.0

    result = result.dropna(subset=["action", "date"])
    result = result[(result["quantity"] > 0) & (result["price"] > 0)]

    return result[CANONICAL_COLUMNS].reset_index(drop=True)


def parse_generic(df: pd.DataFrame) -> pd.DataFrame:
    """Parse generic CSV using column name pattern matching."""
    col_map: dict[str, str] = {}

    for c in df.columns:
        cs = c.strip()
        if not col_map.get("date") and _DATE_PATTERNS.match(cs):
            col_map["date"] = c
        elif not col_map.get("ticker") and _TICKER_PATTERNS.match(cs):
            col_map["ticker"] = c
        elif not col_map.get("action") and _ACTION_PATTERNS.match(cs):
            col_map["action"] = c
        elif not col_map.get("quantity") and _QUANTITY_PATTERNS.match(cs):
            col_map["quantity"] = c
        elif not col_map.get("price") and _PRICE_PATTERNS.match(cs):
            col_map["price"] = c
        elif not col_map.get("fees") and _FEES_PATTERNS.match(cs):
            col_map["fees"] = c

    required = ["date", "ticker", "action", "quantity", "price"]
    missing = [k for k in required if k not in col_map]
    if missing:
        raise ValueError(f"Could not identify columns for: {missing}. "
                         f"Available: {list(df.columns)}")

    result = pd.DataFrame()
    result["date"] = pd.to_datetime(df[col_map["date"]], errors="coerce")
    result["ticker"] = df[col_map["ticker"]].astype(str).str.strip()
    result["quantity"] = df[col_map["quantity"]].apply(_parse_number).abs()
    result["price"] = df[col_map["price"]].apply(_parse_number)
    result["action"] = df[col_map["action"]].apply(_normalize_action)
    result["fees"] = df[col_map["fees"]].apply(_parse_number) if "fees" in col_map else 0.0

    result = result.dropna(subset=["action", "date"])
    result = result[(result["quantity"] > 0) & (result["price"] > 0)]

    return result[CANONICAL_COLUMNS].reset_index(drop=True)


def normalize_csv(csv_path: str | Path) -> tuple[pd.DataFrame, str]:
    """Detect format, parse, and normalize a CSV file.

    Returns:
        Tuple of (normalized DataFrame, format name).
    """
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path)

    if df.empty:
        return df, "empty"

    fmt = detect_format(df)
    logger.info("[CSV Parser] Detected format: %s for %s (%d rows, cols: %s)",
                fmt, csv_path.name, len(df), list(df.columns))

    parsers = {
        "yabo_internal": parse_generic,  # Yabo internal already has standard columns
        "trading212_new": parse_trading212_new,
        "trading212_classic": parse_trading212_classic,
        "robinhood": parse_robinhood,
        "schwab": parse_schwab,
        "generic": parse_generic,
    }

    parser = parsers.get(fmt, parse_generic)
    try:
        result = parser(df)
    except Exception as e:
        logger.warning("Format-specific parser failed (%s), trying generic: %s", fmt, e)
        result = parse_generic(df)
        fmt = "generic_fallback"

    logger.info("[CSV Parser] Normalized %d trade rows from %s format", len(result), fmt)
    return result, fmt
