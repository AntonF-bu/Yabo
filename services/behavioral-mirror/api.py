"""FastAPI service for the Behavioral Mirror."""

from __future__ import annotations

import json
import logging
import tempfile
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, Query, UploadFile
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Startup env-var check (key names only, not values) ───────────────────────
import os as _os
logger.info(
    "[STARTUP] Env check: SUPABASE_URL=%s, SUPABASE_SERVICE_KEY=%s, ANTHROPIC_API_KEY=%s",
    "set" if _os.environ.get("SUPABASE_URL") else "missing",
    "set" if _os.environ.get("SUPABASE_SERVICE_KEY") else "missing",
    "set" if _os.environ.get("ANTHROPIC_API_KEY") else "missing",
)

app = FastAPI(
    title="Behavioral Mirror",
    description="Trading behavior analysis service for Yabo",
    version="0.5.0",
)

# Background retrain state
_retrain_state: dict[str, Any] = {
    "status": "idle",
    "started_at": None,
    "completed_at": None,
    "duration_seconds": None,
    "results": None,
    "error": None,
}

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
_DATA_READY_FLAG = DATA_DIR / ".pipeline_complete"

# Startup import check — surface feature engine load failures immediately
_FEATURES_AVAILABLE = False
try:
    from features.coordinator import extract_all_features, get_features_grouped  # noqa: F401
    _FEATURES_AVAILABLE = True
    logger.info("[STARTUP] 212-feature engine loaded successfully")
except Exception as _feat_err:
    logger.error("[STARTUP] 212-feature engine FAILED to load: %s", _feat_err, exc_info=True)


@app.get("/health")
def health() -> dict[str, Any]:
    from storage.supabase_client import is_configured as supa_ok
    return {
        "status": "ok",
        "version": "0.5.0",
        "data_ready": _DATA_READY_FLAG.exists(),
        "supabase_connected": supa_ok(),
    }


@app.get("/supported_formats")
def supported_formats() -> JSONResponse:
    """List all supported CSV formats (seed + learned)."""
    from ingestion.universal_parser import UniversalParser
    parser = UniversalParser()
    configs = parser.list_configs()
    return JSONResponse({
        "formats": configs,
        "total": len(configs),
        "self_learning": True,
    })


