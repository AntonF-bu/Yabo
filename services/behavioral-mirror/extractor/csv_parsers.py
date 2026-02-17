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
    {"name": "wells_fargo", "description": "Wells Fargo Advisors CSV export"},
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

    # Wells Fargo: "Date", "Account", "Activity", "Description", "Amount"
    if "Activity" in cols and "Description" in cols and "Account" in cols:
        return "wells_fargo"
    if "activity" in cols_lower and "description" in cols_lower and "account" in cols_lower:
        return "wells_fargo"

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


# Money market sweep tickers to filter out
_MONEY_MARKET_TICKERS = {"FRSXX", "SPAXX", "SWVXX", "VMFXX", "FDRXX", "FTEXX", "SPRXX"}


def _parse_wells_fargo_option(desc: str, amount_str: str, date_str: str) -> dict[str, Any] | None:
    """Parse a Wells Fargo options trade from the Description field.

    Patterns:
        -50 TSLA2821A710 CALL TESLA INC $710 EXP 01/21/28 @ $62.2500
        57 NVDA2620C240 CALL NVIDIA CORPORATION $240 EXP 03/20/26 @ $0.6800
        -57 NVDA2620C240 CALL NVIDIA CORPORATION $240 EXP 03/20/26  (no premium = exercise/assignment)

    Returns structured option dict or None if not parseable as option.
    """
    desc_upper = desc.upper()
    if " CALL " not in desc_upper and " PUT " not in desc_upper:
        return None

    # Pattern: qty SYMBOL CALL|PUT name $strike EXP mm/dd/yy [@ $premium]
    pattern = re.compile(
        r"(-?\d+)\s+"                          # signed quantity
        r"(\w+)\s+"                             # option symbol (e.g., TSLA2821A710)
        r"(CALL|PUT)\s+"                        # option type
        r"(.+?)\s+"                             # company name
        r"\$([\d,.]+)\s+"                       # strike price
        r"EXP\s+(\d{2}/\d{2}/\d{2})"           # expiry date MM/DD/YY
        r"(?:\s+@\s+\$?([\d,.]+))?"            # optional premium per share
    )

    m = pattern.match(desc.strip())
    if not m:
        return None

    qty_raw = int(m.group(1))
    option_symbol = m.group(2)
    option_type = m.group(3).upper()
    company_name = m.group(4).strip()
    strike_price = float(m.group(5).replace(",", ""))
    expiry_raw = m.group(6)  # MM/DD/YY
    premium = float(m.group(7).replace(",", "")) if m.group(7) else None

    # Extract underlying ticker: alphabetic prefix before first digit
    underlying_match = re.match(r"^([A-Z]+)", option_symbol)
    underlying_ticker = underlying_match.group(1) if underlying_match else None

    contracts = abs(qty_raw)
    is_buy = qty_raw > 0

    # Directional classification
    if is_buy and option_type == "CALL":
        direction = "bullish"
        strategy_hint = "long_call"
    elif not is_buy and option_type == "CALL":
        direction = "bearish_or_income"
        strategy_hint = "short_call"
    elif is_buy and option_type == "PUT":
        direction = "bearish"
        strategy_hint = "long_put"
    else:  # sell put
        direction = "bullish"
        strategy_hint = "short_put"

    # Parse expiry date MM/DD/YY -> YYYY-MM-DD
    exp_parts = expiry_raw.split("/")
    expiry_date = f"20{exp_parts[2]}-{exp_parts[0]}-{exp_parts[1]}"

    # Parse trade date
    try:
        trade_date = pd.to_datetime(date_str)
    except Exception:
        return None

    # Days to expiry
    try:
        expiry_dt = pd.Timestamp(expiry_date)
        days_to_expiry = max((expiry_dt - trade_date).days, 0)
    except Exception:
        days_to_expiry = 0

    # Premium calculations (per contract = premium * 100)
    premium_per_contract = premium * 100 if premium else None
    total_premium = premium_per_contract * contracts if premium_per_contract else None

    # Fallback total from Amount field
    amount_val = None
    if amount_str:
        try:
            amount_val = abs(float(str(amount_str).replace("$", "").replace(",", "")))
        except (ValueError, TypeError):
            pass

    return {
        "date": trade_date,
        "instrument_type": "option",
        "underlying_ticker": underlying_ticker,
        "option_symbol": option_symbol,
        "option_type": option_type,
        "direction": direction,
        "strategy_hint": strategy_hint,
        "side": "BUY" if is_buy else "SELL",
        "contracts": contracts,
        "shares_equivalent": contracts * 100,
        "strike_price": strike_price,
        "expiry_date": expiry_date,
        "days_to_expiry": days_to_expiry,
        "premium_per_share": premium,
        "premium_per_contract": premium_per_contract,
        "total_premium": total_premium or amount_val,
        "total_from_amount": amount_val,
        "company_name": company_name,
        "is_exercise_or_assignment": premium is None,
        "confidence": "high" if premium else "medium",
    }


