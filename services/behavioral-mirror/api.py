"""FastAPI service for the Behavioral Mirror."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Behavioral Mirror",
    description="Trading behavior analysis service for Yabo",
    version="0.3.0",
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
_DATA_READY_FLAG = DATA_DIR / ".pipeline_complete"


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "version": "0.3.0", "data_ready": _DATA_READY_FLAG.exists()}


@app.get("/supported_formats")
def supported_formats() -> JSONResponse:
    """List all supported CSV formats."""
    from extractor.csv_parsers import SUPPORTED_FORMATS
    return JSONResponse({"formats": SUPPORTED_FORMATS})


@app.post("/extract")
async def extract(
    file: UploadFile = File(...),
    context: str | None = Form(None),
) -> JSONResponse:
    """Accept trade CSV upload + optional context JSON, return behavioral profile.

    Uses normalize_csv for multi-format CSV parsing and dynamic ticker resolution.
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
        # Step 1: Extract features (uses normalize_csv internally)
        profile = extract_features(tmp_path, context=ctx)

        # Step 2: Classify
        if not is_loaded():
            load_model()
        classification = classify(profile)

        # Step 3: Generate narrative (confidence-aware)
        narrative = generate_narrative(profile, classification)

        return JSONResponse({
            "extraction": profile,
            "classification": classification,
            "narrative": narrative,
            "confidence_metadata": profile.get("confidence_metadata"),
        })
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
