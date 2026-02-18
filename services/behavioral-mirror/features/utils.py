"""Shared utility functions for the 212-feature extraction engine."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ─── Known ETF / leveraged / inverse / sector ETF lists ────────────────────

_ETFS = {
    "SPY", "QQQ", "IWM", "DIA", "VOO", "VTI", "VEA", "VWO", "EFA", "AGG",
    "BND", "TLT", "IEF", "SHY", "GLD", "SLV", "USO", "UNG", "VNQ", "SCHD",
    "VIG", "ARKK", "ARKG", "ARKW", "ARKF", "ARKQ", "XLK", "XLV", "XLE",
    "XLF", "XLI", "XLY", "XLP", "XLB", "XLU", "XLRE", "XLC", "SMH", "SOXX",
    "KWEB", "EEM", "HYG", "LQD", "TIP", "IEMG", "RSP", "MDY", "IJR", "IJH",
    "ITOT", "IXUS", "VXUS", "VGT", "VHT", "VFH", "VDE", "VIS", "VCR",
    "VDC", "VAW", "VOX", "VNQI",
}

_LEVERAGED_ETFS = {
    "TQQQ", "SOXL", "UPRO", "SPXL", "TNA", "LABU", "TECL", "FAS", "NUGT",
    "JNUG", "UDOW", "FNGU", "BULZ", "CURE", "NAIL", "RETL", "DPST", "MIDU",
    "DFEN", "DUSL", "PILL", "UBOT", "WANT",
}

_INVERSE_ETFS = {
    "SH", "SDS", "SQQQ", "SPXS", "SPXU", "TZA", "SOXS", "LABD", "FAZ",
    "SDOW", "FNGD", "PSQ", "DOG", "RWM", "SRTY",
}

_SECTOR_ETFS = {
    "XLK", "XLV", "XLE", "XLF", "XLI", "XLY", "XLP", "XLB", "XLU", "XLRE",
    "XLC", "SMH", "SOXX", "KWEB", "IBB", "IHI", "ITA", "ITB", "IGV", "HACK",
    "ARKK", "ARKG", "ARKW", "ARKF", "ARKQ",
}

# ─── Sector mapping for top ~200 tickers ───────────────────────────────────

_SECTOR_MAP: dict[str, str] = {
    # Technology
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
    "GOOG": "Technology", "META": "Technology", "NVDA": "Technology",
    "TSM": "Technology", "AVGO": "Technology", "ADBE": "Technology",
    "CRM": "Technology", "ORCL": "Technology", "ACN": "Technology",
    "CSCO": "Technology", "INTC": "Technology", "AMD": "Technology",
    "TXN": "Technology", "QCOM": "Technology", "IBM": "Technology",
    "AMAT": "Technology", "NOW": "Technology", "INTU": "Technology",
    "MU": "Technology", "LRCX": "Technology", "KLAC": "Technology",
    "SNPS": "Technology", "CDNS": "Technology", "MRVL": "Technology",
    "NXPI": "Technology", "PANW": "Technology", "CRWD": "Technology",
    "SNOW": "Technology", "NET": "Technology", "PLTR": "Technology",
    "SMCI": "Technology", "APP": "Technology", "SHOP": "Technology",
    "SQ": "Technology", "COIN": "Technology", "MSTR": "Technology",
    "IONQ": "Technology", "SOUN": "Technology", "RKLB": "Technology",
    "ANET": "Technology", "FTNT": "Technology", "ZS": "Technology",
    # Healthcare
    "UNH": "Healthcare", "JNJ": "Healthcare", "LLY": "Healthcare",
    "ABBV": "Healthcare", "MRK": "Healthcare", "TMO": "Healthcare",
    "ABT": "Healthcare", "PFE": "Healthcare", "DHR": "Healthcare",
    "BMY": "Healthcare", "AMGN": "Healthcare", "GILD": "Healthcare",
    "MDT": "Healthcare", "ISRG": "Healthcare", "SYK": "Healthcare",
    "ELV": "Healthcare", "VRTX": "Healthcare", "REGN": "Healthcare",
    "CI": "Healthcare", "BSX": "Healthcare", "ZTS": "Healthcare",
    "BDX": "Healthcare", "HCA": "Healthcare", "MRNA": "Healthcare",
    "INMB": "Healthcare", "DXCM": "Healthcare",
    # Financials
    "BRK-B": "Financials", "JPM": "Financials", "V": "Financials",
    "MA": "Financials", "BAC": "Financials", "WFC": "Financials",
    "GS": "Financials", "MS": "Financials", "SCHW": "Financials",
    "AXP": "Financials", "BLK": "Financials", "C": "Financials",
    "SPGI": "Financials", "CB": "Financials", "MMC": "Financials",
    "PGR": "Financials", "ICE": "Financials", "CME": "Financials",
    "AON": "Financials", "MCO": "Financials", "USB": "Financials",
    "HOOD": "Financials", "SOFI": "Financials",
    # Consumer Discretionary
    "AMZN": "Consumer Discretionary", "TSLA": "Consumer Discretionary",
    "HD": "Consumer Discretionary", "MCD": "Consumer Discretionary",
    "NKE": "Consumer Discretionary", "LOW": "Consumer Discretionary",
    "SBUX": "Consumer Discretionary", "TJX": "Consumer Discretionary",
    "BKNG": "Consumer Discretionary", "CMG": "Consumer Discretionary",
    "GM": "Consumer Discretionary", "F": "Consumer Discretionary",
    "RIVN": "Consumer Discretionary", "LCID": "Consumer Discretionary",
    "ABNB": "Consumer Discretionary", "ROST": "Consumer Discretionary",
    # Consumer Staples
    "PG": "Consumer Staples", "KO": "Consumer Staples",
    "PEP": "Consumer Staples", "COST": "Consumer Staples",
    "WMT": "Consumer Staples", "PM": "Consumer Staples",
    "MO": "Consumer Staples", "MDLZ": "Consumer Staples",
    "CL": "Consumer Staples", "EL": "Consumer Staples",
    "KHC": "Consumer Staples", "GIS": "Consumer Staples",
    "KR": "Consumer Staples", "SYY": "Consumer Staples",
    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy",
    "SLB": "Energy", "EOG": "Energy", "MPC": "Energy",
    "PSX": "Energy", "VLO": "Energy", "OXY": "Energy",
    "HAL": "Energy", "DVN": "Energy", "PXD": "Energy",
    "FANG": "Energy", "HES": "Energy",
    # Industrials
    "GE": "Industrials", "CAT": "Industrials", "HON": "Industrials",
    "UNP": "Industrials", "RTX": "Industrials", "BA": "Industrials",
    "DE": "Industrials", "LMT": "Industrials", "UPS": "Industrials",
    "MMM": "Industrials", "GD": "Industrials", "NOC": "Industrials",
    "EMR": "Industrials", "ITW": "Industrials", "WM": "Industrials",
    "CSX": "Industrials", "NSC": "Industrials", "FDX": "Industrials",
    # Communication Services
    "DIS": "Communication Services", "NFLX": "Communication Services",
    "CMCSA": "Communication Services", "T": "Communication Services",
    "VZ": "Communication Services", "TMUS": "Communication Services",
    "ATVI": "Communication Services", "EA": "Communication Services",
    "TTWO": "Communication Services", "RBLX": "Communication Services",
    "SNAP": "Communication Services", "PINS": "Communication Services",
    # Materials
    "LIN": "Materials", "APD": "Materials", "FCX": "Materials",
    "NEM": "Materials", "NUE": "Materials", "DOW": "Materials",
    "DD": "Materials", "ECL": "Materials", "SHW": "Materials",
    # Utilities
    "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities",
    "D": "Utilities", "AEP": "Utilities", "SRE": "Utilities",
    "EXC": "Utilities", "XEL": "Utilities",
    # Real Estate
    "PLD": "Real Estate", "AMT": "Real Estate", "CCI": "Real Estate",
    "EQIX": "Real Estate", "PSA": "Real Estate", "O": "Real Estate",
    "SPG": "Real Estate", "DLR": "Real Estate",
}

_SECTOR_INT_MAP: dict[str, int] = {
    "Technology": 0, "Healthcare": 1, "Financials": 2,
    "Consumer Discretionary": 3, "Consumer Staples": 4, "Energy": 5,
    "Industrials": 6, "Communication Services": 7, "Materials": 8,
    "Utilities": 9, "Real Estate": 10, "unknown": 11,
}

# Top 10 S&P 500 by market cap (approx)
_MEGA_CAP = {"AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "LLY"}

# Known small-cap / micro-cap tickers (rough proxy)
_SMALL_CAP_PROXY = {
    "IONQ", "SOUN", "RKLB", "INMB", "WISH", "CLOV", "BB", "NOK", "BBBY",
    "DWAC", "LCID", "RIVN", "HOOD", "SOFI", "SMCI",
}

# Meme stocks
MEME_STOCKS = {
    "GME", "AMC", "BBBY", "BB", "NOK", "PLTR", "WISH", "CLOV", "SOFI",
    "RIVN", "LCID", "MSTR", "SMCI", "DWAC", "TRUMP", "HOOD",
}

# Top retail stocks (for copycat score)
TOP_RETAIL_STOCKS = {
    "AAPL", "TSLA", "NVDA", "AMD", "AMZN", "META", "GOOGL", "MSFT",
    "PLTR", "SOFI", "NIO", "GME", "AMC", "SPY", "QQQ", "COIN",
    "RIVN", "LCID", "HOOD", "SQ",
}

# Growth vs value classification (rough)
_GROWTH_TICKERS = {
    "NVDA", "TSLA", "AMD", "SHOP", "SQ", "NET", "SNOW", "CRWD", "PLTR",
    "COIN", "MSTR", "RBLX", "ABNB", "RIVN", "LCID", "IONQ", "SOUN",
    "RKLB", "ARKK", "ARKG", "TQQQ", "META", "AMZN", "GOOGL", "NFLX",
    "CRM", "NOW", "ADBE", "INTU", "PANW", "FTNT", "ZS", "APP", "SMCI",
}

_VALUE_TICKERS = {
    "BRK-B", "JPM", "BAC", "WFC", "JNJ", "PG", "KO", "PEP", "VZ", "T",
    "XOM", "CVX", "MO", "PM", "ABBV", "MRK", "BMY", "PFE", "MMM",
    "IBM", "INTC", "COST", "WMT", "HD", "LOW", "GIS", "KHC",
}

_INCOME_TICKERS = {
    "O", "VNQ", "SCHD", "VIG", "T", "VZ", "MO", "PM", "ABBV", "XOM",
    "CVX", "PG", "KO", "PEP", "JNJ", "DUK", "SO", "NEE", "D",
}

# Recently IPO'd (rough list, 2023-2024 vintage)
_RECENT_IPOS = {
    "ARM", "BIRK", "CART", "CAVA", "KPLT", "KVYO", "TOST", "VFS",
    "IBKR", "RDDT", "ASTERA",
}


def compute_cv(series: pd.Series | np.ndarray) -> float | None:
    """Coefficient of variation. Returns None if insufficient data."""
    arr = np.asarray(series, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) < 2:
        return None
    mean = np.mean(arr)
    if mean == 0:
        return None
    return float(np.std(arr, ddof=1) / abs(mean))


def safe_divide(a: float | None, b: float | None) -> float | None:
    """Safe division returning None if b is 0 or either is None."""
    if a is None or b is None or b == 0:
        return None
    return float(a / b)


def classify_ticker_type(ticker: str) -> str:
    """Classify ticker as stock, etf, option, leveraged_etf, inverse_etf."""
    t = ticker.upper()
    if t in _LEVERAGED_ETFS:
        return "leveraged_etf"
    if t in _INVERSE_ETFS:
        return "inverse_etf"
    if t in _SECTOR_ETFS or t in _ETFS:
        return "etf"
    # Simple heuristic for options: tickers with digits or > 6 chars
    if any(c.isdigit() for c in t) and len(t) > 5:
        return "option"
    return "stock"


def get_sector(ticker: str) -> str:
    """Return GICS sector for known tickers, 'unknown' otherwise."""
    return _SECTOR_MAP.get(ticker.upper(), "unknown")


def get_sector_int(ticker: str) -> int:
    """Return sector as integer encoding."""
    return _SECTOR_INT_MAP.get(get_sector(ticker), 11)


def is_mega_cap(ticker: str) -> bool:
    return ticker.upper() in _MEGA_CAP


def is_small_cap(ticker: str) -> bool:
    return ticker.upper() in _SMALL_CAP_PROXY


def is_meme_stock(ticker: str) -> bool:
    return ticker.upper() in MEME_STOCKS


def is_recent_ipo(ticker: str) -> bool:
    return ticker.upper() in _RECENT_IPOS


def is_growth(ticker: str) -> bool:
    return ticker.upper() in _GROWTH_TICKERS


def is_value(ticker: str) -> bool:
    return ticker.upper() in _VALUE_TICKERS


def is_income(ticker: str) -> bool:
    return ticker.upper() in _INCOME_TICKERS


def estimate_portfolio_value(trades_df: pd.DataFrame) -> pd.Series:
    """Reconstruct approximate portfolio value over time from cumulative trades.

    Returns a Series indexed by date with estimated total portfolio value.
    """
    df = trades_df.sort_values("date").copy()
    if "value" not in df.columns:
        df["value"] = df["price"] * df["quantity"]

    # Walk through trades accumulating cash and holdings
    holdings: dict[str, float] = {}  # ticker -> shares
    dates = sorted(df["date"].unique())
    portfolio_vals: dict[Any, float] = {}

    # Rough estimate: track cumulative investment
    cum_invested = 0.0
    for date in dates:
        day_trades = df[df["date"] == date]
        for _, row in day_trades.iterrows():
            ticker = row["ticker"]
            qty = float(row["quantity"])
            price = float(row["price"])
            action = str(row["action"]).upper()

            if action == "BUY":
                holdings[ticker] = holdings.get(ticker, 0) + qty
                cum_invested += qty * price
            elif action == "SELL":
                holdings[ticker] = holdings.get(ticker, 0) - qty
                cum_invested -= qty * price  # approximate

        # Mark-to-market with last known prices
        total = 0.0
        for ticker, shares in holdings.items():
            if shares > 0:
                # Use the last price we saw for this ticker
                ticker_trades = df[(df["ticker"] == ticker) & (df["date"] <= date)]
                if len(ticker_trades) > 0:
                    last_price = float(ticker_trades.iloc[-1]["price"])
                    total += shares * last_price
        portfolio_vals[date] = max(total, 0)

    if not portfolio_vals:
        return pd.Series(dtype=float)
    return pd.Series(portfolio_vals).sort_index()


def compute_trend(series: pd.Series | np.ndarray) -> float | None:
    """Return slope of linear regression. Positive = increasing, negative = decreasing.

    Returns None if fewer than 3 data points.
    """
    arr = np.asarray(series, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) < 3:
        return None
    x = np.arange(len(arr), dtype=float)
    # Normalize x to [0, 1] to get interpretable slope
    if x[-1] > 0:
        x = x / x[-1]
    try:
        coeffs = np.polyfit(x, arr, 1)
        return float(coeffs[0])
    except (np.linalg.LinAlgError, ValueError):
        return None


def build_position_history(trades_df: pd.DataFrame) -> pd.DataFrame:
    """Reconstruct position-level data from trade history.

    For each ticker, tracks open date, shares accumulated, average cost,
    close date, close price, hold duration, return %. Handles partial closes.

    Returns DataFrame with columns:
        ticker, open_date, close_date, shares, avg_cost, close_price,
        hold_days, return_pct, pnl_usd, is_winner, is_partial_close, is_open
    """
    df = trades_df.sort_values("date").copy()
    positions: list[dict[str, Any]] = []

    # Per-ticker FIFO inventory
    inventory: dict[str, list[dict]] = {}  # ticker -> list of {date, qty, price}

    for _, row in df.iterrows():
        ticker = str(row["ticker"])
        action = str(row["action"]).upper()
        qty = float(row["quantity"])
        price = float(row["price"])
        date = row["date"]

        if action == "BUY":
            if ticker not in inventory:
                inventory[ticker] = []
            inventory[ticker].append({"date": date, "qty": qty, "price": price})

        elif action == "SELL":
            if ticker not in inventory or not inventory[ticker]:
                # Inherited exit - no matching buy
                positions.append({
                    "ticker": ticker,
                    "open_date": pd.NaT,
                    "close_date": date,
                    "shares": qty,
                    "avg_cost": None,
                    "close_price": price,
                    "hold_days": None,
                    "return_pct": None,
                    "pnl_usd": None,
                    "is_winner": None,
                    "is_partial_close": False,
                    "is_open": False,
                })
                continue

            remaining_sell = qty
            lots = inventory[ticker]

            while remaining_sell > 0 and lots:
                lot = lots[0]
                matched = min(remaining_sell, lot["qty"])
                is_partial = lot["qty"] > matched

                open_date = lot["date"]
                if pd.notna(open_date) and pd.notna(date):
                    try:
                        hold = (pd.Timestamp(date) - pd.Timestamp(open_date)).days
                    except Exception:
                        hold = None
                else:
                    hold = None

                cost = lot["price"]
                ret_pct = ((price - cost) / cost * 100) if cost and cost > 0 else None
                pnl = (price - cost) * matched if cost else None

                positions.append({
                    "ticker": ticker,
                    "open_date": open_date,
                    "close_date": date,
                    "shares": matched,
                    "avg_cost": cost,
                    "close_price": price,
                    "hold_days": hold,
                    "return_pct": ret_pct,
                    "pnl_usd": pnl,
                    "is_winner": ret_pct > 0 if ret_pct is not None else None,
                    "is_partial_close": is_partial,
                    "is_open": False,
                })

                lot["qty"] -= matched
                remaining_sell -= matched
                if lot["qty"] <= 0:
                    lots.pop(0)

    # Mark remaining inventory as open positions
    for ticker, lots in inventory.items():
        for lot in lots:
            if lot["qty"] > 0:
                positions.append({
                    "ticker": ticker,
                    "open_date": lot["date"],
                    "close_date": pd.NaT,
                    "shares": lot["qty"],
                    "avg_cost": lot["price"],
                    "close_price": None,
                    "hold_days": None,
                    "return_pct": None,
                    "pnl_usd": None,
                    "is_winner": None,
                    "is_partial_close": False,
                    "is_open": True,
                })

    if not positions:
        return pd.DataFrame(columns=[
            "ticker", "open_date", "close_date", "shares", "avg_cost",
            "close_price", "hold_days", "return_pct", "pnl_usd",
            "is_winner", "is_partial_close", "is_open",
        ])

    result = pd.DataFrame(positions)
    return result
