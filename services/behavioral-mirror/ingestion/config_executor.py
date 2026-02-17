"""Execute a cached parser config against a CSV DataFrame.

The ConfigExecutor applies a ParserConfig's column_map, action_map, and
number_cleanup rules to normalize a raw DataFrame into canonical columns.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

CANONICAL_COLUMNS = ["ticker", "action", "quantity", "price", "date", "fees"]


class ConfigExecutor:
    """Apply a parser config to normalize a CSV DataFrame."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.config_id = config.get("config_id", "unknown")
        self.format_name = config.get("format_name", "unknown")

    def execute(
        self, df: pd.DataFrame,
    ) -> tuple[pd.DataFrame, dict[str, Any] | None]:
        """Apply config to normalize a DataFrame.

        Returns:
            Tuple of (normalized trades DataFrame, metadata dict or None).
            metadata may contain 'cash_flow' and/or 'option_trades' keys.
        """
        col_map = self.config.get("column_map", {})
        action_map = self.config.get("action_map", {})
        skip_actions = set(
            a.upper() for a in self.config.get("skip_actions", [])
        )
        number_cleanup = self.config.get("number_cleanup", ["$", ","])

        # Wells Fargo uses description parsing — delegate to existing parser
        if self.config.get("description_parsing"):
            return self._execute_description_parsing(df)

        # Build case-insensitive column lookup
        actual_cols = {c.strip().lower(): c for c in df.columns}

        def _resolve_col(target: str | None) -> str | None:
            """Resolve a config column name to an actual DataFrame column."""
            if target is None:
                return None
            # Exact match first
            if target in df.columns:
                return target
            # Case-insensitive match
            return actual_cols.get(target.strip().lower())

        date_col = _resolve_col(col_map.get("date"))
        ticker_col = _resolve_col(col_map.get("ticker"))
        action_col = _resolve_col(col_map.get("action"))
        qty_col = _resolve_col(col_map.get("quantity"))
        price_col = _resolve_col(col_map.get("price"))
        fees_col = _resolve_col(col_map.get("fees"))

        required = {"date": date_col, "ticker": ticker_col, "action": action_col,
                     "quantity": qty_col, "price": price_col}
        missing = [k for k, v in required.items() if v is None]
        if missing:
            raise ValueError(
                f"Config '{self.config_id}' could not resolve columns: {missing}. "
                f"Available: {list(df.columns)}"
            )

        def _clean_number(val: Any) -> float:
            if pd.isna(val):
                return 0.0
            s = str(val).strip()
            for char in number_cleanup:
                s = s.replace(char, "")
            s = s.strip()
            # Handle parenthetical negatives: (123.45) -> -123.45
            if s.startswith("(") and s.endswith(")"):
                s = "-" + s[1:-1]
            try:
                return float(s)
            except (ValueError, TypeError):
                return 0.0

        def _map_action(val: str) -> str | None:
            v = str(val).strip()
            # Check exact match first
            if v in action_map:
                return action_map[v]
            # Check uppercase
            vu = v.upper()
            if vu in action_map:
                return action_map[vu]
            # Check skip list
            if vu in skip_actions:
                return None
            # Fuzzy: contains BUY or SELL
            if "BUY" in vu:
                return "BUY"
            if "SELL" in vu:
                return "SELL"
            return None

        result = pd.DataFrame()
        date_format = self.config.get("date_format")
        if date_format:
            result["date"] = pd.to_datetime(df[date_col], format=date_format, errors="coerce")
        else:
            result["date"] = pd.to_datetime(df[date_col], errors="coerce")

        result["ticker"] = df[ticker_col].astype(str).str.strip()
        result["quantity"] = df[qty_col].apply(_clean_number).abs()
        result["price"] = df[price_col].apply(_clean_number)
        result["action"] = df[action_col].apply(_map_action)
        result["fees"] = df[fees_col].apply(_clean_number) if fees_col else 0.0

        # Drop non-trade rows
        result = result.dropna(subset=["action", "date"])
        result = result[(result["quantity"] > 0) & (result["price"] > 0)]

        # Extract cash flow metadata if configured
        metadata = self._extract_cash_flow(df, col_map, action_col) if self.config.get("has_cash_flow") else None

        logger.info(
            "[ConfigExecutor] '%s' parsed %d trade rows from %d raw rows",
            self.format_name, len(result), len(df),
        )

        return result[CANONICAL_COLUMNS].reset_index(drop=True), metadata

    def _execute_description_parsing(
        self, df: pd.DataFrame,
    ) -> tuple[pd.DataFrame, dict[str, Any] | None]:
        """Delegate to the existing Wells Fargo parser for description-based formats."""
        from extractor.csv_parsers import (
            parse_wells_fargo, parse_wells_fargo_options,
            _extract_cash_flow_metadata,
        )

        result = parse_wells_fargo(df)

        metadata: dict[str, Any] | None = None
        if self.config.get("has_options"):
            try:
                option_trades = parse_wells_fargo_options(df)
                if option_trades:
                    metadata = {"option_trades": option_trades}
            except Exception as e:
                logger.warning("[ConfigExecutor] Options parsing failed: %s", e)

        return result, metadata

    def _extract_cash_flow(
        self, df: pd.DataFrame, col_map: dict[str, str | None],
        action_col: str,
    ) -> dict[str, Any] | None:
        """Extract cash flow metadata from non-trade rows."""
        cash_flow_config = self.config.get("cash_flow_actions")
        if not cash_flow_config:
            return None

        actual_cols = {c.strip().lower(): c for c in df.columns}
        date_col_name = col_map.get("date")
        date_col = None
        if date_col_name:
            date_col = date_col_name if date_col_name in df.columns else actual_cols.get(date_col_name.lower())

        # Find an amount column
        amount_col = None
        for candidate in ["Total Amount", "total amount", "Total", "total", "Result", "result", "Amount", "amount"]:
            if candidate in df.columns:
                amount_col = candidate
                break
            lower = candidate.lower()
            if lower in actual_cols:
                amount_col = actual_cols[lower]
                break

        deposit_actions = set(a.upper() for a in cash_flow_config.get("deposits", []))
        withdrawal_actions = set(a.upper() for a in cash_flow_config.get("withdrawals", []))
        dividend_actions = set(a.upper() for a in cash_flow_config.get("dividends", []))

        ticker_col_name = col_map.get("ticker")
        ticker_col = None
        if ticker_col_name:
            ticker_col = ticker_col_name if ticker_col_name in df.columns else actual_cols.get(ticker_col_name.lower())

        deposits: list[dict] = []
        withdrawals: list[dict] = []
        dividends: list[dict] = []

        number_cleanup = self.config.get("number_cleanup", ["$", ","])

        def _clean(val: Any) -> float:
            if pd.isna(val):
                return 0.0
            s = str(val).strip()
            for char in number_cleanup:
                s = s.replace(char, "")
            try:
                return float(s.strip())
            except (ValueError, TypeError):
                return 0.0

        for _, row in df.iterrows():
            action = str(row[action_col]).strip().upper()
            date_val = str(row[date_col]) if date_col else ""
            amount = abs(_clean(row[amount_col])) if amount_col and amount_col in row.index else 0.0

            if any(da in action for da in deposit_actions):
                deposits.append({"date": date_val, "amount": amount})
            elif any(wa in action for wa in withdrawal_actions):
                withdrawals.append({"date": date_val, "amount": amount})
            elif any(diva in action for diva in dividend_actions):
                ticker = str(row[ticker_col]).strip() if ticker_col and ticker_col in row.index else ""
                dividends.append({"date": date_val, "amount": amount, "ticker": ticker})

        if not deposits and not withdrawals and not dividends:
            return None

        total_deposited = sum(d["amount"] for d in deposits)
        total_withdrawn = sum(w["amount"] for w in withdrawals)
        total_dividends = sum(d["amount"] for d in dividends)

        return {
            "cash_flow": {
                "deposits": deposits,
                "withdrawals": withdrawals,
                "dividends": dividends,
                "total_deposited": total_deposited,
                "total_withdrawn": total_withdrawn,
                "total_dividends": total_dividends,
                "estimated_starting_capital": deposits[0]["amount"] if deposits else 0.0,
            }
        }

    def validate(self, df: pd.DataFrame) -> dict[str, Any]:
        """Validate that a config can parse a DataFrame without errors.

        Returns a dict with 'valid' bool, 'issues' list, and 'sample_rows' count.
        """
        issues: list[str] = []
        col_map = self.config.get("column_map", {})

        if self.config.get("description_parsing"):
            # Description-parsed formats are validated differently
            return {"valid": True, "issues": [], "sample_rows": len(df)}

        actual_cols = {c.strip().lower(): c for c in df.columns}

        for field in ["date", "ticker", "action", "quantity", "price"]:
            target = col_map.get(field)
            if target is None:
                issues.append(f"No column mapped for '{field}'")
                continue
            if target not in df.columns and target.strip().lower() not in actual_cols:
                issues.append(f"Column '{target}' (for {field}) not found in CSV")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "sample_rows": len(df),
        }