@app.post("/extract")
async def extract(
    file: UploadFile = File(...),
    context: str | None = Form(None),
) -> JSONResponse:
    """Accept trade CSV upload + optional context JSON, return behavioral profile.

    Uses the UniversalParser for self-learning multi-format CSV parsing.
    Falls back to legacy parser if universal parser fails.
    """
    from extractor.pipeline import extract_features

    ctx: dict[str, Any] = {}
    if context:
        try:
            ctx = json.loads(context)
        except json.JSONDecodeError:
            return JSONResponse({"error": "Invalid context JSON"}, status_code=400)

    # Write uploaded CSV to temp file
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        profile = extract_features(tmp_path, context=ctx)

        # Run new 212-feature extraction alongside old
        new_features = _run_new_features(tmp_path)
        if new_features:
            from features.coordinator import get_features_grouped
            profile["features"] = get_features_grouped(new_features)

        return JSONResponse(profile)
    except Exception as e:
        logger.exception("Extraction failed")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    context: str | None = Form(None),
) -> JSONResponse:
    """Full pipeline: CSV upload -> extraction + classification + narrative.

    Uses normalize_csv for multi-format CSV parsing. Includes confidence_metadata
    in the response. For insufficient data (<15 trades), skips Claude API call.

    Works even before the startup pipeline completes. Market data cache is
    optional (extraction works without it, just fewer indicator-based features).
    If ANTHROPIC_API_KEY is not set, returns extraction + classification with
    a placeholder narrative.
    """
    from extractor.pipeline import extract_features
    from classifier.cluster import classify, is_loaded, load_model
    from narrative.generator import generate_narrative

    ctx: dict[str, Any] = {}
    if context:
        try:
            ctx = json.loads(context)
        except json.JSONDecodeError:
            return JSONResponse({"error": "Invalid context JSON"}, status_code=400)

    # Write uploaded CSV to temp file
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Step 0: Parse CSV once — share the DataFrame with both extractors
        trades_df = _parse_csv_once(tmp_path)

        # Step 1: Extract features (old extractor, receives pre-parsed df)
        profile = extract_features(tmp_path, context=ctx, pre_parsed_df=trades_df)

        # Step 1b: Run new 212-feature extraction on SAME parsed DataFrame
        new_features = _run_new_features(trades_df=trades_df)

        # Step 2: Classify (v1 — old GMM/heuristic)
        if not is_loaded():
            load_model()
        classification = classify(profile)

        # Step 2b: Classify (v2 — 8-dimension behavioral profile)
        classification_v2 = None
        if new_features:
            try:
                from classifier_v2 import classify_v2
                classification_v2 = classify_v2(new_features, v1_classification=classification)
            except Exception:
                logger.exception("[ANALYZE] V2 classification failed (non-fatal)")

        # Step 3: Generate narrative (confidence-aware, v2-enriched)
        narrative = generate_narrative(
            profile, classification, classification_v2=classification_v2,
        )

        # Step 4: Persist profile for ML feedback loop
        profile_id = None
        try:
            from profile_store import save_real_profile, should_auto_retrain
            profile_id = save_real_profile(profile, classification)

            # Auto-retrain check (every 25 real profiles)
            if should_auto_retrain():
                logger.info("Auto-retrain triggered: %s real profiles", profile_id)
                _trigger_retrain_background()
        except Exception:
            logger.exception("Profile persistence failed (non-fatal)")

        result: dict[str, Any] = {
            "extraction": profile,
            "classification": classification,
            "narrative": narrative,
            "confidence_metadata": profile.get("confidence_metadata"),
            "profile_id": profile_id,
        }
        if classification_v2:
            result["classification_v2"] = classification_v2
        if new_features:
            from features.coordinator import get_features_grouped
            result["features"] = get_features_grouped(new_features)
            logger.info(
                "[ANALYZE] 212-feature extraction: %d computed, %d null",
                new_features.get("_meta_computed_features", 0),
                new_features.get("_meta_null_features", 0),
            )
        else:
            logger.warning("[ANALYZE] New feature extraction returned no results")

        return JSONResponse(result)
    except Exception as e:
        logger.exception("Analysis pipeline failed")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.get("/traders")
def list_traders() -> list[str]:
    """List all synthetic trader IDs."""
    trades_dir = DATA_DIR / "trades"
    if not trades_dir.exists():
        return []
    return sorted(p.stem for p in trades_dir.glob("*.csv"))


@app.get("/traders/narratives/all")
def all_narratives() -> JSONResponse:
    """Return all pre-generated narratives in a single response."""
    narrative_dir = DATA_DIR / "narratives"
    if not narrative_dir.exists():
        return JSONResponse({"count": 0, "traders": {}})

    traders: dict[str, Any] = {}
    for path in sorted(narrative_dir.glob("*.json")):
        with open(path) as f:
            traders[path.stem] = json.load(f)

    return JSONResponse({"count": len(traders), "traders": traders})


@app.get("/traders/{trader_id}/profile")
def get_profile(trader_id: str) -> JSONResponse:
    """Get extracted profile for a synthetic trader."""
    path = DATA_DIR / "extracted" / f"{trader_id}.json"
    if not path.exists():
        return JSONResponse({"error": "Profile not found"}, status_code=404)
    with open(path) as f:
        return JSONResponse(json.load(f))


@app.get("/traders/{trader_id}/classification")
def get_classification(trader_id: str) -> JSONResponse:
    """Get GMM classification for a synthetic trader."""
    from classifier.cluster import classify, is_loaded, load_model

    path = DATA_DIR / "extracted" / f"{trader_id}.json"
    if not path.exists():
        return JSONResponse({"error": "Profile not found"}, status_code=404)

    if not is_loaded():
        load_model()

    with open(path) as f:
        profile = json.load(f)

    result = classify(profile)
    return JSONResponse(result)


