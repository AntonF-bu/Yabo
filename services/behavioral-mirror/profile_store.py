"""Persistent profile storage for real user profiles.

Saves extracted feature profiles so the classifier can improve over time.

Storage strategy:
    - Real profiles: Supabase (survives Railway redeploys) + local fallback

Storage layout (local):
    data/profiles/
        real/R001.json …          (local fallback only)
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
REAL_DIR = PROFILES_DIR / "real"
MANIFEST_PATH = PROFILES_DIR / "manifest.json"

_lock = threading.Lock()


def _ensure_dirs() -> None:
    REAL_DIR.mkdir(parents=True, exist_ok=True)


def _load_manifest() -> dict[str, Any]:
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            return json.load(f)
    return {
        "total_profiles": 0,
        "real": 0,
        "last_retrain": None,
        "last_upload": None,
        "next_real_id": 1,
    }


def _save_manifest(manifest: dict[str, Any]) -> None:
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)


def get_manifest() -> dict[str, Any]:
    """Return current manifest (thread-safe).

    If Supabase is configured, real count comes from Supabase.
    """
    from storage.supabase_client import is_configured, get_profile_count

    with _lock:
        manifest = _load_manifest()

    if is_configured():
        real_count = get_profile_count()
        manifest["real"] = real_count
        manifest["total_profiles"] = real_count

    return manifest


def _next_real_id(manifest: dict[str, Any]) -> str:
    """Get next R-prefixed ID and bump counter."""
    from storage.supabase_client import is_configured, get_next_profile_id

    if is_configured():
        return get_next_profile_id()

    num = manifest.get("next_real_id", 1)
    profile_id = f"R{num:03d}"
    manifest["next_real_id"] = num + 1
    return profile_id


def _find_local_duplicate(features_hash: str) -> str | None:
    """Check local real profile JSONs for a matching features_hash."""
    if not REAL_DIR.exists():
        return None
    for p in REAL_DIR.glob("R*.json"):
        with open(p) as f:
            doc = json.load(f)
        if doc.get("features_hash") == features_hash:
            return doc["profile_id"]
    return None


def save_real_profile(
    extracted_profile: dict[str, Any],
    classification: dict[str, Any],
) -> str:
    """Persist a real user's extracted features after /analyze.

    Returns the assigned profile ID (e.g. "R001").
    If an identical feature set already exists, returns the existing ID
    instead of creating a duplicate.
    Saves to Supabase if configured, with local fallback.
    Does NOT store raw CSV data or individual trades.
    """
    from storage.supabase_client import (
        is_configured, save_profile as supa_save,
        compute_features_hash, find_by_features_hash,
    )

    features_hash = compute_features_hash(extracted_profile)

    # ── Dedup check ──────────────────────────────────────────────────────
    if is_configured():
        existing_id = find_by_features_hash(features_hash)
        if existing_id:
            logger.info(
                "Duplicate profile detected, returning existing %s", existing_id,
            )
            return existing_id
    else:
        existing_id = _find_local_duplicate(features_hash)
        if existing_id:
            logger.info(
                "Duplicate profile detected (local), returning existing %s",
                existing_id,
            )
            return existing_id

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
            "features_hash": features_hash,
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

        # Try Supabase first (fire-and-forget — don't block if it fails)
        saved_to_supabase = False
        if is_configured():
            saved_to_supabase = supa_save(doc)

        # Always save locally as fallback
        out_path = REAL_DIR / f"{profile_id}.json"
        with open(out_path, "w") as f:
            json.dump(doc, f, indent=2, default=str)

        if not is_configured():
            # Only update manifest real count if not using Supabase
            manifest["real"] += 1
            manifest["total_profiles"] = manifest["real"]

        manifest["last_upload"] = datetime.now(timezone.utc).isoformat()
        _save_manifest(manifest)

    logger.info(
        "Saved real profile %s (%d trades, supabase=%s)",
        profile_id, doc["trade_count"], saved_to_supabase,
    )
    return profile_id


def list_real_profiles() -> list[dict[str, Any]]:
    """Return metadata for all real profiles (no full features -- privacy).

    Uses Supabase if configured, otherwise falls back to local files.
    """
    from storage.supabase_client import is_configured, list_profiles_metadata

    if is_configured():
        return list_profiles_metadata()

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
    """Remove a real profile. Deletes from Supabase + local.

    Returns True if found and deleted from at least one location.
    """
    from storage.supabase_client import is_configured, delete_profile as supa_delete

    deleted = False

    if is_configured():
        deleted = supa_delete(profile_id)

    # Also delete local copy if present
    path = REAL_DIR / f"{profile_id}.json"
    if path.exists():
        path.unlink()
        deleted = True

    if deleted:
        with _lock:
            manifest = _load_manifest()
            if not is_configured():
                manifest["real"] = max(0, manifest.get("real", 1) - 1)
                manifest["total_profiles"] = manifest["real"]
            _save_manifest(manifest)
        logger.info("Deleted real profile %s", profile_id)

    return deleted


def load_all_profiles() -> list[dict[str, Any]]:
    """Load all real profile documents.

    Real profiles come from Supabase if configured, otherwise local.
    """
    from storage.supabase_client import is_configured, get_all_real_profiles

    _ensure_dirs()
    docs = []

    # Real: Supabase if configured, otherwise local
    if is_configured():
        real_profiles = get_all_real_profiles()
        docs.extend(real_profiles)
        logger.info("Loaded %d real profiles from Supabase", len(real_profiles))
    else:
        for p in sorted(REAL_DIR.glob("*.json")):
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
    from storage.supabase_client import is_configured, get_profile_count

    if is_configured():
        real_count = get_profile_count()
    else:
        with _lock:
            manifest = _load_manifest()
        real_count = manifest.get("real", 0)

    return real_count > 0 and real_count % 25 == 0


def _top_archetype(classification: dict[str, Any]) -> str:
    if not classification:
        return "unknown"
    return max(classification, key=lambda k: classification.get(k, 0), default="unknown")
