"""Seed parser configs for known brokerage formats.

These are pre-built configs that get loaded on first run so known formats
parse instantly without any Claude API call.
"""

from __future__ import annotations

from typing import Any


def get_seed_configs() -> list[dict[str, Any]]:
    """Return all seed parser configs."""
    return [
        _trading212_new_config(),
        _trading212_classic_config(),
        _robinhood_config(),
        _schwab_config(),
        _wells_fargo_config(),
    ]


def _trading212_new_config() -> dict[str, Any]:
    return {
        "config_id": "seed_trading212_new",
        "format_name": "Trading212 (2024+ format)",
        "header_signature": _signature([
            "Date", "Ticker", "Type", "Quantity", "Price per share",
        ]),
        "required_headers": ["Date", "Ticker", "Type", "Quantity", "Price per share"],
        "column_map": {
            "date": "Date",
            "ticker": "Ticker",
            "action": "Type",
            "quantity": "Quantity",
            "price": "Price per share",
            "fees": None,
        },
        "action_map": {
            "BUY": "BUY",
            "SELL": "SELL",
            "Market buy": "BUY",
            "Market sell": "SELL",
            "Limit buy": "BUY",
            "Limit sell": "SELL",
        },
        "skip_actions": [
            "Deposit", "Withdrawal", "Dividend", "Interest",
            "TOP-UP", "Currency conversion",
        ],
        "date_format": None,  # pandas auto-detect
        "number_cleanup": ["$", ",", "USD ", "GBP ", "EUR "],
        "has_options": False,
        "has_cash_flow": True,
        "cash_flow_actions": {
            "deposits": ["TOP-UP", "Deposit"],
            "withdrawals": ["Withdrawal"],
            "dividends": ["Dividend"],
        },
        "source": "seed",
        "version": 1,
        "confidence": 1.0,
        "times_used": 0,
    }


def _trading212_classic_config() -> dict[str, Any]:
    return {
        "config_id": "seed_trading212_classic",
        "format_name": "Trading212 (classic format)",
        "header_signature": _signature([
            "Time", "Ticker", "Type", "No. of shares", "Price / share",
        ]),
        "required_headers": ["Time", "Ticker", "Type", "No. of shares", "Price / share"],
        "column_map": {
            "date": "Time",
            "ticker": "Ticker",
            "action": "Type",
            "quantity": "No. of shares",
            "price": "Price / share",
            "fees": None,
        },
        "action_map": {
            "BUY": "BUY",
            "SELL": "SELL",
            "Market buy": "BUY",
            "Market sell": "SELL",
            "Limit buy": "BUY",
            "Limit sell": "SELL",
        },
        "skip_actions": [
            "Deposit", "Withdrawal", "Dividend", "Interest",
            "TOP-UP", "Currency conversion",
        ],
        "date_format": None,
        "number_cleanup": ["$", ",", "USD ", "GBP ", "EUR "],
        "has_options": False,
        "has_cash_flow": True,
        "cash_flow_actions": {
            "deposits": ["TOP-UP", "Deposit"],
            "withdrawals": ["Withdrawal"],
            "dividends": ["Dividend"],
        },
        "source": "seed",
        "version": 1,
        "confidence": 1.0,
        "times_used": 0,
    }


def _robinhood_config() -> dict[str, Any]:
    return {
        "config_id": "seed_robinhood",
        "format_name": "Robinhood CSV export",
        "header_signature": _signature([
            "Activity Date", "Instrument", "Trans Code", "Quantity", "Price",
        ]),
        "required_headers": [
            "Activity Date", "Instrument", "Trans Code", "Quantity", "Price",
        ],
        "column_map": {
            "date": "Activity Date",
            "ticker": "Instrument",
            "action": "Trans Code",
            "quantity": "Quantity",
            "price": "Price",
            "fees": None,
        },
        "action_map": {
            "BUY": "BUY",
            "B": "BUY",
            "SELL": "SELL",
            "SLD": "SELL",
            "S": "SELL",
        },
        "skip_actions": ["DIV", "INT", "CDEP", "CWIT", "ACH"],
        "date_format": None,
        "number_cleanup": ["$", ","],
        "has_options": False,
        "has_cash_flow": False,
        "source": "seed",
        "version": 1,
        "confidence": 1.0,
        "times_used": 0,
    }


def _schwab_config() -> dict[str, Any]:
    return {
        "config_id": "seed_schwab",
        "format_name": "Charles Schwab CSV export",
        "header_signature": _signature([
            "Date", "Action", "Symbol", "Quantity", "Price",
        ]),
        "required_headers": ["Date", "Action", "Symbol", "Quantity", "Price"],
        "column_map": {
            "date": "Date",
            "ticker": "Symbol",
            "action": "Action",
            "quantity": "Quantity",
            "price": "Price",
            "fees": "Fees & Comm",
        },
        "action_map": {
            "Buy": "BUY",
            "Sell": "SELL",
            "Buy to Open": "BUY",
            "Sell to Close": "SELL",
            "Buy to Close": "BUY",
            "Sell to Open": "SELL",
        },
        "skip_actions": [
            "Dividend", "Interest", "Journal", "Wire", "Reinvest",
            "Qual Div Reinvest", "Cash Dividend", "Bank Interest",
        ],
        "date_format": None,
        "number_cleanup": ["$", ","],
        "has_options": False,
        "has_cash_flow": False,
        "source": "seed",
        "version": 1,
        "confidence": 1.0,
        "times_used": 0,
    }


def _wells_fargo_config() -> dict[str, Any]:
    return {
        "config_id": "seed_wells_fargo",
        "format_name": "Wells Fargo Advisors CSV export",
        "header_signature": _signature([
            "Date", "Account", "Activity", "Description", "Amount",
        ]),
        "required_headers": ["Date", "Activity", "Description"],
        "column_map": {
            "date": "Date",
            "ticker": None,  # extracted from Description
            "action": "Activity",
            "quantity": None,  # extracted from Description
            "price": None,  # extracted from Description
            "fees": None,
        },
        "action_map": {
            "BUY": "BUY",
            "SELL": "SELL",
        },
        "skip_actions": [
            "Dividend", "Interest", "Fee", "Journal",
            "Transfer", "Reinvest",
        ],
        "date_format": None,
        "number_cleanup": ["$", ","],
        "has_options": True,
        "has_cash_flow": False,
        "description_parsing": True,
        "source": "seed",
        "version": 1,
        "confidence": 1.0,
        "times_used": 0,
    }


def _signature(headers: list[str]) -> str:
    """Generate a stable header signature from a list of column names.

    Lowercases, sorts, and joins with pipe to create a format fingerprint.
    """
    return "|".join(sorted(h.strip().lower() for h in headers))