@app.get("/traders/{trader_id}/narrative")
def get_narrative(trader_id: str) -> JSONResponse:
    """Get generated narrative for a synthetic trader.

    Checks for pre-generated narrative first. Falls back to on-demand generation.
    """
    # Check for pre-generated
    narrative_path = DATA_DIR / "narratives" / f"{trader_id}.json"
    if narrative_path.exists():
        with open(narrative_path) as f:
            return JSONResponse(json.load(f))

    # Generate on demand
    from classifier.cluster import classify, is_loaded, load_model
    from narrative.generator import generate_narrative

    profile_path = DATA_DIR / "extracted" / f"{trader_id}.json"
    if not profile_path.exists():
        return JSONResponse({"error": "Profile not found"}, status_code=404)

    if not is_loaded():
        load_model()

    with open(profile_path) as f:
        profile = json.load(f)

    classification = classify(profile)
    narrative = generate_narrative(profile, classification)
    return JSONResponse(narrative)


@app.get("/traders/{trader_id}/full_profile")
def get_full_profile(trader_id: str) -> JSONResponse:
    """Get extraction + classification + narrative combined."""
    from classifier.cluster import classify, is_loaded, load_model
    from narrative.generator import generate_narrative

    profile_path = DATA_DIR / "extracted" / f"{trader_id}.json"
    if not profile_path.exists():
        return JSONResponse({"error": "Profile not found"}, status_code=404)

    if not is_loaded():
        load_model()

    with open(profile_path) as f:
        profile = json.load(f)

    classification = classify(profile)

    # Check pre-generated narrative first
    narrative_path = DATA_DIR / "narratives" / f"{trader_id}.json"
    if narrative_path.exists():
        with open(narrative_path) as f:
            narrative = json.load(f)
    else:
        narrative = generate_narrative(profile, classification)

    return JSONResponse({
        "extraction": profile,
        "classification": classification,
        "narrative": narrative,
    })


@app.get("/traders/{trader_id}/ground_truth")
def get_ground_truth(trader_id: str) -> JSONResponse:
    """Get ground truth for validation (dev only)."""
    path = DATA_DIR / "ground_truth" / f"{trader_id}.json"
    if not path.exists():
        return JSONResponse({"error": "Ground truth not found"}, status_code=404)
    with open(path) as f:
        return JSONResponse(json.load(f))


@app.get("/validation/report")
def validation_report() -> JSONResponse:
    """Run validation and return accuracy metrics (heuristic + GMM comparison)."""
    from validate import run_validation

    report = run_validation()

    # Also include GMM validation if model exists
    gmm_report: dict[str, Any] = {}
    try:
        from classifier.train import validate_gmm
        gmm_report = validate_gmm()
    except Exception as e:
        gmm_report = {"error": str(e)}

    return JSONResponse({
        "heuristic": report,
        "gmm": gmm_report,
    })


# ─── Profile persistence endpoints ───────────────────────────────────────────


@app.get("/profiles/stats")
def profiles_stats() -> JSONResponse:
    """Return manifest with profile counts and retrain status."""
    from profile_store import get_manifest
    return JSONResponse(get_manifest())


@app.get("/profiles/real")
def profiles_real_list() -> JSONResponse:
    """List real profile IDs with basic metadata (no full features — privacy)."""
    from profile_store import list_real_profiles
    return JSONResponse(list_real_profiles())


@app.delete("/profiles/real/{profile_id}")
def profiles_real_delete(profile_id: str) -> JSONResponse:
    """Remove a real profile from the training set."""
    from profile_store import delete_real_profile

    if not profile_id.startswith("R"):
        return JSONResponse({"error": "Invalid profile ID"}, status_code=400)

    if delete_real_profile(profile_id):
        return JSONResponse({"deleted": profile_id})
    return JSONResponse({"error": "Profile not found"}, status_code=404)


# ─── Retrain endpoints ───────────────────────────────────────────────────────


def _trigger_retrain_background() -> None:
    """Run retrain in a background thread."""
    import time
    from datetime import datetime, timezone

    def _run() -> None:
        global _retrain_state
        _retrain_state = {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "duration_seconds": None,
            "results": None,
            "error": None,
        }
        t0 = time.time()
        try:
            from classifier.retrain import retrain
            results = retrain()
            elapsed = time.time() - t0
            _retrain_state.update({
                "status": "complete",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": round(elapsed, 1),
                "results": results,
            })
        except Exception as e:
            elapsed = time.time() - t0
            logger.exception("Retrain failed")
            _retrain_state.update({
                "status": "failed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": round(elapsed, 1),
                "error": str(e),
            })

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


