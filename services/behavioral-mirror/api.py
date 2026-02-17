"""FastAPI service for the Behavioral Mirror."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Behavioral Mirror",
    description="Trading behavior analysis service for Yabo",
    version="0.1.0",
)

DATA_DIR = Path(__file__).resolve().parent / "data"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}


@app.post("/extract")
async def extract(
    file: UploadFile = File(...),
    context: str | None = Form(None),
) -> JSONResponse:
    """Accept trade CSV upload + optional context JSON, return behavioral profile."""
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


@app.get("/traders")
def list_traders() -> list[str]:
    """List all synthetic trader IDs."""
    trades_dir = DATA_DIR / "trades"
    if not trades_dir.exists():
        return []
    return sorted(p.stem for p in trades_dir.glob("*.csv"))


@app.get("/traders/{trader_id}/profile")
def get_profile(trader_id: str) -> JSONResponse:
    """Get extracted profile for a synthetic trader."""
    path = DATA_DIR / "extracted" / f"{trader_id}.json"
    if not path.exists():
        return JSONResponse({"error": "Profile not found"}, status_code=404)
    with open(path) as f:
        return JSONResponse(json.load(f))


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
    """Run validation and return accuracy metrics."""
    from validate import run_validation
    report = run_validation()
    return JSONResponse(report)