def parse_wells_fargo(df: pd.DataFrame) -> pd.DataFrame:
    """Parse Wells Fargo Advisors CSV export (equities only).

    Returns normalized equity trades. Options are parsed separately via
    parse_wells_fargo_options().
    """
    col_map = _wells_fargo_col_map(df)

    # Pattern: quantity TICKER rest_of_name @ $price
    desc_pattern = re.compile(
        r"^(-?\d+(?:\.\d+)?)\s+"   # quantity (may be negative)
        r"([A-Z]{1,5})\s+"         # ticker symbol (1-5 uppercase letters)
        r".*?"                      # fund/company name
        r"@\s*\$?([\d,]+\.?\d*)",  # price after @
        re.IGNORECASE,
    )

    # Secondary pattern: equity without @ price (e.g., option exercise delivery)
    # "-575 APP APPLOVIN CORP CL A" — use Amount field to infer price
    no_price_pattern = re.compile(
        r"^(-?\d+(?:\.\d+)?)\s+"   # quantity
        r"([A-Z]{1,5})\s+"         # ticker
        r".+",                      # name
        re.IGNORECASE,
    )

    rows: list[dict[str, Any]] = []
    options_count = 0

    for _, row in df.iterrows():
        activity = str(row.get(col_map["activity"], "")).upper().strip()
        desc = str(row.get(col_map["description"], ""))
        desc_upper = desc.upper()

        # Skip non-trade activities (dividends, interest, fees, journal entries)
        if activity not in ("BUY", "SELL"):
            if "BUY" not in desc_upper and "SELL" not in desc_upper:
                continue

        # Skip options — they're parsed separately
        if " CALL " in desc_upper or " PUT " in desc_upper:
            options_count += 1
            continue

        # Skip money market sweeps
        if any(mm in desc_upper for mm in _MONEY_MARKET_TICKERS):
            continue

        # Try standard equity pattern with @ price
        m = desc_pattern.match(desc.strip())
        if m:
            qty_raw = float(m.group(1).replace(",", ""))
            ticker = m.group(2).upper()
            price = float(m.group(3).replace(",", ""))
        else:
            # Try no-price pattern (exercise delivery etc.)
            m2 = no_price_pattern.match(desc.strip())
            if not m2:
                continue
            qty_raw = float(m2.group(1).replace(",", ""))
            ticker = m2.group(2).upper()
            # Infer price from Amount field
            amount_str = str(row.get(col_map.get("amount", "Amount"), "0"))
            try:
                amount_val = abs(float(amount_str.replace("$", "").replace(",", "")))
            except (ValueError, TypeError):
                continue
            price = amount_val / abs(qty_raw) if abs(qty_raw) > 0 else 0

        if ticker in _MONEY_MARKET_TICKERS:
            continue
        if price <= 0:
            continue

        action = "SELL" if qty_raw < 0 else "BUY"
        qty = abs(qty_raw)

        date_str = str(row.get(col_map["date"], ""))
        try:
            date_val = pd.to_datetime(date_str)
        except Exception:
            continue

        rows.append({
            "date": date_val,
            "ticker": ticker,
            "action": action,
            "quantity": qty,
            "price": price,
            "fees": 0.0,
        })

    if not rows:
        logger.warning("[Wells Fargo] No stock trades found in CSV")
        return pd.DataFrame(columns=CANONICAL_COLUMNS)

    result = pd.DataFrame(rows)
    result = result[(result["quantity"] > 0) & (result["price"] > 0)]
    logger.info("[Wells Fargo] Parsed %d equity trades (%d options parsed separately)",
                len(result), options_count)
    return result[CANONICAL_COLUMNS].reset_index(drop=True)


