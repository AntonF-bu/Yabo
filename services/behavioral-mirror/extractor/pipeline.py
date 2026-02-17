"""Main extraction pipeline: CSV in -> behavioral profile JSON out."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from extractor.timing import (
    compute_round_trips, holding_period_stats,
    entry_classification, inter_trade_timing,
)
from extractor.sizing import position_size_analysis, reconstruct_portfolio
from extractor.patterns import (
    sector_analysis, ticker_concentration, win_loss_stats,
    exit_pattern_analysis, tax_analysis, pdt_analysis,
    sector_concentration_risk,
)
from extractor.features import (
    compute_trait_scores, compute_stress_response, compute_active_vs_passive,
)

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_market_data(market_data_path: str | Path | None = None) -> pd.DataFrame | None:
    """Load cached market data."""
    if market_data_path:
        p = Path(market_data_path)
    else:
        p = DATA_DIR / "cache" / "market_data.parquet"
    if p.exists():
        return pd.read_parquet(p)
    logger.warning("Market data not found at %s", p)
    return None


def extract_features(
    csv_path: str | Path,
    context: dict[str, Any] | None = None,
    market_data_path: str | Path | None = None,
) -> dict[str, Any]:
    """Extract behavioral profile from a trade CSV.

    Args:
        csv_path: Path to trades CSV with columns:
            trader_id, ticker, action, quantity, price, date, fees
        context: Optional dict with keys:
            tax_jurisdiction, account_size, portfolio_pct_of_net_worth,
            brokerage_platform, options_approval_level
        market_data_path: Optional path to market data parquet.

    Returns:
        Full behavioral profile dict matching the output schema.
    """
    ctx = context or {}
    csv_path = Path(csv_path)
    trades_df = pd.read_csv(csv_path)

    if trades_df.empty:
        logger.warning("Empty trades CSV: %s", csv_path)
        return _empty_profile(csv_path.stem, ctx)

    # Ensure date column is parsed
    trades_df["date"] = pd.to_datetime(trades_df["date"])
    trades_df = trades_df.sort_values("date").reset_index(drop=True)

    trader_id = str(trades_df.iloc[0].get("trader_id", csv_path.stem))
    market_data = _load_market_data(market_data_path)

    # --- Round trips ---
    trips = compute_round_trips(trades_df)
    holding = holding_period_stats(trips)
    entry = entry_classification(trades_df, market_data)
    timing_info = inter_trade_timing(trades_df, trips)

    # --- Sizing ---
    account_size = ctx.get("account_size")
    sizing = position_size_analysis(trades_df, trips, account_size=account_size)

    # --- Patterns ---
    sectors = sector_analysis(trades_df)
    concentration = ticker_concentration(trades_df)
    wl = win_loss_stats(trips)
    exit_pats = exit_pattern_analysis(trips)
    tax = tax_analysis(trips, tax_jurisdiction=ctx.get("tax_jurisdiction"))
    pdt = pdt_analysis(trades_df, account_size=account_size)

    # --- Trade frequency ---
    dates = pd.to_datetime(trades_df["date"])
    date_range_days = max((dates.max() - dates.min()).days, 1)
    trade_freq = len(trades_df) / (date_range_days / 30.0)

    # --- Trait scores ---
    traits = compute_trait_scores(holding, entry, exit_pats, wl, sizing, trips, trade_freq)

    # --- Stress response ---
    stress = compute_stress_response(trips, sizing, timing_info)

    # --- Active vs passive ---
    active_passive = compute_active_vs_passive(trips, market_data)

    # --- Risk profile ---
    portfolio_beta = _compute_portfolio_beta(trips, market_data)
    risk_assessment = _risk_assessment(
        sizing["avg_position_pct"], sizing["max_position_pct"],
        portfolio_beta, sector_concentration_risk(sectors),
        ctx.get("portfolio_pct_of_net_worth"),
    )

    risk_profile = {
        "avg_position_pct": sizing["avg_position_pct"],
        "max_position_pct": sizing["max_position_pct"],
        "position_size_consistency": sizing["position_size_consistency"],
        "portfolio_beta": portfolio_beta,
        "sector_concentration_risk": sector_concentration_risk(sectors),
        "conviction_sizing_detected": sizing["conviction_sizing_detected"],
        "portfolio_pct_of_net_worth": ctx.get("portfolio_pct_of_net_worth"),
        "risk_adjusted_assessment": risk_assessment,
    }

    # --- Confidence ---
    total_trades = len(trades_df)
    confidence = min(100, int(20 + total_trades * 0.5 + len(trips) * 1.0))

    # --- Build output ---
    profile: dict[str, Any] = {
        "trader_id": trader_id,
        "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
        "model_version": "behavioral-mirror-v0.1",
        "traits": traits,
        "patterns": {
            "dominant_sectors": sectors[:5],
            "ticker_concentration": concentration,
            "holding_period": holding,
            "entry_patterns": entry,
            "exit_patterns": exit_pats,
            "win_rate": wl["win_rate"],
            "avg_winner_pct": wl["avg_winner_pct"],
            "avg_loser_pct": wl["avg_loser_pct"],
            "profit_factor": wl["profit_factor"],
            "trade_frequency_per_month": round(trade_freq, 2),
        },
        "stress_response": stress,
        "risk_profile": risk_profile,
        "context_factors": {
            **tax,
            **pdt,
            "brokerage_constraints_detected": [],
            "regulatory_adjustment_notes": "",
        },
        "active_vs_passive": active_passive,
        "metadata": {
            "total_trades": total_trades,
            "date_range": {
                "start": str(dates.min().date()),
                "end": str(dates.max().date()),
            },
            "confidence_score": confidence,
        },
    }

    return profile


def _compute_portfolio_beta(trips: list[dict], market_data: pd.DataFrame | None) -> float:
    """Compute portfolio beta vs SPY."""
    if not trips or market_data is None or "SPY_Return" not in market_data.columns:
        return 1.0

    spy_returns = market_data["SPY_Return"].dropna()
    if spy_returns.empty:
        return 1.0

    # Compute daily portfolio returns from trips
    daily_pnl: dict[pd.Timestamp, float] = {}
    daily_value: dict[pd.Timestamp, float] = {}
    for t in trips:
        entry = t["entry_date"]
        exit_d = t["exit_date"]
        value = t["entry_price"] * t["quantity"]
        hold = max((exit_d - entry).days, 1)
        daily_ret = t["pnl_pct"] / hold

        current = entry
        while current <= exit_d:
            if current in spy_returns.index:
                daily_pnl[current] = daily_pnl.get(current, 0) + daily_ret * value
                daily_value[current] = daily_value.get(current, 0) + value
            current += pd.Timedelta(days=1)

    if not daily_pnl:
        return 1.0

    port_returns = pd.Series({
        d: daily_pnl[d] / daily_value[d] if daily_value.get(d, 0) > 0 else 0
        for d in daily_pnl
    })

    # Align with SPY
    common = port_returns.index.intersection(spy_returns.index)
    if len(common) < 10:
        return 1.0

    p = port_returns[common].values
    s = spy_returns[common].values

    cov = np.cov(p, s)
    if cov.shape == (2, 2) and cov[1, 1] > 0:
        beta = float(cov[0, 1] / cov[1, 1])
        return round(max(-3.0, min(3.0, beta)), 4)

    return 1.0


def _risk_assessment(avg_pos: float, max_pos: float, beta: float,
                     sector_conc: float, nw_pct: float | None) -> str:
    """Generate risk-adjusted assessment string."""
    risk_level = 0
    if avg_pos > 15:
        risk_level += 2
    elif avg_pos > 8:
        risk_level += 1
    if max_pos > 25:
        risk_level += 2
    if abs(beta) > 1.5:
        risk_level += 1
    if sector_conc > 0.5:
        risk_level += 1
    if nw_pct is not None and nw_pct > 50:
        risk_level += 1

    if risk_level >= 5:
        return "aggressive — high concentration and position sizes"
    elif risk_level >= 3:
        return "moderate-high — above-average position sizing"
    elif risk_level >= 1:
        return "moderate — balanced approach"
    else:
        return "conservative — small positions and diversified"


def _empty_profile(trader_id: str, ctx: dict) -> dict[str, Any]:
    """Return a minimal profile for an empty CSV."""
    return {
        "trader_id": trader_id,
        "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
        "model_version": "behavioral-mirror-v0.1",
        "traits": {k: 0 for k in [
            "momentum_score", "value_score", "income_score", "swing_score",
            "day_trading_score", "event_driven_score", "mean_reversion_score",
            "passive_dca_score", "risk_appetite", "discipline",
            "conviction_consistency", "loss_aversion",
        ]},
        "patterns": {},
        "stress_response": {},
        "risk_profile": {},
        "context_factors": {},
        "active_vs_passive": {},
        "metadata": {"total_trades": 0, "date_range": {}, "confidence_score": 0},
    }


def extract_all(
    trades_dir: str | Path,
    output_dir: str | Path,
    context_map: dict[str, dict[str, Any]] | None = None,
    market_data_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Batch-extract all trader CSVs in a directory.

    Args:
        trades_dir: Directory containing {trader_id}.csv files
        output_dir: Directory to write extracted JSON profiles
        context_map: Optional dict of trader_id -> context dict
        market_data_path: Optional path to market data parquet

    Returns:
        List of extracted profiles
    """
    trades_dir = Path(trades_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ctx_map = context_map or {}
    profiles: list[dict[str, Any]] = []

    csv_files = sorted(trades_dir.glob("*.csv"))
    logger.info("Extracting features from %d CSV files …", len(csv_files))

    for csv_path in csv_files:
        trader_id = csv_path.stem
        ctx = ctx_map.get(trader_id, {})

        try:
            profile = extract_features(csv_path, context=ctx, market_data_path=market_data_path)
            profiles.append(profile)

            out_path = output_dir / f"{trader_id}.json"
            with open(out_path, "w") as f:
                json.dump(profile, f, indent=2, default=str)

        except Exception:
            logger.exception("Failed to extract %s", trader_id)

    logger.info("Extracted %d profiles", len(profiles))
    return profiles