@app.post("/retrain")
def trigger_retrain(confirm: bool = Query(False)) -> JSONResponse:
    """Trigger a GMM retrain with all profiles (synthetic + real).

    Requires ?confirm=true to prevent accidental triggers.
    Runs in background — use GET /retrain/status to monitor.
    """
    if not confirm:
        return JSONResponse(
            {"error": "Add ?confirm=true to trigger retrain"}, status_code=400,
        )

    if _retrain_state.get("status") == "running":
        return JSONResponse(
            {"error": "Retrain already in progress", "started_at": _retrain_state["started_at"]},
            status_code=409,
        )

    _trigger_retrain_background()
    return JSONResponse({"status": "started", "message": "Retrain running in background"})


@app.get("/retrain/status")
def retrain_status() -> JSONResponse:
    """Return status of the last retrain job."""
    return JSONResponse(_retrain_state)


# ─── Batch import endpoint ────────────────────────────────────────────────────


@app.post("/batch_import")
async def batch_import(
    files: list[UploadFile] = File(...),
    context: str | None = Form(None),
) -> JSONResponse:
    """Import multiple CSVs at once for bulk ingestion.

    Runs feature extraction and saves profiles, but skips narrative generation.
    """
    from extractor.pipeline import extract_features
    from classifier.cluster import classify, is_loaded, load_model
    from profile_store import save_real_profile, get_manifest, should_auto_retrain

    ctx: dict[str, Any] = {}
    if context:
        try:
            ctx = json.loads(context)
        except json.JSONDecodeError:
            return JSONResponse({"error": "Invalid context JSON"}, status_code=400)

    if not is_loaded():
        load_model()

    imported = 0
    failed = 0
    errors: list[dict[str, str]] = []
    profile_ids: list[str] = []

    for upload_file in files:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as tmp:
            content = await upload_file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            profile = extract_features(tmp_path, context=ctx)
            classification = classify(profile)
            pid = save_real_profile(profile, classification)
            profile_ids.append(pid)
            imported += 1
        except Exception as e:
            failed += 1
            errors.append({
                "filename": upload_file.filename or "unknown",
                "error": str(e),
            })
            logger.warning("Batch import failed for %s: %s", upload_file.filename, e)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    # Check auto-retrain threshold
    retrain_triggered = False
    if imported > 0 and should_auto_retrain():
        _trigger_retrain_background()
        retrain_triggered = True

    manifest = get_manifest()

    return JSONResponse({
        "imported": imported,
        "failed": failed,
        "errors": errors,
        "profiles_created": profile_ids,
        "total_profiles_now": manifest["total_profiles"],
        "retrain_triggered": retrain_triggered,
    })


# ─── Screenshot extraction endpoints ─────────────────────────────────────────


@app.post("/extract_screenshots")
async def extract_screenshots(files: list[UploadFile] = File(...)) -> JSONResponse:
    """Accept screenshot images, extract trades using Claude Vision.

    Returns structured trade data for review before analysis.
    """
    from extraction.screenshot_extractor import extract_from_multiple_screenshots

    if not files:
        return JSONResponse({"error": "No files provided"}, status_code=400)

    images: list[tuple[bytes, str]] = []
    for f in files:
        content = await f.read()
        media_type = f.content_type or "image/png"
        images.append((content, media_type))

    try:
        result = extract_from_multiple_screenshots(images)

        # Upload screenshots to Supabase storage if configured
        try:
            from storage.supabase_client import upload_screenshot
            for i, (img_bytes, media_type) in enumerate(images):
                upload_screenshot(img_bytes, media_type, i)
        except Exception:
            logger.debug("Screenshot storage not available (non-fatal)")

        return JSONResponse(result)
    except Exception as e:
        logger.exception("Screenshot extraction failed")
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── Parser config management endpoints ───────────────────────────────────────


