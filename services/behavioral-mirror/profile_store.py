"""Persistent profile storage for the ML feedback loop.

Saves extracted feature profiles to disk so the GMM can be retrained
on real user data in addition to synthetic profiles.

Storage layout:
    data/profiles/
        synthetic/T001.json … T075.json
        real/R001.json …
        manifest.json
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"
PROFILES_DIR = DATA_DIR / "profiles"
SYNTHETIC_DIR = PROFILES_DIR / "synthetic"
REAL_DIR = PROFILES_DIR / "real"
MANIFEST_PATH = PROFILES_DIR / "manifest.json"

_lock = threading.Lock()


def _ensure_dirs() -> None:
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)
    REAL_DIR.mkdir(parents=True, exist_ok=True)


def _load_manifest() -> dict[str, Any]:
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            return json.load(f)
    return {
        "total_profiles": 0,
        "synthetic": 0,
        "real": 0,
        "last_retrain": None,
        "last_upload": None,
        "next_real_id": 1,
    }


def _save_manifest(manifest: dict[str, Any]) -> None:
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)


def get_manifest() -> dict[str, Any]:
    """Return current manifest (thread-safe)."""
    with _lock:
        return _load_manifest()


def _next_real_id(manifest: dict[str, Any]) -> str:
    """Get next R-prefixed ID and bump counter."""
    num = manifest.get("next_real_id", 1)
    profile_id = f"R{num:03d}"
    manifest["next_real_id"] = num + 1
    return profile_id


def save_real_profile(
    extracted_profile: dict[str, Any],
    classification: dict[str, Any],
) -> str:
    """Persist a real user's extracted features after /analyze.

    Returns the assigned profile ID (e.g. "R001").
    Does NOT store raw CSV data or individual trades.
    """
    _ensure_dirs()

    with _lock:
        manifest = _load_manifest()
        profile_id = _next_real_id(manifest)

        meta = extracted_profile.get("metadata", {})
        conf_meta = extracted_profile.get("confidence_metadata", {})
        hp = extracted_profile.get("holdings_profile", {})
        risk = extracted_profile.get("risk_profile", {})

        doc = {
            "profile_id": profile_id,
            "source": "real",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "csv_format": meta.get("csv_format", "unknown"),
            "trade_count": meta.get("total_trades", 0),
            "unique_tickers": conf_meta.get("unique_tickers", 0),
            "date_range": meta.get("date_range", {}),
            "confidence_tier": conf_meta.get("confidence_tier", "unknown"),
            "features": extracted_profile,
            "classification": {
                arch.replace("_score", ""): score
                for arch, score in extracted_profile.get("traits", {}).items()
                if arch.endswith("_score")
            },
            "holdings_profile": hp,
            "metadata": {
                "portfolio_value_estimated": risk.get("estimated_portfolio_value"),
                "portfolio_value_source": risk.get("portfolio_value_source"),
            },
        }

        out_path = REAL_DIR / f"{profile_id}.json"
        with open(out_path, "w") as f:
            json.dump(doc, f, indent=2, default=str)

        manifest["real"] += 1
        manifest["total_profiles"] = manifest["synthetic"] + manifest["real"]
        manifest["last_upload"] = datetime.now(timezone.utc).isoformat()
        _save_manifest(manifest)

    logger.info("Saved real profile %s (%d trades)", profile_id, doc["trade_count"])
    return profile_id


def save_synthetic_profile(
    trader_id: str,
    extracted_profile: dict[str, Any],
    ground_truth: dict[str, Any] | None = None,
) -> None:
    """Persist a synthetic trader's extracted features in the same format.

    Called during the startup pipeline when synthetic traders are generated.
    """
    _ensure_dirs()

    meta = extracted_profile.get("metadata", {})
    conf_meta = extracted_profile.get("confidence_metadata", {})
    hp = extracted_profile.get("holdings_profile", {})

    doc: dict[str, Any] = {
        "profile_id": trader_id,
        "source": "synthetic",
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "csv_format": meta.get("csv_format", "synthetic"),
        "trade_count": meta.get("total_trades", 0),
        "unique_tickers": conf_meta.get("unique_tickers", 0),
        "date_range": meta.get("date_range", {}),
        "confidence_tier": conf_meta.get("confidence_tier", "unknown"),
        "features": extracted_profile,
        "classification": {
            arch.replace("_score", ""): score
            for arch, score in extracted_profile.get("traits", {}).items()
            if arch.endswith("_score")
        },
        "holdings_profile": hp,
    }

    if ground_truth:
        doc["ground_truth"] = ground_truth.get("archetype_weights", {})

    out_path = SYNTHETIC_DIR / f"{trader_id}.json"
    with open(out_path, "w") as f:
        json.dump(doc, f, indent=2, default=str)


def save_all_synthetic(
    extracted_dir: Path | None = None,
    gt_dir: Path | None = None,
) -> int:
    """Bulk-save all synthetic profiles from data/extracted/ + data/ground_truth/.

    Returns count of profiles saved.
    """
    _ensure_dirs()
    extracted_dir = extracted_dir or (DATA_DIR / "extracted")
    gt_dir = gt_dir or (DATA_DIR / "ground_truth")

    count = 0
    for ext_path in sorted(extracted_dir.glob("*.json")):
        tid = ext_path.stem
        with open(ext_path) as f:
            profile = json.load(f)

        gt = None
        gt_path = gt_dir / f"{tid}.json"
        if gt_path.exists():
            with open(gt_path) as f:
                gt = json.load(f)

        save_synthetic_profile(tid, profile, ground_truth=gt)
        count += 1

    # Update manifest
    with _lock:
        manifest = _load_manifest()
        manifest["synthetic"] = count
        manifest["total_profiles"] = count + manifest.get("real", 0)
        _save_manifest(manifest)

    logger.info("Saved %d synthetic profiles to %s", count, SYNTHETIC_DIR)
    return count


def list_real_profiles() -> list[dict[str, Any]]:
    """Return metadata for all real profiles (no full features — privacy)."""
    if not REAL_DIR.exists():
        return []

    profiles = []
    for p in sorted(REAL_DIR.glob("R*.json")):
        with open(p) as f:
            doc = json.load(f)
        profiles.append({
            "profile_id": doc["profile_id"],
            "uploaded_at": doc.get("uploaded_at"),
            "trade_count": doc.get("trade_count", 0),
            "unique_tickers": doc.get("unique_tickers", 0),
            "date_range": doc.get("date_range", {}),
            "confidence_tier": doc.get("confidence_tier"),
            "csv_format": doc.get("csv_format"),
            "top_archetype": _top_archetype(doc.get("classification", {})),
        })
    return profiles


def delete_real_profile(profile_id: str) -> bool:
    """Remove a real profile from storage. Returns True if found and deleted."""
    path = REAL_DIR / f"{profile_id}.json"
    if not path.exists():
        return False

    path.unlink()

    with _lock:
        manifest = _load_manifest()
        manifest["real"] = max(0, manifest.get("real", 1) - 1)
        manifest["total_profiles"] = manifest["synthetic"] + manifest["real"]
        _save_manifest(manifest)

    logger.info("Deleted real profile %s", profile_id)
    return True


def load_all_profiles() -> list[dict[str, Any]]:
    """Load all profile documents (synthetic + real) for retraining."""
    _ensure_dirs()
    docs = []
    for d in [SYNTHETIC_DIR, REAL_DIR]:
        for p in sorted(d.glob("*.json")):
            with open(p) as f:
                docs.append(json.load(f))
    return docs


def update_retrain_timestamp() -> None:
    """Mark the last retrain time in the manifest."""
    with _lock:
        manifest = _load_manifest()
        manifest["last_retrain"] = datetime.now(timezone.utc).isoformat()
        _save_manifest(manifest)


def should_auto_retrain() -> bool:
    """Check if auto-retrain threshold is reached (every 25 new real profiles)."""
    with _lock:
        manifest = _load_manifest()
    real_count = manifest.get("real", 0)
    return real_count > 0 and real_count % 25 == 0


def _top_archetype(classification: dict[str, Any]) -> str:
    if not classification:
        return "unknown"
    return max(classification, key=lambda k: classification.get(k, 0), default="unknown")
