"""FastAPI service for the Behavioral Mirror — Schema V2.

Single entry point: POST /process-upload { upload_id }
Reads file from Supabase Storage, detects format, parses,
writes normalized data (trades, holdings, income, fees),
runs analysis pipelines, stores results in analysis_results.
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Startup env-var check ───────────────────────────────────────────────────
logger.info(
    "[STARTUP] Env check: SUPABASE_URL=%s, SUPABASE_SERVICE_KEY=%s, ANTHROPIC_API_KEY=%s",
    "set" if os.environ.get("SUPABASE_URL") else "missing",
    "set" if os.environ.get("SUPABASE_SERVICE_KEY") else "missing",
    "set" if os.environ.get("ANTHROPIC_API_KEY") else "missing",
)

app = FastAPI(
    title="Behavioral Mirror",
    description="Trading behavior analysis service for Yabo — Schema V2",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://yabo-five.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

DATA_DIR = Path(__file__).resolve().parent / "data"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SERVICE_DIR = Path(__file__).resolve().parent

# Ensure backend.* imports work:
# - Local dev: repo root has backend/ → add REPO_ROOT
# - Railway Docker: /app has backend/ → add SERVICE_DIR (/app)
for p in (REPO_ROOT, SERVICE_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Startup import check — 212-feature engine
_FEATURES_AVAILABLE = False
try:
    from features.coordinator import extract_all_features, get_features_grouped  # noqa: F401
    _FEATURES_AVAILABLE = True
    logger.info("[STARTUP] 212-feature engine loaded successfully")
except Exception as _feat_err:
    logger.error("[STARTUP] 212-feature engine FAILED to load: %s", _feat_err, exc_info=True)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _get_supabase():
    """Get the Supabase client (service role)."""
    from storage.supabase_client import _get_client
    return _get_client()


def _update_upload(client: Any, upload_id: str, updates: dict) -> None:
    """Update an upload row in Supabase."""
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    client.table("uploads").update(updates).eq("id", upload_id).execute()


def _run_new_features(trades_df: "pd.DataFrame") -> dict[str, Any] | None:
    """Run the 212-feature extraction on a trades DataFrame."""
    try:
        import numpy as np
        from features.coordinator import extract_all_features

        if trades_df is None or len(trades_df) == 0:
            return None

        # Create MarketDataService backed by Supabase for classification lookups + price data
        market_data = None
        try:
            from services.market_data import MarketDataService
            market_data = MarketDataService()
        except Exception as mds_err:
            logger.warning("[NEW_FEATURES] MarketDataService unavailable: %s (falling back to legacy)", mds_err)

        logger.info("[NEW_FEATURES] Running on %d trades", len(trades_df))
        features = extract_all_features(trades_df, market_data=market_data)

        sanitized: dict[str, Any] = {}
        for k, v in features.items():
            if isinstance(v, (np.integer,)):
                sanitized[k] = int(v)
            elif isinstance(v, (np.floating,)):
                sanitized[k] = None if np.isnan(v) else float(v)
            elif isinstance(v, (np.bool_,)):
                sanitized[k] = bool(v)
            elif isinstance(v, np.ndarray):
                sanitized[k] = v.tolist()
            else:
                sanitized[k] = v

        return sanitized
    except Exception as e:
        logger.error("[NEW_FEATURES] Extraction failed: %s", e, exc_info=True)
        return None


# ─── Endpoints ───────────────────────────────────────────────────────────────


@app.get("/health")
def health() -> dict[str, Any]:
    from storage.supabase_client import is_configured as supa_ok
    return {
        "status": "ok",
        "version": "2.0.0",
        "supabase_connected": supa_ok(),
        "features_available": _FEATURES_AVAILABLE,
    }


class ProcessUploadRequest(BaseModel):
    upload_id: str


@app.post("/process-upload")
async def process_upload(req: ProcessUploadRequest) -> JSONResponse:
    """Full processing pipeline for a single upload.

    1. Read upload record from Supabase
    2. Download file from Supabase Storage
    3. Detect format (format_signatures or Claude)
    4. Parse file (WFA parser or universal parser)
    5. Write normalized data (trades_new, holdings, income, fees)
    6. Run analysis (behavioral + portfolio)
    7. Store results in analysis_results
    """
    client = _get_supabase()
    if not client:
        return JSONResponse({"error": "Supabase not configured"}, status_code=503)

    upload_id = req.upload_id

    # ── Step 1: Read upload record ───────────────────────────────────────
    try:
        resp = (
            client.table("uploads")
            .select("*")
            .eq("id", upload_id)
            .single()
            .execute()
        )
        upload = resp.data
    except Exception as e:
        return JSONResponse({"error": f"Upload not found: {e}"}, status_code=404)

    if not upload:
        return JSONResponse({"error": "Upload not found"}, status_code=404)

    profile_id = upload["profile_id"]
    file_path = upload["file_path"]
    file_name = upload["file_name"]

    logger.info("[PROCESS] Starting upload %s for profile %s: %s", upload_id, profile_id, file_name)

    # ── Reprocess support: clean up previous data if re-running ───────
    if upload.get("status") in ("completed", "error", "partial"):
        logger.info("[PROCESS] Reprocessing: clearing previous data for profile %s", profile_id)
        for tbl in ("trades_new", "holdings", "income", "fees", "analysis_results"):
            try:
                client.table(tbl).delete().eq("profile_id", profile_id).execute()
            except Exception:
                logger.warning("[PROCESS] Failed to clear %s for %s (may not exist)", tbl, profile_id)

    _update_upload(client, upload_id, {
        "status": "classifying",
        "processing_started_at": datetime.now(timezone.utc).isoformat(),
    })

    # ── Step 2: Download file from Supabase Storage ──────────────────────
    tmp_path = None
    try:
        file_bytes = client.storage.from_("uploads").download(file_path)
        if not file_bytes:
            _update_upload(client, upload_id, {"status": "error", "error_message": "File not found in storage"})
            return JSONResponse({"error": "File not found in storage"}, status_code=404)

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        logger.info("[PROCESS] Downloaded %d bytes to %s", len(file_bytes), tmp_path)
    except Exception as e:
        logger.exception("[PROCESS] Download failed")
        _update_upload(client, upload_id, {"status": "error", "error_message": f"Download failed: {e}"})
        return JSONResponse({"error": f"Download failed: {e}"}, status_code=500)

    try:
        # ── Step 3: Detect format ────────────────────────────────────────
        file_content = Path(tmp_path).read_text(errors="replace")

        from backend.parsers.format_detector import FormatDetector
        detector = FormatDetector(client)
        fmt = detector.detect(file_content, file_name)

        _update_upload(client, upload_id, {
            "status": "classified",
            "classified_as": "activity_export" if "trades" in fmt.data_types else "unknown",
            "brokerage_detected": fmt.brokerage,
            "format_signature_id": fmt.signature_id,
        })

        logger.info("[PROCESS] Format: %s (%s), new=%s", fmt.format_name, fmt.brokerage, fmt.is_new)

        # ── Step 4: Parse the file ───────────────────────────────────────
        from backend.parsers.wfa_activity import WFAActivityParser
        from backend.parsers.instrument_classifier import classify as classify_instrument
        from backend.parsers.holdings_reconstructor import reconstruct
        from backend.analyzers.portfolio_analyzer import analyze_portfolio, compute_metrics

        parser = WFAActivityParser()
        transactions = parser.parse_csv(tmp_path)

        if not transactions:
            _update_upload(client, upload_id, {"status": "error", "error_message": "No transactions parsed"})
            return JSONResponse({"error": "No transactions parsed"}, status_code=400)

        logger.info("[PROCESS] Parsed %d transactions", len(transactions))

        snapshot = reconstruct(transactions)

        # ── Step 4b: Run intelligent parsing orchestrator ────────────────
        # Wraps parser output with pattern memory, Claude fallback, and
        # review queue.  Does NOT replace the existing parser — it enriches.
        enrichment_by_idx: dict[int, dict] = {}
        parsing_stats: dict[str, Any] = {}
        completeness_report: dict[str, Any] = {}
        try:
            from parsing.orchestrator import parse_with_intelligence

            # Build dicts the orchestrator understands
            raw_csv_rows = []
            for i, t in enumerate(transactions):
                ic = classify_instrument(t.symbol, t.description, t.action)
                raw_text = " ".join(str(v) for v in t.raw_row.values() if v) if t.raw_row else t.description
                # Serialize option_details for the orchestrator
                opt_details_dict = None
                if ic.option_details:
                    od = ic.option_details
                    opt_details_dict = {
                        "underlying": od.underlying,
                        "option_type": od.option_type,
                        "strike": od.strike,
                        "expiry_year": od.expiry_year,
                        "expiry_month": od.expiry_month,
                        "expiry_day": od.expiry_day,
                    }
                raw_csv_rows.append({
                    "action": t.action,
                    "symbol": t.symbol,
                    "description": t.description,
                    "quantity": t.quantity,
                    "price": t.price,
                    "amount": t.amount,
                    "raw_action": t.raw_action,
                    "raw_text": raw_text,
                    "instrument_type": ic.instrument_type,
                    "instrument_confidence": ic.confidence,
                    "option_details": opt_details_dict,
                })

            # Account positions from reconstructed snapshot
            account_positions = {
                pos.symbol: float(pos.quantity)
                for pos in snapshot.positions.values()
                if pos.quantity
            }

            orch_result = await parse_with_intelligence(
                raw_csv_rows=raw_csv_rows,
                brokerage=fmt.brokerage or "unknown",
                account_positions=account_positions,
                trader_id=profile_id,
                import_id=upload_id,
            )

            # Build enrichment lookup by original index
            for enriched_txn in orch_result.get("transactions", []):
                idx = enriched_txn.get("index")
                if idx is not None:
                    enrichment_by_idx[idx] = enriched_txn

            parsing_stats = orch_result.get("stats", {})
            review_needed = orch_result.get("review_needed", [])
            completeness_report = orch_result.get("completeness", {})

            logger.info(
                "[PARSING STATS] total=%d L1=%d L2=%d L3=%d memory=%d learned=%d strategies=%d positions=%d",
                parsing_stats.get("total", 0),
                parsing_stats.get("layer1_resolved", 0),
                parsing_stats.get("layer2_resolved", 0),
                parsing_stats.get("layer3_flagged", 0),
                parsing_stats.get("memory_hits", 0),
                parsing_stats.get("new_patterns_learned", 0),
                parsing_stats.get("strategies_detected", 0),
                parsing_stats.get("positions_tracked", 0),
            )
            if review_needed:
                logger.info("[PARSING STATS] %d transactions flagged for review", len(review_needed))
        except Exception:
            logger.warning("[PROCESS] Intelligent parsing layer failed (non-fatal, using parser output as-is)", exc_info=True)

        # ── Step 5: Write normalized data to Supabase ────────────────────
        data_types_written: list[str] = []

        # -- Trades (buy/sell) --
        trade_rows = []
        for i, t in enumerate(transactions):
            if t.action in ("buy", "sell"):
                ic = classify_instrument(t.symbol, t.description, t.action)
                details: dict[str, Any] = {"reason": ic.reason, "confidence": ic.confidence}
                if ic.sub_type:
                    details["sub_type"] = ic.sub_type
                if ic.option_details:
                    od = ic.option_details
                    details["underlying"] = od.underlying
                    details["option_type"] = od.option_type
                    details["strike"] = od.strike
                    details["expiry"] = f"{od.expiry_year}-{od.expiry_month:02d}-{od.expiry_day:02d}"

                # Premium accounting for options:
                # Sold option premium is income received, not loss.
                # The negative sign in WFA CSVs is formatting, not P&L.
                is_option = ic.instrument_type == "options"
                trade_price = t.price
                trade_amount = t.amount

                if is_option and t.action == "sell":
                    details["premium_type"] = "collected"
                    # Ensure amount is recorded as positive income
                    if trade_amount and trade_amount < 0:
                        trade_amount = abs(trade_amount)
                    if trade_price and trade_price < 0:
                        trade_price = abs(trade_price)
                elif is_option and t.action == "buy":
                    details["premium_type"] = "paid"
                    # Bought option: premium paid is an outflow (negative)
                    if trade_amount and trade_amount > 0:
                        trade_amount = -abs(trade_amount)

                # Merge enrichment from intelligent parsing layer
                enrichment = enrichment_by_idx.get(i, {})
                if enrichment:
                    if enrichment.get("strategy"):
                        details["strategy"] = enrichment["strategy"]
                    if enrichment.get("strategy_name"):
                        details["strategy_name"] = enrichment["strategy_name"]
                    if enrichment.get("is_closing") is not None:
                        details["is_closing"] = enrichment["is_closing"]
                    if enrichment.get("is_opening") is not None:
                        details["is_opening"] = enrichment["is_opening"]
                    if enrichment.get("position_direction"):
                        details["position_direction"] = enrichment["position_direction"]
                    if enrichment.get("classified_by"):
                        details["classified_by"] = enrichment["classified_by"]
                    if enrichment.get("confidence"):
                        details["parsing_confidence"] = enrichment["confidence"]
                    # If Claude or memory provided a more specific action, record it
                    enriched_action = enrichment.get("action")
                    if enriched_action and enriched_action != t.action:
                        details["enriched_action"] = enriched_action

                trade_rows.append({
                    "profile_id": profile_id,
                    "upload_id": upload_id,
                    "date": t.date.isoformat(),
                    "account_id": t.account,
                    "account_type": t.account_type,
                    "side": t.action,
                    "ticker": t.symbol,
                    "description": t.description,
                    "quantity": t.quantity,
                    "price": trade_price,
                    "amount": trade_amount,
                    "fees": t.fees,
                    "instrument_type": ic.instrument_type,
                    "instrument_details": details,
                })
        if trade_rows:
            client.table("trades_new").insert(trade_rows).execute()
            data_types_written.append("trades")
            logger.info("[PROCESS] Wrote %d trade rows", len(trade_rows))

        # -- Income (dividend, interest, reinvest) --
        income_rows = []
        for t in transactions:
            if t.action in ("dividend", "interest", "reinvest"):
                # Classify income type
                income_type = t.action
                if t.action == "interest":
                    desc_lower = (t.description or "").lower()
                    if "muni" in desc_lower or "municipal" in desc_lower:
                        income_type = "muni_interest"
                    elif "money market" in desc_lower or "sweep" in desc_lower:
                        income_type = "money_market"
                    else:
                        income_type = "corporate_interest"

                income_rows.append({
                    "profile_id": profile_id,
                    "upload_id": upload_id,
                    "date": t.date.isoformat(),
                    "account_id": t.account,
                    "account_type": t.account_type,
                    "income_type": income_type,
                    "ticker": t.symbol,
                    "amount": t.amount,
                    "description": t.description,
                })
        if income_rows:
            client.table("income").insert(income_rows).execute()
            data_types_written.append("income")
            logger.info("[PROCESS] Wrote %d income rows", len(income_rows))

        # -- Fees --
        fee_rows = []
        for t in transactions:
            if t.action in ("fee", "withholding"):
                fee_rows.append({
                    "profile_id": profile_id,
                    "upload_id": upload_id,
                    "date": t.date.isoformat(),
                    "account_id": t.account,
                    "fee_type": "advisory" if t.action == "fee" else "withholding",
                    "amount": t.amount,
                    "description": t.description,
                })
        if fee_rows:
            client.table("fees").insert(fee_rows).execute()
            data_types_written.append("fees")
            logger.info("[PROCESS] Wrote %d fee rows", len(fee_rows))

        # -- Holdings (reconstructed positions) --
        holding_rows = []
        max_date = max(t.date for t in transactions)
        for pos in snapshot.positions.values():
            if pos.quantity and pos.quantity != 0:
                inst_type = None
                inst_details: dict[str, Any] = {}
                if hasattr(pos, "instrument") and pos.instrument:
                    inst_type = pos.instrument.instrument_type
                    if getattr(pos.instrument, "sub_type", None):
                        inst_details["sub_type"] = pos.instrument.sub_type
                    od = getattr(pos.instrument, "option_details", None)
                    if od:
                        inst_details["underlying"] = od.underlying
                        inst_details["option_type"] = od.option_type
                        inst_details["strike"] = od.strike
                        inst_details["expiry"] = f"{od.expiry_year}-{od.expiry_month:02d}-{od.expiry_day:02d}"
                        inst_details["expiry_year"] = od.expiry_year
                        inst_details["expiry_month"] = od.expiry_month
                        inst_details["expiry_day"] = od.expiry_day
                holding_rows.append({
                    "profile_id": profile_id,
                    "upload_id": upload_id,
                    "snapshot_date": max_date.isoformat(),
                    "account_id": getattr(pos, "account", None),
                    "ticker": pos.symbol,
                    "instrument_type": inst_type,
                    "quantity": float(pos.quantity),
                    "cost_basis": float(pos.cost_basis) if pos.cost_basis else None,
                    "total_dividends": float(pos.dividends) if pos.dividends else None,
                    "pre_existing": getattr(pos, "pre_existing", False),
                    "description": getattr(pos, "description", None),
                    "instrument_details": inst_details if inst_details else None,
                })
        logger.info("[PROCESS] Built %d holding rows from %d positions", len(holding_rows), len(snapshot.positions))
        if holding_rows:
            try:
                client.table("holdings").insert(holding_rows).execute()
            except Exception as hold_err:
                # 'description' column may not exist yet (migration pending).
                # Strip ONLY description — instrument_details already exists
                # in the schema and should be preserved.
                logger.warning(
                    "[PROCESS] Holdings insert failed (%s), retrying without description column",
                    hold_err,
                )
                for row in holding_rows:
                    row.pop("description", None)
                try:
                    client.table("holdings").insert(holding_rows).execute()
                except Exception as retry_err:
                    # Second failure: also strip instrument_details as last resort
                    logger.warning(
                        "[PROCESS] Holdings retry failed (%s), retrying without instrument_details",
                        retry_err,
                    )
                    for row in holding_rows:
                        row.pop("instrument_details", None)
                    client.table("holdings").insert(holding_rows).execute()
            data_types_written.append("holdings")
            logger.info("[PROCESS] Wrote %d holding rows", len(holding_rows))

        _update_upload(client, upload_id, {
            "status": "processing",
            "data_types_extracted": data_types_written,
        })

        # ── Step 6: Run analysis pipelines ───────────────────────────────
        analyses_run: list[str] = []
        holdings_features: dict[str, Any] | None = None

        # -- Portfolio analysis (if we have holdings) --
        if "holdings" in data_types_written:
            try:
                status_p = "completed"
                try:
                    result = analyze_portfolio(snapshot, transactions)
                    portfolio_analysis = result["analysis"]
                    metrics = result["metrics"]
                except Exception:
                    logger.exception("[PROCESS] Claude portfolio narrative failed; partial results")
                    status_p = "partial"
                    metrics = compute_metrics(snapshot, transactions)
                    portfolio_analysis = None

                # Serialize account summaries
                acct_summaries = {}
                for name, acct in snapshot.accounts.items():
                    acct_summaries[name] = {
                        "account_type": acct.account_type,
                        "total_bought": acct.total_bought,
                        "total_sold": acct.total_sold,
                        "total_dividends": acct.total_dividends,
                        "total_interest": acct.total_interest,
                        "total_fees": acct.total_fees,
                        "total_transfers_in": acct.total_transfers_in,
                        "total_transfers_out": acct.total_transfers_out,
                        "transaction_count": acct.transaction_count,
                        "unique_symbols": acct.unique_symbols,
                    }

                client.table("analysis_results").insert({
                    "profile_id": profile_id,
                    "analysis_type": "portfolio",
                    "features": metrics.get("portfolio_features"),
                    "narrative": portfolio_analysis,
                    "account_summaries": acct_summaries,
                    "summary_stats": {
                        **(metrics.get("asset_allocation") or {}),
                        "portfolio_completeness": metrics.get("portfolio_completeness"),
                    },
                    "status": status_p,
                    "model_used": "claude-sonnet-4-20250514",
                }).execute()

                analyses_run.append("portfolio")
                logger.info("[PROCESS] Portfolio analysis stored (%s)", status_p)
            except Exception:
                logger.exception("[PROCESS] Portfolio analysis pipeline failed")

        # -- Holdings behavioral analysis (69 h_ features) --
        # Runs BEFORE classify_v2 so holdings features can inform dimensions.
        if "holdings" in data_types_written:
            try:
                from features.holdings_extractor import HoldingsExtractor

                market_data_svc = None
                try:
                    from services.market_data import MarketDataService
                    market_data_svc = MarketDataService(supabase_client=client)
                except Exception:
                    logger.debug("[HOLDINGS] MarketDataService unavailable for holdings")

                hx = HoldingsExtractor(supabase_client=client, market_data=market_data_svc)
                holdings_features = hx.extract(profile_id)

                if holdings_features:
                    client.table("analysis_results").insert({
                        "profile_id": profile_id,
                        "analysis_type": "holdings_behavioral",
                        "features": holdings_features,
                        "summary_stats": {
                            "h_total_value": holdings_features.get("h_total_value"),
                            "h_account_count": holdings_features.get("h_account_count"),
                            "h_instrument_type_count": holdings_features.get("h_instrument_type_count"),
                            "h_overall_sophistication": holdings_features.get("h_overall_sophistication"),
                        },
                        "status": "completed",
                    }).execute()
                    analyses_run.append("holdings_behavioral")
                    logger.info(
                        "[HOLDINGS] Stored %d features for %s (h_total_value=%s)",
                        len(holdings_features), profile_id,
                        holdings_features.get("h_total_value"),
                    )
                else:
                    logger.info("[HOLDINGS] No holdings features returned for %s", profile_id)
            except Exception:
                logger.warning("[PROCESS] Holdings behavioral analysis failed (non-fatal)", exc_info=True)

        # -- Behavioral analysis (only on equity/ETF trades) --
        if "trades" in data_types_written:
            try:
                import pandas as pd

                # Filter to equity/ETF trades for behavioral analysis
                equity_trades = [
                    t for t in transactions
                    if t.action in ("buy", "sell")
                    and not _is_complex_instrument(t)
                ]
                logger.info("[BEHAVIORAL] %d equity/ETF trades out of %d total transactions", len(equity_trades), len(transactions))

                if len(equity_trades) >= 5:
                    # Build DataFrame in canonical format from parsed transactions
                    trades_df = pd.DataFrame([
                        {
                            "ticker": t.symbol.upper().strip(),
                            "action": t.action.upper(),  # "BUY" / "SELL"
                            "quantity": abs(t.quantity) if t.quantity else 0.0,
                            "price": abs(t.price) if t.price else 0.0,
                            "date": t.date,
                            "fees": abs(t.fees) if t.fees else 0.0,
                        }
                        for t in equity_trades
                    ])
                    trades_df["date"] = pd.to_datetime(trades_df["date"])
                    trades_df = trades_df.dropna(subset=["date"])
                    trades_df = trades_df[trades_df["quantity"] > 0]
                    trades_df = trades_df.sort_values("date").reset_index(drop=True)
                    logger.info("[BEHAVIORAL] Built DataFrame: %d rows, columns=%s", len(trades_df), list(trades_df.columns))

                    # Run 212-feature engine
                    new_features = _run_new_features(trades_df=trades_df)
                    logger.info("[BEHAVIORAL] Feature extraction returned: %s", "features" if new_features else "None")

                    if new_features:
                        # Run v2 classification (with holdings features if available)
                        classification_v2 = None
                        try:
                            from classifier_v2 import classify_v2
                            classification_v2 = classify_v2(
                                new_features,
                                v1_classification=None,
                                holdings_features=holdings_features,
                            )
                            logger.info("[BEHAVIORAL] V2 classification completed")
                        except Exception:
                            logger.warning("[BEHAVIORAL] V2 classification failed (non-fatal)", exc_info=True)

                        # Generate narrative (uses 212 features + dimensions directly)
                        narrative = None
                        try:
                            from narrative.generator import generate_narrative

                            dims = classification_v2.get("dimensions", {}) if classification_v2 else {}
                            narrative = generate_narrative(
                                features=new_features,
                                dimensions=dims,
                                classification_v2=classification_v2,
                                holdings_features=holdings_features,
                            )
                            # Embed classification_v2 in narrative for frontend consumption
                            if narrative and isinstance(narrative, dict) and classification_v2:
                                narrative["classification_v2"] = {
                                    "primary_archetype": classification_v2.get("primary_archetype"),
                                    "archetype_confidence": classification_v2.get("archetype_confidence"),
                                    "behavioral_summary": classification_v2.get("behavioral_summary"),
                                    "confidence_tier": narrative.get("confidence_metadata", {}).get("tier_label"),
                                    "dimensions": classification_v2.get("dimensions"),
                                    "v1_comparison": classification_v2.get("v1_comparison", {}),
                                }
                            logger.info("[BEHAVIORAL] Narrative generated: %d sections", len(narrative) if isinstance(narrative, dict) else 0)
                        except Exception:
                            logger.exception("[BEHAVIORAL] Narrative generation failed (non-fatal)")

                        # Compute summary stats
                        summary_stats = {
                            "win_rate": new_features.get("portfolio_win_rate"),
                            "profit_factor": new_features.get("portfolio_profit_factor"),
                            "avg_hold_days": new_features.get("holding_mean_days"),
                            "total_trades": new_features.get("portfolio_total_round_trips"),
                        }

                        client.table("analysis_results").insert({
                            "profile_id": profile_id,
                            "analysis_type": "behavioral",
                            "features": new_features,
                            "dimensions": classification_v2.get("dimensions") if classification_v2 else None,
                            "narrative": narrative,
                            "summary_stats": summary_stats,
                            "status": "completed" if narrative else "partial",
                            "model_used": "claude-sonnet-4-20250514",
                        }).execute()

                        analyses_run.append("behavioral")
                        logger.info("[BEHAVIORAL] Analysis stored successfully")
                    else:
                        logger.warning("[BEHAVIORAL] 212-feature extraction returned no results for %d trades", len(trades_df))
                else:
                    logger.info("[BEHAVIORAL] Only %d equity/ETF trades, need >= 5, skipping", len(equity_trades))
            except Exception:
                logger.exception("[BEHAVIORAL] Pipeline failed")

        # -- Portfolio completeness (from orchestrator) --
        if completeness_report and completeness_report.get("signals"):
            try:
                client.table("analysis_results").insert({
                    "profile_id": profile_id,
                    "analysis_type": "completeness",
                    "features": {
                        "invisible_holdings": completeness_report.get("invisible_holdings"),
                        "reconstructed_value": completeness_report.get("reconstructed_value"),
                    },
                    "summary_stats": {
                        "completeness_confidence": completeness_report.get("completeness_confidence"),
                        "invisible_count": completeness_report.get("invisible_holdings", {}).get("count", 0),
                        "prompt_for_more_data": completeness_report.get("prompt_for_more_data", False),
                    },
                    "narrative": {
                        "signals": completeness_report.get("signals"),
                        "user_message": completeness_report.get("user_message"),
                    },
                    "status": "completed",
                }).execute()
                analyses_run.append("completeness")
                logger.info(
                    "[COMPLETENESS] Stored: %s, %d signals, prompt=%s",
                    completeness_report.get("completeness_confidence"),
                    len(completeness_report.get("signals", [])),
                    completeness_report.get("prompt_for_more_data"),
                )
            except Exception:
                logger.warning("[PROCESS] Completeness storage failed (non-fatal)", exc_info=True)

        # ── Step 7: Update profile completeness ──────────────────────────
        completeness = "foundation"
        if "behavioral" in analyses_run and "portfolio" in analyses_run:
            completeness = "complete"
        elif "portfolio" in analyses_run:
            completeness = "complete"

        try:
            client.table("profiles_new").update({
                "profile_completeness": completeness,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("profile_id", profile_id).execute()
        except Exception:
            logger.debug("[PROCESS] Profile completeness update failed (non-fatal)")

        # ── Step 8: Mark upload completed ────────────────────────────────
        _update_upload(client, upload_id, {
            "status": "completed",
            "processing_completed_at": datetime.now(timezone.utc).isoformat(),
        })

        logger.info(
            "[PROCESS] Complete: upload=%s profile=%s data=%s analyses=%s",
            upload_id, profile_id, data_types_written, analyses_run,
        )

        return JSONResponse({
            "success": True,
            "upload_id": upload_id,
            "profile_id": profile_id,
            "data_types_extracted": data_types_written,
            "analyses_run": analyses_run,
            "status": "completed",
        })

    except Exception as e:
        logger.exception("[PROCESS] Pipeline failed")
        try:
            _update_upload(client, upload_id, {
                "status": "error",
                "error_message": str(e)[:500],
            })
        except Exception:
            logger.exception("[PROCESS] Failed to update upload status to 'error'")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


def _is_complex_instrument(t: Any) -> bool:
    """Check if a transaction is for a complex instrument (not equity/ETF)."""
    desc = (t.description or "").lower()
    symbol = (t.symbol or "").upper()
    # Options typically have dates/strikes in description or symbol
    if any(kw in desc for kw in ("call", "put", "option", "strike", "expir")):
        return True
    # Bonds / structured products
    if any(kw in desc for kw in ("bond", "note", "coupon", "muni", "structured", "cdsc")):
        return True
    # If symbol contains a space or is very long, likely an option
    if " " in symbol or len(symbol) > 6:
        return True
    return False


@app.get("/status/{upload_id}")
def upload_status(upload_id: str) -> JSONResponse:
    """Check processing status of an upload."""
    client = _get_supabase()
    if not client:
        return JSONResponse({"error": "Supabase not configured"}, status_code=503)

    try:
        resp = (
            client.table("uploads")
            .select("id, status, data_types_extracted, error_message, processing_started_at, processing_completed_at")
            .eq("id", upload_id)
            .single()
            .execute()
        )
        if not resp.data:
            return JSONResponse({"error": "Upload not found"}, status_code=404)
        return JSONResponse(resp.data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


class ReAnalyzeRequest(BaseModel):
    profile_id: str
    include_holdings: bool = False


@app.post("/re-analyze")
async def re_analyze(req: ReAnalyzeRequest) -> JSONResponse:
    """Re-run analysis pipeline on already-stored data.

    Reads trades (and optionally holdings) from Supabase, then reruns:
      1. 212-feature extraction
      2. classifier_v2 scoring
      3. Narrative generation
      4. Overwrites existing analysis_results

    Does NOT re-parse CSV or re-run the orchestrator/position-tracker.
    """
    import time

    t0 = time.monotonic()

    client = _get_supabase()
    if not client:
        return JSONResponse({"error": "Supabase not configured"}, status_code=503)

    profile_id = req.profile_id

    # ── Step 1: Verify profile exists ─────────────────────────────────
    try:
        profile_resp = (
            client.table("profiles_new")
            .select("profile_id, profile_completeness")
            .eq("profile_id", profile_id)
            .single()
            .execute()
        )
        if not profile_resp.data:
            return JSONResponse(
                {"error": f"Profile not found: {profile_id}"}, status_code=404,
            )
    except Exception as e:
        return JSONResponse(
            {"error": f"Profile not found: {profile_id} ({e})"}, status_code=404,
        )

    # ── Step 2: Read stored trades ────────────────────────────────────
    try:
        trades_resp = (
            client.table("trades_new")
            .select("*")
            .eq("profile_id", profile_id)
            .order("date")
            .execute()
        )
        trade_rows = trades_resp.data or []
    except Exception as e:
        return JSONResponse(
            {"error": f"Failed to read trades: {e}"}, status_code=500,
        )

    if not trade_rows:
        return JSONResponse(
            {"error": f"No trades found for profile {profile_id}"}, status_code=400,
        )

    logger.info("[RE-ANALYZE] %s: read %d trades from Supabase", profile_id, len(trade_rows))

    # ── Step 3: Convert to DataFrame ──────────────────────────────────
    try:
        import pandas as pd

        # Filter to equity/ETF trades (exclude options, bonds, etc.)
        equity_rows = [
            r for r in trade_rows
            if r.get("instrument_type") in ("equity", "etf", None)
            and not _is_stored_trade_complex(r)
        ]

        if len(equity_rows) < 5:
            return JSONResponse(
                {
                    "error": f"Only {len(equity_rows)} equity/ETF trades for "
                    f"{profile_id} — need at least 5 for analysis",
                },
                status_code=400,
            )

        trades_df = pd.DataFrame([
            {
                "ticker": (r.get("ticker") or "").upper().strip(),
                "action": (r.get("side") or "buy").upper(),
                "quantity": abs(float(r.get("quantity", 0) or 0)),
                "price": abs(float(r.get("price", 0) or 0)),
                "date": r.get("date"),
                "fees": abs(float(r.get("fees", 0) or 0)),
            }
            for r in equity_rows
        ])
        trades_df["date"] = pd.to_datetime(trades_df["date"])
        trades_df = trades_df.dropna(subset=["date"])
        trades_df = trades_df[trades_df["quantity"] > 0]
        trades_df = trades_df.sort_values("date").reset_index(drop=True)

        logger.info(
            "[RE-ANALYZE] %s: built DataFrame with %d rows",
            profile_id, len(trades_df),
        )
    except Exception as e:
        logger.exception("[RE-ANALYZE] DataFrame construction failed")
        return JSONResponse(
            {"error": f"Failed to build DataFrame: {e}"}, status_code=500,
        )

    # ── Step 4: Run 212-feature extraction ────────────────────────────
    new_features = _run_new_features(trades_df=trades_df)
    if not new_features:
        return JSONResponse(
            {"error": "Feature extraction returned no results"}, status_code=500,
        )

    # ── Step 4b: Load existing holdings features (if available) ──────
    existing_holdings_features: dict[str, Any] | None = None
    if req.include_holdings:
        try:
            h_resp = (
                client.table("analysis_results")
                .select("features")
                .eq("profile_id", profile_id)
                .eq("analysis_type", "holdings_behavioral")
                .limit(1)
                .execute()
            )
            if h_resp.data:
                existing_holdings_features = h_resp.data[0].get("features")
                logger.info("[RE-ANALYZE] Loaded existing holdings features for merge")
        except Exception:
            logger.debug("[RE-ANALYZE] No existing holdings features", exc_info=True)

    # ── Step 5: Run classifier_v2 ─────────────────────────────────────
    classification_v2 = None
    try:
        from classifier_v2 import classify_v2
        classification_v2 = classify_v2(
            new_features,
            v1_classification=None,
            holdings_features=existing_holdings_features,
        )
    except Exception:
        logger.warning("[RE-ANALYZE] V2 classification failed (non-fatal)", exc_info=True)

    # ── Step 6: Generate narrative ────────────────────────────────────
    narrative = None
    try:
        from narrative.generator import generate_narrative

        dims = classification_v2.get("dimensions", {}) if classification_v2 else {}
        narrative = generate_narrative(
            features=new_features,
            dimensions=dims,
            classification_v2=classification_v2,
            holdings_features=existing_holdings_features,
        )
        if narrative and isinstance(narrative, dict) and classification_v2:
            narrative["classification_v2"] = {
                "primary_archetype": classification_v2.get("primary_archetype"),
                "archetype_confidence": classification_v2.get("archetype_confidence"),
                "behavioral_summary": classification_v2.get("behavioral_summary"),
                "confidence_tier": narrative.get("confidence_metadata", {}).get("tier_label"),
                "dimensions": classification_v2.get("dimensions"),
                "v1_comparison": classification_v2.get("v1_comparison", {}),
            }
    except Exception:
        logger.exception("[RE-ANALYZE] Narrative generation failed (non-fatal)")

    # ── Step 7: Overwrite analysis_results ─────────────────────────────
    analyses_run: list[str] = []

    summary_stats = {
        "win_rate": new_features.get("portfolio_win_rate"),
        "profit_factor": new_features.get("portfolio_profit_factor"),
        "avg_hold_days": new_features.get("holding_mean_days"),
        "total_trades": new_features.get("portfolio_total_round_trips"),
    }

    try:
        # Delete existing behavioral analysis for this profile
        client.table("analysis_results").delete().eq(
            "profile_id", profile_id,
        ).eq("analysis_type", "behavioral").execute()

        client.table("analysis_results").insert({
            "profile_id": profile_id,
            "analysis_type": "behavioral",
            "features": new_features,
            "dimensions": classification_v2.get("dimensions") if classification_v2 else None,
            "narrative": narrative,
            "summary_stats": summary_stats,
            "status": "completed" if narrative else "partial",
            "model_used": "claude-sonnet-4-20250514",
        }).execute()

        analyses_run.append("behavioral")
    except Exception as e:
        logger.exception("[RE-ANALYZE] Failed to store behavioral analysis")
        return JSONResponse(
            {"error": f"Failed to store analysis: {e}"}, status_code=500,
        )

    # ── Step 7b: Re-run holdings behavioral analysis if requested ────
    holdings_features: dict[str, Any] | None = None
    if req.include_holdings:
        try:
            from features.holdings_extractor import HoldingsExtractor

            market_data_svc = None
            try:
                from services.market_data import MarketDataService
                market_data_svc = MarketDataService(supabase_client=client)
            except Exception:
                logger.debug("[RE-ANALYZE] MarketDataService unavailable for holdings")

            hx = HoldingsExtractor(supabase_client=client, market_data=market_data_svc)
            holdings_features = hx.extract(profile_id)

            if holdings_features:
                # Delete + reinsert holdings_behavioral analysis
                client.table("analysis_results").delete().eq(
                    "profile_id", profile_id,
                ).eq("analysis_type", "holdings_behavioral").execute()

                client.table("analysis_results").insert({
                    "profile_id": profile_id,
                    "analysis_type": "holdings_behavioral",
                    "features": holdings_features,
                    "summary_stats": {
                        "h_total_value": holdings_features.get("h_total_value"),
                        "h_account_count": holdings_features.get("h_account_count"),
                        "h_instrument_type_count": holdings_features.get("h_instrument_type_count"),
                        "h_overall_sophistication": holdings_features.get("h_overall_sophistication"),
                    },
                    "status": "completed",
                }).execute()

                analyses_run.append("holdings_behavioral")
                logger.info(
                    "[RE-ANALYZE] %s: holdings behavioral analysis stored (%d features)",
                    profile_id, len(holdings_features),
                )
            else:
                logger.info("[RE-ANALYZE] %s: no holdings data, skipping", profile_id)
        except Exception:
            logger.warning("[RE-ANALYZE] Holdings behavioral analysis failed (non-fatal)", exc_info=True)

    # ── Step 8: Update profile completeness ───────────────────────────
    try:
        completeness = "foundation"
        if "behavioral" in analyses_run and "portfolio" in analyses_run:
            completeness = "complete"
        elif "behavioral" in analyses_run:
            completeness = "foundation"

        # Check if portfolio analysis already exists (from prior upload)
        if "portfolio" not in analyses_run:
            existing_resp = (
                client.table("analysis_results")
                .select("analysis_type")
                .eq("profile_id", profile_id)
                .eq("analysis_type", "portfolio")
                .execute()
            )
            if existing_resp.data:
                completeness = "complete"

        client.table("profiles_new").update({
            "profile_completeness": completeness,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("profile_id", profile_id).execute()
    except Exception:
        logger.debug("[RE-ANALYZE] Profile completeness update failed (non-fatal)")

    elapsed = time.monotonic() - t0

    logger.info(
        "[RE-ANALYZE] %s: %d features extracted, %d dimensions scored, "
        "narrative %s in %.1fs",
        profile_id,
        len(new_features),
        len((classification_v2 or {}).get("dimensions", {})),
        "generated" if narrative else "skipped",
        elapsed,
    )

    return JSONResponse({
        "status": "success",
        "profile_id": profile_id,
        "analyses_run": analyses_run,
        "features_extracted": len(new_features),
        "dimensions_scored": len((classification_v2 or {}).get("dimensions", {})),
        "archetype": (classification_v2 or {}).get("primary_archetype"),
        "elapsed_seconds": round(elapsed, 2),
    })


def _is_stored_trade_complex(row: dict) -> bool:
    """Check if a stored trade row is for a complex instrument."""
    inst_type = (row.get("instrument_type") or "").lower()
    if inst_type in ("options", "muni_bond", "corp_bond", "structured", "money_market"):
        return True
    details = row.get("instrument_details") or {}
    if details.get("sub_type") in ("call", "put"):
        return True
    ticker = (row.get("ticker") or "").upper()
    if " " in ticker or len(ticker) > 6:
        return True
    return False


@app.get("/features/schema")
def features_schema() -> JSONResponse:
    """Return the full list of 212 features."""
    from features.schema import get_schema, get_schema_summary

    summary = get_schema_summary()
    return JSONResponse({
        "features": get_schema(),
        "summary": summary,
    })
