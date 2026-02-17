"""Centralized tax jurisdiction data loader.

Single source of truth: data/tax_jurisdictions.json
All modules that need tax rates should import from here.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"
_TAX_FILE = DATA_DIR / "tax_jurisdictions.json"

# Mapping from legacy codes (used in existing profiles) to new JSON keys
_LEGACY_CODE_MAP: dict[str, str] = {
    "CA": "US_CA", "TX": "US_TX", "FL": "US_FL", "NY": "US_NY",
    "WA": "US_WA", "IL": "US_IL", "MA": "US_MA", "NJ": "US_NJ",
    "NV": "US_NV", "TN": "US_TN", "WY": "US_WY", "CT": "US_CT",
    "PA": "US_PA", "OH": "US_OH", "CO": "US_CO", "GA": "US_GA",
    "NC": "US_NC", "VA": "US_VA", "AZ": "US_AZ", "OR": "US_OR",
    "SD": "US_SD", "AK": "US_AK", "NH": "US_NH",
    # International codes stay the same (except Canada)
    "CA_INT": "CAN",
    "RO": "RO", "SG": "SG", "UK": "UK", "DE": "DE",
    "AU": "AU", "JP": "JP", "CH": "CH", "HK": "HK", "AE": "AE",
    "CAN": "CAN",
}

_cache: dict[str, Any] | None = None


def load_jurisdictions() -> dict[str, Any]:
    """Load the full tax jurisdictions dict from JSON."""
    global _cache
    if _cache is not None:
        return _cache
    if not _TAX_FILE.exists():
        logger.warning("Tax jurisdictions file not found: %s", _TAX_FILE)
        return {}
    with open(_TAX_FILE) as f:
        _cache = json.load(f)
    return _cache


def _resolve_code(code: str) -> str:
    """Resolve a legacy or new-format code to the JSON key."""
    if code in load_jurisdictions():
        return code
    return _LEGACY_CODE_MAP.get(code, code)


def get_jurisdiction(code: str) -> dict[str, Any] | None:
    """Look up a single jurisdiction by code (handles legacy and new formats)."""
    resolved = _resolve_code(code)
    return load_jurisdictions().get(resolved)


def get_combined_long_term_rate(code: str) -> float:
    """Get the combined long-term capital gains rate for a jurisdiction."""
    jur = get_jurisdiction(code)
    if jur is None:
        return 0.20  # default to federal-only
    return jur.get("combined_long_term", 0.20)


def get_combined_short_term_rate(code: str) -> float:
    """Get the combined short-term capital gains rate for a jurisdiction."""
    jur = get_jurisdiction(code)
    if jur is None:
        return 0.37  # default to federal-only
    return jur.get("combined_short_term", 0.37)


# ---------------------------------------------------------------------------
# Backward-compatible exports used by generator/profiles.py & simulate.py
# ---------------------------------------------------------------------------

# US state codes (new format for profile generation)
US_STATES = [
    "US_CA", "US_NY", "US_NJ", "US_IL", "US_MA",
    "US_TX", "US_FL", "US_WA", "US_NV", "US_TN", "US_WY",
    "US_CT", "US_PA", "US_OH", "US_CO", "US_GA",
    "US_NC", "US_VA", "US_AZ", "US_OR",
]

INTL_CODES = ["RO", "SG", "UK", "DE", "AU", "JP", "CAN", "CH", "HK", "AE"]


def build_tax_rates_compat() -> dict[str, float]:
    """Build a TAX_RATES dict mapping jurisdiction codes to combined long-term rates.

    Includes both new-format and legacy codes for backward compatibility.
    """
    jurisdictions = load_jurisdictions()
    rates: dict[str, float] = {}
    for key, jur in jurisdictions.items():
        rates[key] = jur.get("combined_long_term", 0.20)
    # Also add legacy codes
    for legacy, new in _LEGACY_CODE_MAP.items():
        if new in rates and legacy not in rates:
            rates[legacy] = rates[new]
    return rates


# Eagerly load on import so TAX_RATES is available as a module-level dict
TAX_RATES: dict[str, float] = build_tax_rates_compat()
