"""Supabase client for persisting real user behavioral profiles.

Reads connection info from environment:
    SUPABASE_URL          – project URL (e.g. https://xxx.supabase.co)
    SUPABASE_SERVICE_KEY  – service_role key (bypasses RLS)

If either is missing, all operations gracefully return None / empty
so the service still works in local dev without Supabase.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_client = None
_initialized = False

TABLE = "behavioral_profiles"


def _get_client():
    """Lazy-init Supabase client. Returns None if env vars are missing."""
    global _client, _initialized

    if _initialized:
        return _client

    _initialized = True

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")

    if not url or not key:
        logger.info(
            "Supabase not configured (SUPABASE_URL / SUPABASE_SERVICE_KEY missing). "
            "Real profiles will only be stored locally."
        )
        return None

    try:
        from supabase import create_client
        _client = create_client(url, key)
        logger.info("Supabase client initialized for %s", url)
    except Exception:
        logger.exception("Failed to initialize Supabase client")
        _client = None

    return _client


def is_configured() -> bool:
    """Check if Supabase credentials are present."""
    return _get_client() is not None


def save_profile(doc: dict[str, Any]) -> bool:
    """Upsert a real profile to Supabase.

    Expects a dict with at least: id, source, features, classification.
    Returns True on success, False on failure.
    """
    client = _get_client()
    if client is None:
        return False

    try:
        date_range = doc.get("date_range", {})
        features = doc.get("features", {})
        row = {
            "id": doc["profile_id"],
            "created_at": doc.get("uploaded_at", datetime.now(timezone.utc).isoformat()),
            "source": doc.get("source", "real"),
            "csv_format": doc.get("csv_format"),
            "trade_count": doc.get("trade_count", 0),
            "unique_tickers": doc.get("unique_tickers", 0),
            "date_range_start": date_range.get("start"),
            "date_range_end": date_range.get("end"),
            "confidence_tier": doc.get("confidence_tier"),
            "top_archetype": _top_archetype(doc.get("classification", {})),
            "features": features,
            "features_hash": _compute_features_hash(features),
            "classification": doc.get("classification", {}),
            "holdings_profile": doc.get("holdings_profile", {}),
            "metadata": doc.get("metadata", {}),
        }

        client.table(TABLE).upsert(row).execute()
        logger.info("Saved profile %s to Supabase", doc["profile_id"])
        return True
    except Exception:
        logger.exception("Failed to save profile %s to Supabase", doc.get("profile_id"))
        return False


def get_all_real_profiles() -> list[dict[str, Any]]:
    """Fetch all real profiles from Supabase for retraining.

    Returns list of profile docs in the same format as local storage.
    """
    client = _get_client()
    if client is None:
        return []

    try:
        resp = (
            client.table(TABLE)
            .select("*")
            .eq("source", "real")
            .is_("deleted_at", "null")
            .order("created_at")
            .execute()
        )
        profiles = []
        for row in resp.data:
            profiles.append(_row_to_profile_doc(row))
        logger.info("Fetched %d real profiles from Supabase", len(profiles))
        return profiles
    except Exception:
        logger.exception("Failed to fetch profiles from Supabase")
        return []


def get_profile_count() -> int:
    """Return the count of active real profiles in Supabase."""
    client = _get_client()
    if client is None:
        return 0

    try:
        resp = (
            client.table(TABLE)
            .select("id", count="exact")
            .eq("source", "real")
            .is_("deleted_at", "null")
            .execute()
        )
        return resp.count or 0
    except Exception:
        logger.exception("Failed to count profiles in Supabase")
        return 0


def delete_profile(profile_id: str) -> bool:
    """Soft-delete a profile by setting deleted_at.

    Returns True on success, False on failure.
    """
    client = _get_client()
    if client is None:
        return False

    try:
        client.table(TABLE).update({
            "deleted_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", profile_id).execute()
        logger.info("Soft-deleted profile %s in Supabase", profile_id)
        return True
    except Exception:
        logger.exception("Failed to delete profile %s in Supabase", profile_id)
        return False


def get_next_profile_id() -> str:
    """Generate the next R-prefixed profile ID based on Supabase count.

    Uses MAX(id) query to find the highest existing ID.
    """
    client = _get_client()
    if client is None:
        return "R001"

    try:
        resp = (
            client.table(TABLE)
            .select("id")
            .eq("source", "real")
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        if resp.data:
            last_id = resp.data[0]["id"]
            # Extract numeric part from "R001", "R002", etc.
            num = int(last_id[1:]) + 1
        else:
            num = 1
        return f"R{num:03d}"
    except Exception:
        logger.exception("Failed to get next profile ID from Supabase")
        return "R001"


def list_profiles_metadata() -> list[dict[str, Any]]:
    """Return metadata for all real profiles (no full features -- privacy)."""
    client = _get_client()
    if client is None:
        return []

    try:
        resp = (
            client.table(TABLE)
            .select(
                "id, created_at, source, csv_format, trade_count, "
                "unique_tickers, date_range_start, date_range_end, "
                "confidence_tier, top_archetype"
            )
            .eq("source", "real")
            .is_("deleted_at", "null")
            .order("created_at")
            .execute()
        )
        return [
            {
                "profile_id": r["id"],
                "uploaded_at": r["created_at"],
                "trade_count": r.get("trade_count", 0),
                "unique_tickers": r.get("unique_tickers", 0),
                "date_range": {
                    "start": r.get("date_range_start"),
                    "end": r.get("date_range_end"),
                },
                "confidence_tier": r.get("confidence_tier"),
                "csv_format": r.get("csv_format"),
                "top_archetype": r.get("top_archetype"),
            }
            for r in resp.data
        ]
    except Exception:
        logger.exception("Failed to list profiles from Supabase")
        return []


def _row_to_profile_doc(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a Supabase row back to the profile doc format used locally."""
    return {
        "profile_id": row["id"],
        "source": row.get("source", "real"),
        "uploaded_at": row.get("created_at"),
        "csv_format": row.get("csv_format"),
        "trade_count": row.get("trade_count", 0),
        "unique_tickers": row.get("unique_tickers", 0),
        "date_range": {
            "start": row.get("date_range_start"),
            "end": row.get("date_range_end"),
        },
        "confidence_tier": row.get("confidence_tier"),
        "features": row.get("features", {}),
        "classification": row.get("classification", {}),
        "holdings_profile": row.get("holdings_profile", {}),
        "metadata": row.get("metadata", {}),
    }


def _compute_features_hash(features: dict[str, Any]) -> str:
    """SHA-256 of the canonical JSON representation of extracted features.

    Used for deduplication — if two uploads produce identical features,
    they'll have the same hash.
    """
    canonical = json.dumps(features, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _top_archetype(classification: dict[str, Any]) -> str:
    if not classification:
        return "unknown"
    return max(classification, key=lambda k: classification.get(k, 0), default="unknown")