@app.get("/parser_configs")
def list_parser_configs() -> JSONResponse:
    """List all loaded parser configs (seed + learned)."""
    from ingestion.universal_parser import UniversalParser
    parser = UniversalParser()
    return JSONResponse({
        "configs": parser.list_configs(),
        "total": len(parser.list_configs()),
    })


@app.get("/parser_configs/{config_id}")
def get_parser_config(config_id: str) -> JSONResponse:
    """Get a specific parser config by ID."""
    from ingestion.universal_parser import UniversalParser
    parser = UniversalParser()
    config = parser.get_config(config_id)
    if not config:
        return JSONResponse({"error": "Config not found"}, status_code=404)
    return JSONResponse(config)


@app.post("/parser_configs/seed")
def seed_parser_configs() -> JSONResponse:
    """Seed all built-in parser configs to Supabase."""
    from ingestion.universal_parser import UniversalParser
    parser = UniversalParser()
    count = parser.seed_configs()
    return JSONResponse({"seeded": count})


@app.post("/parse_csv")
async def parse_csv(file: UploadFile = File(...)) -> JSONResponse:
    """Parse a CSV using the UniversalParser and return normalized trades.

    This endpoint ONLY parses — it does not run the behavioral analysis.
    Useful for previewing how a CSV will be interpreted.
    """
    from ingestion.universal_parser import UniversalParser

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        parser = UniversalParser()
        trades_df, format_name, metadata = parser.parse(tmp_path)

        return JSONResponse({
            "format": format_name,
            "trade_count": len(trades_df),
            "sample_trades": trades_df.head(20).to_dict(orient="records"),
            "columns": list(trades_df.columns),
            "metadata": metadata,
        })
    except Exception as e:
        logger.exception("CSV parsing failed")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.post("/import_and_analyze")
async def import_and_analyze(
    trades: str = Form(...),
    context: Optional[str] = Form(None),
    trader_name: Optional[str] = Form(None),
    trader_email: Optional[str] = Form(None),
    brokerage: Optional[str] = Form(None),
    referred_by: Optional[str] = Form(None),
) -> JSONResponse:
    """Accept reviewed trades (from screenshot extraction or manual entry),
    create a trader record, and run the full analysis pipeline.
    """
    from extractor.pipeline import extract_features
    from classifier.cluster import classify, is_loaded, load_model
    from narrative.generator import generate_narrative

    try:
        trades_list = json.loads(trades)
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid trades JSON"}, status_code=400)

    if not trades_list:
        return JSONResponse({"error": "No trades provided"}, status_code=400)

    ctx: dict[str, Any] = {}
    if context:
        try:
            ctx = json.loads(context)
        except json.JSONDecodeError:
            pass

    # Convert trades list to CSV the pipeline expects
    lines = ["date,ticker,side,quantity,price,total"]
    for t in trades_list:
        lines.append(
            f"{t['date']},{t['ticker']},{t['side']},"
            f"{t['quantity']},{t['price']},{t.get('total', 0)}"
        )
    csv_content = "\n".join(lines) + "\n"

    with tempfile.NamedTemporaryFile(
        suffix=".csv", delete=False, mode="w"
    ) as tmp:
        tmp.write(csv_content)
        tmp_path = tmp.name

    try:
        # Step 1: Extract features
        profile = extract_features(tmp_path, context=ctx)

        # Step 2: Classify
        if not is_loaded():
            load_model()
        classification = classify(profile)

        # Step 3: Generate narrative
        narrative = generate_narrative(profile, classification)

        # Step 4: Persist profile
        profile_id = None
        try:
            from profile_store import save_real_profile, should_auto_retrain
            profile_id = save_real_profile(profile, classification)

            if should_auto_retrain():
                _trigger_retrain_background()
        except Exception:
            logger.exception("Profile persistence failed (non-fatal)")

        # Step 5: Save trader record if info provided
        try:
            from storage.supabase_client import save_trader
            if trader_name or trader_email:
                save_trader(
                    name=trader_name,
                    email=trader_email,
                    brokerage=brokerage,
                    referred_by=referred_by or "Daniel Starr",
                    profile_id=profile_id,
                )
        except Exception:
            logger.debug("Trader record save failed (non-fatal)")

        return JSONResponse({
            "extraction": profile,
            "classification": classification,
            "narrative": narrative,
            "confidence_metadata": profile.get("confidence_metadata"),
            "profile_id": profile_id,
            "trader_info": {
                "name": trader_name,
                "brokerage": brokerage,
            },
        })
    except Exception as e:
        logger.exception("Import-and-analyze pipeline failed")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ─── CSV parsing helper ──────────────────────────────────────────────────────


