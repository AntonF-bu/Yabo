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
    sector_concentration_risk, set_resolved_sectors,
)
from extractor.features import (
    compute_trait_scores, compute_stress_response, compute_active_vs_passive,
    compute_options_profile, compute_options_round_trips,
    compute_instruments_summary, adjust_traits_for_options,
)
from extractor.csv_parsers import normalize_csv, normalize_csv_with_metadata
from extractor.ticker_resolver import (
    resolve_batch, enrich_market_data, ensure_market_data_for_tickers,
)
from extractor.holdings_profile import compute_holdings_profile

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
    pre_parsed_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Extract behavioral profile from a trade CSV.

    Args:
        csv_path: Path to trades CSV with columns:
            trader_id, ticker, action, quantity, price, date, fees
        context: Optional dict with keys:
            tax_jurisdiction, account_size, portfolio_pct_of_net_worth,
            brokerage_platform, options_approval_level
        market_data_path: Optional path to market data parquet.
        pre_parsed_df: Optional pre-normalized DataFrame (skips CSV parsing).

    Returns:
        Full behavioral profile dict matching the output schema.
    """
    ctx = context or {}
    csv_path = Path(csv_path)

    # Use pre-parsed df or normalize from CSV
    csv_format = "unknown"
    cash_flow_metadata = None
    option_trades: list[dict[str, Any]] = []
    if pre_parsed_df is not None:
        trades_df = pre_parsed_df.copy()
        csv_format = "pre_parsed"
    else:
        try:
            trades_df, csv_format, raw_metadata = normalize_csv_with_metadata(csv_path)
            if raw_metadata:
                cash_flow_metadata = raw_metadata.get("cash_flow")
                option_trades = raw_metadata.get("option_trades", [])
        except Exception as e:
            logger.warning("CSV normalization failed, falling back to basic read: %s", e)
            trades_df = pd.read_csv(csv_path)
            csv_format = "basic_fallback"

    if trades_df.empty:
        logger.warning("Empty trades CSV: %s", csv_path)
        return _empty_profile(csv_path.stem, ctx)

    # Deduplicate identical rows (real brokerage exports sometimes have dupes)
    n_before = len(trades_df)
    trades_df = trades_df.drop_duplicates()
    n_dupes = n_before - len(trades_df)
    if n_dupes > 0:
        logger.info("Removed %d duplicate trade records from %s", n_dupes, csv_path.name)

    # Ensure date column is parsed
    trades_df["date"] = pd.to_datetime(trades_df["date"])
    trades_df = trades_df.sort_values("date").reset_index(drop=True)

    # Ensure required columns exist
    if "fees" not in trades_df.columns:
        trades_df["fees"] = 0.0

    trader_id = str(trades_df.iloc[0].get("trader_id", csv_path.stem))

    # --- Dynamic ticker resolution ---
    unique_tickers = trades_df["ticker"].unique().tolist()
    resolved = resolve_batch(unique_tickers)
    sector_map = {sym: info.get("sector", "Unknown") for sym, info in resolved.items()}
    set_resolved_sectors(sector_map)

    # --- Holdings profile (what the trader buys) ---
    holdings_profile = compute_holdings_profile(trades_df, resolved)

    # --- Load and enrich market data ---
    # First try the pre-cached parquet (for batch/synthetic runs)
    dates_for_range = pd.to_datetime(trades_df["date"])
    start_str = str((dates_for_range.min() - pd.Timedelta(days=60)).date())
    end_str = str((dates_for_range.max() + pd.Timedelta(days=5)).date())

    market_data = _load_market_data(market_data_path)
    if market_data is not None:
        logger.info("[MARKET DATA] Loaded pre-cached parquet, enriching with trade tickers")
        market_data = enrich_market_data(market_data, unique_tickers, start_str, end_str)
    else:
        # No pre-cached parquet — blocking fetch for all tickers
        logger.info("[MARKET DATA] No pre-cached parquet — fetching live data for %d tickers", len(unique_tickers))
        market_data = ensure_market_data_for_tickers(
            unique_tickers, start_str, end_str,
        )

    if market_data is not None:
        logger.info(
            "[MARKET DATA] Ready: %d columns, %d rows",
            len(market_data.columns), len(market_data),
        )
    else:
        logger.warning("[MARKET DATA] WARNING: No market data available — entry patterns will be flat")

    # --- Round trips (classifies inherited exits, then FIFO matches) ---
    rt_result = compute_round_trips(trades_df)
    trips = rt_result["closed"]
    open_positions = rt_result["open_positions"]
    open_count = rt_result["open_count"]
    open_pct = rt_result["open_pct"]
    inherited_summary = rt_result["inherited"]
    data_completeness = rt_result["data_completeness"]

    holding = holding_period_stats(trips)
    entry = entry_classification(trades_df, market_data)
    timing_info = inter_trade_timing(trades_df, trips)

    # --- Sizing ---
    account_size = ctx.get("account_size")
    sizing = position_size_analysis(
        trades_df, trips,
        account_size=account_size,
        cash_flow_metadata=cash_flow_metadata,
    )

    # --- Patterns ---
    sectors = sector_analysis(trades_df)
    concentration = ticker_concentration(trades_df)
    wl = win_loss_stats(trips)
    exit_pats = exit_pattern_analysis(trips)
    tax = tax_analysis(trips, tax_jurisdiction=ctx.get("tax_jurisdiction"))
    pdt = pdt_analysis(trades_df, account_size=account_size)

    # --- Enrich inherited positions with sector data ---
    inherited_positions_output: dict[str, Any] | None = None
    if inherited_summary.get("count", 0) > 0:
        inherited_positions_output = _enrich_inherited_summary(
            inherited_summary, resolved,
        )

    # --- Trade frequency ---
    dates = pd.to_datetime(trades_df["date"])
    date_range_days = max((dates.max() - dates.min()).days, 1)
    trade_freq = len(trades_df) / (date_range_days / 30.0)

    # --- Trait scores ---
    traits = compute_trait_scores(
        holding, entry, exit_pats, wl, sizing, trips, trade_freq,
        holdings_profile=holdings_profile,
    )

    # --- Options profile ---
    options_profile: dict[str, Any] | None = None
    option_round_trips: list[dict[str, Any]] = []
    if option_trades:
        options_profile = compute_options_profile(
            option_trades,
            estimated_portfolio_value=sizing.get("estimated_portfolio_value"),
        )
        option_round_trips = compute_options_round_trips(option_trades)

        # Merge option round trips into main trips for performance metrics
        if option_round_trips:
            trips = trips + option_round_trips
            logger.info("[OPTIONS] Added %d option round trips to %d equity trips",
                        len(option_round_trips), len(trips) - len(option_round_trips))
            # Recompute win/loss stats with combined trips
            wl = win_loss_stats(trips)

        # Adjust archetype scores based on options activity
        traits = adjust_traits_for_options(traits, options_profile)

    # --- Instruments summary ---
    equity_volume = float((trades_df["price"] * trades_df["quantity"]).sum())
    etf_count = sum(
        1 for _, row in trades_df.iterrows()
        if resolved.get(row["ticker"], {}).get("instrument_type") == "ETF"
    )
    instruments_summary = compute_instruments_summary(
        equity_count=len(trades_df),
        option_count=len(option_trades),
        equity_tickers=len(unique_tickers),
        option_underlyings=len(set(
            t.get("underlying_ticker", "") for t in option_trades
        )) if option_trades else 0,
        equity_volume=equity_volume,
        total_premium=options_profile["total_premium_deployed"] if options_profile else 0,
        etf_count=etf_count,
        resolved=resolved,
    )

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
        "estimated_portfolio_value": sizing.get("estimated_portfolio_value"),
        "portfolio_value_source": sizing.get("portfolio_value_source"),
    }

    # --- Confidence ---
    total_trades = len(trades_df)
    confidence = min(100, int(20 + total_trades * 0.5 + len(trips) * 1.0))

    # --- Confidence tier ---
    confidence_tier = _determine_confidence_tier(total_trades)

    # --- Open positions summary ---
    open_positions_summary: dict[str, Any] | None = None
    if open_positions:
        total_cost_basis = sum(p["total_cost"] for p in open_positions)
        open_tickers = sorted(set(p["ticker"] for p in open_positions))
        avg_days = (
            sum(p["days_held"] for p in open_positions) / len(open_positions)
        )
        open_positions_summary = {
            "count": open_count,
            "total_cost_basis": round(total_cost_basis, 2),
            "pct_of_trades": open_pct,
            "tickers": open_tickers,
            "avg_days_held": round(avg_days, 1),
            "note": (
                f"Performance metrics computed on {len(trips)} closed trades only. "
                f"{open_count} positions remain open."
            ),
        }

    # --- Performance data quality warning ---
    perf_note: str | None = None
    if data_completeness["score"] == "partial" and len(trips) < 5:
        perf_note = (
            f"Only {len(trips)} closed round trips in data window. "
            f"Insufficient for reliable performance metrics."
        )

    # --- Build output ---
    profile: dict[str, Any] = {
        "trader_id": trader_id,
        "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
        "model_version": "behavioral-mirror-v0.5",
        "traits": traits,
        "holdings_profile": holdings_profile,
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
        "data_completeness": data_completeness,
        "metadata": {
            "total_trades": total_trades,
            "date_range": {
                "start": str(dates.min().date()),
                "end": str(dates.max().date()),
            },
            "confidence_score": confidence,
            "csv_format": csv_format,
        },
        "confidence_metadata": {
            "total_trades": total_trades,
            "round_trips": len(trips),
            "confidence_tier": confidence_tier,
            "unique_tickers": len(unique_tickers),
            "tickers_resolved": sum(1 for v in resolved.values() if v.get("source") != "fallback"),
            "tickers_unknown": sum(1 for v in resolved.values() if v.get("sector") == "Unknown"),
            "inherited_exits": inherited_summary.get("count", 0),
            "data_completeness": data_completeness["score"],
        },
    }

    if perf_note:
        profile["patterns"]["performance_note"] = perf_note

    if open_positions_summary:
        profile["open_positions"] = open_positions_summary

    if inherited_positions_output:
        profile["inherited_positions"] = inherited_positions_output

    if options_profile:
        profile["options_profile"] = options_profile

    if instruments_summary.get("multi_instrument_trader"):
        profile["instruments_summary"] = instruments_summary

    return profile


def _enrich_inherited_summary(
    inherited_summary: dict[str, Any],
    resolved_tickers: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Enrich inherited position summary with sector data.

    Inherited exits don't have performance metrics, but they reveal
    portfolio rotation — which sectors the trader is exiting.
    """
    exits = inherited_summary.get("exits", [])
    if not exits:
        return inherited_summary

    # Group by sector
    sectors_exited: dict[str, dict[str, Any]] = {}
    for e in exits:
        ticker = e["ticker"]
        info = resolved_tickers.get(ticker, {})
        sector = info.get("sector", "Unknown")

        if sector not in sectors_exited:
            sectors_exited[sector] = {"tickers": [], "proceeds": 0.0, "count": 0}
        if ticker not in sectors_exited[sector]["tickers"]:
            sectors_exited[sector]["tickers"].append(ticker)
        sectors_exited[sector]["proceeds"] += e["total"]
        sectors_exited[sector]["count"] += 1

    # Round proceeds
    for sec in sectors_exited.values():
        sec["proceeds"] = round(sec["proceeds"], 2)

    # Build interpretation
    sorted_sectors = sorted(sectors_exited.items(), key=lambda x: x[1]["proceeds"], reverse=True)
    top_sectors = [f"{s} ({d['proceeds']:,.0f})" for s, d in sorted_sectors[:3]]

    return {
        "count": inherited_summary["count"],
        "tickers": inherited_summary["tickers"],
        "total_proceeds": inherited_summary["total_proceeds"],
        "avg_exit_size": inherited_summary.get("avg_exit_size", 0),
        "sectors_exited": sectors_exited,
        "note": inherited_summary["note"],
        "interpretation": (
            f"Liquidating positions in {', '.join(top_sectors)}. "
            f"These {inherited_summary['count']} exits predate the data window "
            f"and indicate longer-term holdings being unwound."
        ),
    }


def _determine_confidence_tier(total_trades: int) -> str:
    """Determine confidence tier based on trade count.

    Tiers:
        insufficient: <15 trades — skip Claude, return template
        preliminary: 15-29 trades — heavy hedging
        emerging: 30-74 trades — moderate hedging
        developing: 75-149 trades — light hedging
        confident: 150+ trades — definitive language
    """
    if total_trades < 15:
        return "insufficient"
    elif total_trades < 30:
        return "preliminary"
    elif total_trades < 75:
        return "emerging"
    elif total_trades < 150:
        return "developing"
    else:
        return "confident"


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
        "model_version": "behavioral-mirror-v0.4",
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
