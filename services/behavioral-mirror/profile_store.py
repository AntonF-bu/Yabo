"""Persistent profile storage for the ML feedback loop.

Saves extracted feature profiles so the GMM can be retrained
on real user data in addition to synthetic profiles.

Storage strategy:
    - Synthetic profiles: local filesystem (regenerated at startup)
    - Real profiles: Supabase (survives Railway redeploys) + local fallback

Storage layout (local):
    data/profiles/
        synthetic/T001.json … T075.json
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
    """Return current manifest (thread-safe).

    If Supabase is configured, real count comes from Supabase.
    """
    from storage.supabase_client import is_configured, get_profile_count

    with _lock:
        manifest = _load_manifest()

    if is_configured():
        real_count = get_profile_count()
        manifest["real"] = real_count
        manifest["total_profiles"] = manifest["synthetic"] + real_count

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


def save_real_profile(
    extracted_profile: dict[str, Any],
    classification: dict[str, Any],
) -> str:
    """Persist a real user's extracted features after /analyze.

    Returns the assigned profile ID (e.g. "R001").
    Saves to Supabase if configured, with local fallback.
    Does NOT store raw CSV data or individual trades.
    """
    from storage.supabase_client import is_configured, save_profile as supa_save

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
            manifest["total_profiles"] = manifest["synthetic"] + manifest["real"]

        manifest["last_upload"] = datetime.now(timezone.utc).isoformat()
        _save_manifest(manifest)

    logger.info(
        "Saved real profile %s (%d trades, supabase=%s)",
        profile_id, doc["trade_count"], saved_to_supabase,
    )
    return profile_id


def save_synthetic_profile(
    trader_id: str,
    extracted_profile: dict[str, Any],
    ground_truth: dict[str, Any] | None = None,
) -> None:
    """Persist a synthetic trader's extracted features in the same format.

    Called during the startup pipeline when synthetic traders are generated.
    Synthetic profiles are always local only — not sent to Supabase.
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
                manifest["total_profiles"] = manifest["synthetic"] + manifest["real"]
            _save_manifest(manifest)
        logger.info("Deleted real profile %s", profile_id)

    return deleted


def load_all_profiles() -> list[dict[str, Any]]:
    """Load all profile documents (synthetic + real) for retraining.

    Synthetic profiles come from local filesystem.
    Real profiles come from Supabase if configured, otherwise local.
    """
    from storage.supabase_client import is_configured, get_all_real_profiles

    _ensure_dirs()
    docs = []

    # Synthetic: always local
    for p in sorted(SYNTHETIC_DIR.glob("*.json")):
        with open(p) as f:
            docs.append(json.load(f))

    # Real: Supabase if configured, otherwise local
    if is_configured():
        real_profiles = get_all_real_profiles()
        docs.extend(real_profiles)
        logger.info("Loaded %d real profiles from Supabase for retraining", len(real_profiles))
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