def parse_wells_fargo_options(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Parse all options trades from a Wells Fargo CSV.

    Returns list of structured option trade dicts.
    """
    col_map = _wells_fargo_col_map(df)
    option_trades: list[dict[str, Any]] = []
    unparseable: list[str] = []

    for _, row in df.iterrows():
        desc = str(row.get(col_map["description"], ""))
        desc_upper = desc.upper()

        # Only process lines containing CALL or PUT
        if " CALL " not in desc_upper and " PUT " not in desc_upper:
            continue

        date_str = str(row.get(col_map["date"], ""))
        amount_str = str(row.get(col_map.get("amount", "Amount"), "0"))

        option = _parse_wells_fargo_option(desc, amount_str, date_str)
        if option:
            option_trades.append(option)
        else:
            unparseable.append(desc)

    if unparseable:
        logger.warning("[Wells Fargo Options] %d option lines could not be parsed", len(unparseable))
    if option_trades:
        logger.info(
            "[Wells Fargo Options] Parsed %d option trades across %d underlyings",
            len(option_trades),
            len(set(t["underlying_ticker"] for t in option_trades if t.get("underlying_ticker"))),
        )
    return option_trades


def _wells_fargo_col_map(df: pd.DataFrame) -> dict[str, str]:
    """Build case-insensitive column map for Wells Fargo CSV."""
    col_map: dict[str, str] = {}
    for c in df.columns:
        cl = c.strip().lower()
        if cl == "date":
            col_map["date"] = c
        elif cl == "activity":
            col_map["activity"] = c
        elif cl == "description":
            col_map["description"] = c
        elif cl == "amount":
            col_map["amount"] = c
        elif cl == "account":
            col_map["account"] = c
    if not all(k in col_map for k in ("date", "activity", "description")):
        raise ValueError("Wells Fargo format missing required columns")
    return col_map


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


def _extract_cash_flow_metadata(df: pd.DataFrame, fmt: str) -> dict[str, Any] | None:
    """Extract cash flow metadata (deposits, withdrawals, dividends) from raw CSV.

    Only works for formats that include non-trade rows (Trading212).
    Returns None for formats without cash flow data.
    """
    if fmt not in ("trading212_new", "trading212_classic"):
        return None

    # Find the action/type column
    type_col = None
    date_col = None
    amount_col = None
    ticker_col = None
    for c in df.columns:
        cl = c.strip().lower()
        if cl == "type":
            type_col = c
        elif cl in ("date", "time"):
            date_col = c
        elif cl in ("total amount", "total", "result"):
            amount_col = c
        elif cl == "ticker":
            ticker_col = c

    if not type_col or not date_col:
        return None

    deposits: list[dict] = []
    withdrawals: list[dict] = []
    dividends: list[dict] = []

    for _, row in df.iterrows():
        action = str(row[type_col]).upper().strip()
        date_val = str(row[date_col])
        amount = _parse_number(row[amount_col]) if amount_col and amount_col in row.index else 0.0

        if "TOP-UP" in action or "DEPOSIT" in action:
            deposits.append({"date": date_val, "amount": abs(amount)})
        elif "WITHDRAWAL" in action:
            withdrawals.append({"date": date_val, "amount": abs(amount)})
        elif "DIVIDEND" in action:
            ticker = str(row[ticker_col]).strip() if ticker_col and ticker_col in row.index else ""
            dividends.append({"date": date_val, "amount": abs(amount), "ticker": ticker})

    total_deposited = sum(d["amount"] for d in deposits)
    total_withdrawn = sum(w["amount"] for w in withdrawals)
    total_dividends = sum(d["amount"] for d in dividends)

    metadata = {
        "deposits": deposits,
        "withdrawals": withdrawals,
        "dividends": dividends,
        "total_deposited": total_deposited,
        "total_withdrawn": total_withdrawn,
        "total_dividends": total_dividends,
        "estimated_starting_capital": deposits[0]["amount"] if deposits else 0.0,
    }

    if deposits:
        logger.info("[CSV Parser] Cash flow: %d deposits ($%.0f), %d withdrawals ($%.0f), "
                     "%d dividends ($%.2f)",
                     len(deposits), total_deposited, len(withdrawals), total_withdrawn,
                     len(dividends), total_dividends)

    return metadata


def normalize_csv(csv_path: str | Path) -> tuple[pd.DataFrame, str]:
    """Detect format, parse, and normalize a CSV file.

    Returns:
        Tuple of (normalized DataFrame, format name).
    """
    result, fmt, _ = normalize_csv_with_metadata(csv_path)
    return result, fmt


def normalize_csv_with_metadata(
    csv_path: str | Path,
) -> tuple[pd.DataFrame, str, dict[str, Any] | None]:
    """Detect format, parse, normalize a CSV file, and extract cash flow metadata.

    Returns:
        Tuple of (normalized DataFrame, format name, metadata_dict or None).
        metadata_dict may contain 'cash_flow' and/or 'option_trades' keys.
    """
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path)

    if df.empty:
        return df, "empty", None

    fmt = detect_format(df)
    logger.info("[CSV Parser] Detected format: %s for %s (%d rows, cols: %s)",
                fmt, csv_path.name, len(df), list(df.columns))

    # Extract cash flow metadata BEFORE filtering to trades only
    cash_flow_metadata = _extract_cash_flow_metadata(df, fmt)

    # Extract options trades for supported formats
    option_trades: list[dict[str, Any]] = []
    if fmt == "wells_fargo":
        try:
            option_trades = parse_wells_fargo_options(df)
        except Exception as e:
            logger.warning("[CSV Parser] Options parsing failed (non-fatal): %s", e)

    parsers = {
        "yabo_internal": parse_generic,
        "trading212_new": parse_trading212_new,
        "trading212_classic": parse_trading212_classic,
        "robinhood": parse_robinhood,
        "schwab": parse_schwab,
        "wells_fargo": parse_wells_fargo,
        "generic": parse_generic,
    }

    parser = parsers.get(fmt, parse_generic)
    try:
        result = parser(df)
    except Exception as e:
        logger.warning("Format-specific parser failed (%s), trying generic: %s", fmt, e)
        result = parse_generic(df)
        fmt = "generic_fallback"

    # Combine metadata
    metadata: dict[str, Any] | None = None
    if cash_flow_metadata or option_trades:
        metadata = {}
        if cash_flow_metadata:
            metadata["cash_flow"] = cash_flow_metadata
        if option_trades:
            metadata["option_trades"] = option_trades
            logger.info("[CSV Parser] Total: %d equity trades + %d option trades from %s",
                        len(result), len(option_trades), fmt)

    logger.info("[CSV Parser] Normalized %d trade rows from %s format", len(result), fmt)
    return result, fmt, metadata