def _parse_csv_once(csv_path: str) -> "pd.DataFrame":
    """Parse a CSV once using UniversalParser with legacy fallback.

    Returns the parsed trades DataFrame. Both the old and new extractors
    share this result so the CSV is only parsed once per request.
    """
    import pandas as pd

    try:
        from ingestion.universal_parser import UniversalParser
        parser = UniversalParser()
        trades_df, fmt, _metadata = parser.parse(csv_path)
        logger.info("[PARSE] UniversalParser: format=%s, %d trades", fmt, len(trades_df))
        return trades_df
    except Exception as e:
        logger.warning("[PARSE] UniversalParser failed, falling back to legacy: %s", e)

    try:
        from extractor.csv_parsers import normalize_csv
        result = normalize_csv(csv_path)
        trades_df = result[0] if isinstance(result, tuple) else result
        logger.info("[PARSE] Legacy parser: %d trades", len(trades_df))
        return trades_df
    except Exception as e2:
        logger.warning("[PARSE] Legacy parser failed, raw read: %s", e2)

    return pd.read_csv(csv_path)


# ─── New 212-feature extraction helper ───────────────────────────────────────


def _run_new_features(
    csv_path: str | None = None,
    trades_df: "pd.DataFrame | None" = None,
) -> dict[str, Any] | None:
    """Run the new 212-feature extraction.

    Accepts a pre-parsed DataFrame (preferred) or csv_path as fallback.
    Returns the sanitized flat feature dict, or None on failure.
    """
    try:
        import numpy as np
        import pandas as pd
        from features.coordinator import extract_all_features

        if trades_df is None and csv_path is not None:
            from extractor.csv_parsers import normalize_csv
            result = normalize_csv(csv_path)
            trades_df = result[0] if isinstance(result, tuple) else result

        if trades_df is None or len(trades_df) == 0:
            logger.warning("[NEW_FEATURES] No trades DataFrame available")
            return None

        logger.info("[NEW_FEATURES] Running on %d trades", len(trades_df))
        features = extract_all_features(trades_df)

        # Sanitize numpy types to native Python for JSON serialization
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


# ─── Portfolio analysis endpoints ─────────────────────────────────────────────


