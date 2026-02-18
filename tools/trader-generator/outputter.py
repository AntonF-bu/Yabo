"""
Converts each trader's simulated trade history into Trading212-format
CSV files, plus generates the answer_key JSON and summary.txt.
"""

import json
import os
import datetime
from typing import Any, Dict, List

import pandas as pd

# ---------------------------------------------------------------------------
# Trading212 CSV format
# ---------------------------------------------------------------------------

HEADER = "Action,Time,Ticker,No. of shares,Price / share,Currency (Price / share),Result (GBP)"


def _format_action(trade: Dict[str, Any]) -> str:
    """Map internal action + order_type to Trading212 column value."""
    action = trade["action"]  # "buy" or "sell"
    order = trade.get("order_type", "Market")  # "Market" or "Limit"
    return f"{order} {action}"


def _format_time(dt: pd.Timestamp) -> str:
    """Format datetime as Trading212 expects: YYYY-MM-DD HH:MM:SS"""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _format_shares(shares: float) -> str:
    """Format share count — remove trailing zeros but keep fractional precision."""
    if shares == int(shares):
        return str(int(shares))
    return f"{shares:.6f}".rstrip("0").rstrip(".")


def _format_price(price: float) -> str:
    return f"{price:.4f}".rstrip("0").rstrip(".")


def trade_to_csv_row(trade: Dict[str, Any]) -> str:
    """Convert a single trade dict to a CSV row string."""
    action = _format_action(trade)
    time_str = _format_time(trade["date"])
    ticker = trade["ticker"]
    shares = _format_shares(trade["shares"])
    price = _format_price(trade["price"])
    currency = "USD"
    result = ""
    if trade["action"] == "sell" and trade.get("result_gbp", 0) != 0:
        result = f"{trade['result_gbp']:.2f}"

    return f"{action},{time_str},{ticker},{shares},{price},{currency},{result}"


# ---------------------------------------------------------------------------
# File writers
# ---------------------------------------------------------------------------

def write_trader_csv(trades: List[Dict[str, Any]], filepath: str):
    """Write a single trader's trades to a Trading212-format CSV."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    # Sort trades by date
    sorted_trades = sorted(trades, key=lambda t: t["date"])
    lines = [HEADER]
    for trade in sorted_trades:
        lines.append(trade_to_csv_row(trade))
    with open(filepath, "w", newline="") as f:
        f.write("\n".join(lines) + "\n")


def write_answer_key(traders: List[Dict[str, Any]], filepath: str):
    """Write the full personality data for all traders to JSON."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    # Convert any non-serialisable types
    serialisable = []
    for t in traders:
        entry = {}
        for k, v in t.items():
            if k == "life_events":
                entry[k] = v  # already dicts
            elif isinstance(v, (dict, list, str, int, float, bool)):
                entry[k] = v
            else:
                entry[k] = str(v)
        serialisable.append(entry)

    with open(filepath, "w") as f:
        json.dump(serialisable, f, indent=2)


def write_summary(traders: List[Dict[str, Any]],
                  all_trades: Dict[int, List[Dict[str, Any]]],
                  output_dir: str):
    """Write summary.txt with quick stats about the generation run."""
    filepath = os.path.join(output_dir, "summary.txt")

    total_trades = sum(len(t) for t in all_trades.values())
    trade_counts = [len(t) for t in all_trades.values()]

    lines = [
        "=== Trader Generator Summary ===",
        f"Generated: {datetime.datetime.now().isoformat()}",
        f"Traders: {len(traders)}",
        f"Total trades: {total_trades}",
        f"Avg trades/trader: {total_trades / max(1, len(traders)):.1f}",
        f"Min trades: {min(trade_counts) if trade_counts else 0}",
        f"Max trades: {max(trade_counts) if trade_counts else 0}",
        f"Median trades: {sorted(trade_counts)[len(trade_counts)//2] if trade_counts else 0}",
        "",
        "=== Trade Count Distribution ===",
    ]

    # Histogram buckets
    buckets = [(0, 25), (25, 50), (50, 100), (100, 200), (200, 400), (400, 800), (800, 2000)]
    for lo, hi in buckets:
        count = sum(1 for c in trade_counts if lo <= c < hi)
        if count > 0:
            lines.append(f"  {lo:>4}-{hi:>4} trades: {count} traders")

    lines.append("")
    lines.append("=== Date Range ===")
    all_dates = []
    for trades in all_trades.values():
        for t in trades:
            if isinstance(t["date"], pd.Timestamp):
                all_dates.append(t["date"])
    if all_dates:
        lines.append(f"  First trade: {min(all_dates).date()}")
        lines.append(f"  Last trade:  {max(all_dates).date()}")

    lines.append("")
    lines.append("=== Time Availability Breakdown ===")
    for level in ["very_low", "low", "medium", "high", "full_time"]:
        count = sum(1 for t in traders if t["time_availability"] == level)
        if count > 0:
            lines.append(f"  {level}: {count} traders")

    lines.append("")
    lines.append("=== Sector Breakdown ===")
    sector_counts: Dict[str, int] = {}
    for t in traders:
        s = t["job_sector"]
        sector_counts[s] = sector_counts.get(s, 0) + 1
    for sector in sorted(sector_counts, key=sector_counts.get, reverse=True):
        lines.append(f"  {sector}: {sector_counts[sector]} traders")

    lines.append("")
    lines.append("=== Account Size Distribution ===")
    sizes = [t["account_size"] for t in traders]
    if sizes:
        lines.append(f"  Min:    ${min(sizes):>12,.2f}")
        lines.append(f"  Median: ${sorted(sizes)[len(sizes)//2]:>12,.2f}")
        lines.append(f"  Max:    ${max(sizes):>12,.2f}")
        lines.append(f"  Mean:   ${sum(sizes)/len(sizes):>12,.2f}")

    with open(filepath, "w") as f:
        f.write("\n".join(lines) + "\n")

    return filepath