@app.post("/analyze-portfolio")
async def analyze_portfolio_endpoint(
    file: UploadFile = File(...),
    profile_id: str | None = Form(None),
    trader_id: str | None = Form(None),
) -> JSONResponse:
    """Full WFA portfolio analysis pipeline.

    Accepts: multipart form with CSV file + optional profile_id + trader_id.

    Pipeline:
    1. Parse CSV with WFAActivityParser
    2. Classify all instruments
    3. Reconstruct holdings
    4. Run portfolio analysis (local metrics + Claude narrative)
    5. Store in Supabase portfolio_imports table
    6. Optionally update trader.profile_completeness
    """
    import sys
    import uuid
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from backend.parsers.wfa_activity import WFAActivityParser
        from backend.parsers.holdings_reconstructor import reconstruct
        from backend.analyzers.portfolio_analyzer import analyze_portfolio, compute_metrics

        # Step 1-2: Parse CSV
        parser = WFAActivityParser()
        transactions = parser.parse_csv(tmp_path)

        if not transactions:
            return JSONResponse(
                {"error": "No transactions found. Check that this is a WFA activity CSV."},
                status_code=400,
            )

        # Step 3: Reconstruct holdings
        snapshot = reconstruct(transactions)

        # Step 4: Run portfolio analysis (metrics + Claude narrative)
        status = "complete"
        try:
            result = analyze_portfolio(snapshot, transactions)
            portfolio_analysis = result["analysis"]
            metrics = result["metrics"]
        except Exception:
            logger.exception("Claude analysis failed; storing partial results")
            status = "partial"
            metrics = compute_metrics(snapshot, transactions)
            portfolio_analysis = None

        # Serialize transactions for storage
        raw_txns = [
            {
                "date": t.date.isoformat(),
                "account": t.account,
                "account_type": t.account_type,
                "action": t.action,
                "symbol": t.symbol,
                "description": t.description,
                "quantity": t.quantity,
                "price": t.price,
                "amount": t.amount,
                "fees": t.fees,
                "raw_action": t.raw_action,
            }
            for t in transactions
        ]

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

        # Detected accounts info
        accounts_detected = [
            {"name": name, "type": acct.account_type, "transactions": acct.transaction_count}
            for name, acct in snapshot.accounts.items()
        ]

        # Use provided profile_id or generate one
        pid = profile_id or f"P-{uuid.uuid4().hex[:8]}"

        # Step 5: Store in Supabase
        try:
            from storage.supabase_client import _get_client
            client = _get_client()
            if client:
                row = {
                    "profile_id": pid,
                    "source_type": "wfa_activity",
                    "source_file": file.filename,
                    "raw_transactions": raw_txns,
                    "reconstructed_holdings": metrics.get("asset_allocation"),
                    "account_summaries": acct_summaries,
                    "portfolio_analysis": portfolio_analysis,
                    "accounts_detected": accounts_detected,
                    "instrument_breakdown": snapshot.instrument_breakdown,
                    "portfolio_features": metrics.get("portfolio_features"),
                    "status": status,
                }
                if trader_id:
                    row["trader_id"] = trader_id
                client.table("portfolio_imports").insert(row).execute()
                logger.info("Stored portfolio import: %s", pid)

                # Step 6: Update trader completeness if trader_id provided
                if trader_id:
                    try:
                        client.table("traders").update({
                            "profile_completeness": "complete",
                        }).eq("id", trader_id).execute()
                    except Exception:
                        logger.debug("Could not update trader completeness (non-fatal)")
        except Exception:
            logger.debug("Supabase storage failed (non-fatal)")

        return JSONResponse({
            "success": True,
            "profile_id": pid,
            "summary": {
                "accounts": accounts_detected,
                "positions": len(snapshot.positions),
                "instrument_breakdown": snapshot.instrument_breakdown,
                "total_transactions": len(transactions),
            },
            "analysis": portfolio_analysis,
            "metrics": metrics,
            "portfolio_features": metrics.get("portfolio_features"),
        })
    except Exception as e:
        logger.exception("Portfolio analysis pipeline failed")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.get("/portfolio/{profile_id}")
def get_portfolio(profile_id: str) -> JSONResponse:
    """Return the stored portfolio_imports record for a profile_id."""
    try:
        from storage.supabase_client import _get_client
        client = _get_client()
        if not client:
            return JSONResponse(
                {"error": "Supabase not configured"},
                status_code=503,
            )

        resp = (
            client.table("portfolio_imports")
            .select("*")
            .eq("profile_id", profile_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if not resp.data:
            return JSONResponse({"error": "Portfolio not found"}, status_code=404)

        return JSONResponse(resp.data[0])
    except Exception as e:
        logger.exception("Failed to fetch portfolio %s", profile_id)
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── Test endpoint: browser-triggerable local CSV analysis ────────────────────


@app.get("/test/analyze-local")
def test_analyze_local(
    profile_id: str = Query(...),
    file: str = Query(...),
) -> JSONResponse:
    """Run the full portfolio pipeline on a test CSV already on disk.

    GET /test/analyze-local?profile_id=D001&file=WFA_Activity_021826_1652.csv

    Only allows filenames from backend/test-data/ (no path traversal).
    Runs: parse → classify → reconstruct → features → Claude narrative → Supabase store.
    """
    import sys
    import uuid

    # Guard: reject path traversal
    if "/" in file or ".." in file:
        return JSONResponse(
            {"error": "Invalid filename — no path separators or '..' allowed"},
            status_code=400,
        )

    # Resolve the test-data directory relative to this service
    repo_root = Path(__file__).resolve().parent.parent.parent
    test_data_dir = repo_root / "backend" / "test-data"
    csv_path = test_data_dir / file

    if not csv_path.exists():
        return JSONResponse(
            {"error": f"File not found: backend/test-data/{file}"},
            status_code=404,
        )

    sys.path.insert(0, str(repo_root))

    try:
        from backend.parsers.wfa_activity import WFAActivityParser
        from backend.parsers.holdings_reconstructor import reconstruct
        from backend.analyzers.portfolio_analyzer import analyze_portfolio, compute_metrics

        # Step 1-2: Parse CSV
        parser = WFAActivityParser()
        transactions = parser.parse_csv(str(csv_path))

        if not transactions:
            return JSONResponse(
                {"error": "No transactions found in CSV."},
                status_code=400,
            )

        logger.info("[TEST] Parsed %d transactions from %s", len(transactions), file)

        # Step 3: Reconstruct holdings
        snapshot = reconstruct(transactions)

        # Step 4: Run portfolio analysis (metrics + Claude narrative)
        status = "complete"
        try:
            result = analyze_portfolio(snapshot, transactions)
            portfolio_analysis = result["analysis"]
            metrics = result["metrics"]
        except Exception:
            logger.exception("[TEST] Claude analysis failed; storing partial results")
            status = "partial"
            metrics = compute_metrics(snapshot, transactions)
            portfolio_analysis = None

        # Serialize transactions
        raw_txns = [
            {
                "date": t.date.isoformat(),
                "account": t.account,
                "account_type": t.account_type,
                "action": t.action,
                "symbol": t.symbol,
                "description": t.description,
                "quantity": t.quantity,
                "price": t.price,
                "amount": t.amount,
                "fees": t.fees,
                "raw_action": t.raw_action,
            }
            for t in transactions
        ]

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

        # Detected accounts
        accounts_detected = [
            {"name": name, "type": acct.account_type, "transactions": acct.transaction_count}
            for name, acct in snapshot.accounts.items()
        ]

        pid = profile_id or f"P-{uuid.uuid4().hex[:8]}"

        # Step 5: Store in Supabase
        supabase_stored = False
        supabase_error = None
        try:
            from storage.supabase_client import _get_client
            client = _get_client()
            if client:
                row = {
                    "profile_id": pid,
                    "source_type": "wfa_activity_csv",
                    "source_file": file,
                    "raw_transactions": raw_txns,
                    "reconstructed_holdings": metrics.get("asset_allocation"),
                    "account_summaries": acct_summaries,
                    "portfolio_analysis": portfolio_analysis,
                    "accounts_detected": accounts_detected,
                    "instrument_breakdown": snapshot.instrument_breakdown,
                    "portfolio_features": metrics.get("portfolio_features"),
                    "status": status,
                }
                client.table("portfolio_imports").insert(row).execute()
                supabase_stored = True
                logger.info("[TEST] Stored portfolio import: %s", pid)
            else:
                supabase_error = "Supabase client not configured"
        except Exception as e:
            supabase_error = str(e)
            logger.exception("[TEST] Supabase storage failed")

        return JSONResponse({
            "success": True,
            "profile_id": pid,
            "supabase_stored": supabase_stored,
            "supabase_error": supabase_error,
            "status": status,
            "summary": {
                "accounts": accounts_detected,
                "positions": len(snapshot.positions),
                "instrument_breakdown": snapshot.instrument_breakdown,
                "total_transactions": len(transactions),
            },
            "analysis": portfolio_analysis,
            "portfolio_features": metrics.get("portfolio_features"),
        })
    except Exception as e:
        logger.exception("[TEST] Pipeline failed")
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── Feature schema endpoint ─────────────────────────────────────────────────


@app.get("/features/schema")
def features_schema() -> JSONResponse:
    """Return the full list of 212 features with names, descriptions,
    data types, and which dimension they belong to."""
    from features.schema import get_schema, get_schema_summary

    summary = get_schema_summary()
    return JSONResponse({
        "features": get_schema(),
        "summary": summary,
    })
