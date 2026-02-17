"""GMM-based trader classification into archetype probabilities."""

from __future__ import annotations

import json
import logging
import pickle
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent.parent / "data" / "models"

# Module-level cached model objects
_gmm = None
_scaler = None
_component_map: dict[int, str] = {}

ARCHETYPES = [
    "momentum", "value", "income", "swing",
    "day_trader", "event_driven", "mean_reversion", "passive_dca",
]


def load_model() -> bool:
    """Load trained GMM model, scaler, and component mapping.

    Returns True if model loaded successfully, False otherwise.
    """
    global _gmm, _scaler, _component_map

    gmm_path = MODEL_DIR / "gmm_classifier.pkl"
    scaler_path = MODEL_DIR / "feature_scaler.pkl"
    mapping_path = MODEL_DIR / "component_mapping.json"

    if not gmm_path.exists():
        logger.warning("GMM model not found at %s", gmm_path)
        return False

    with open(gmm_path, "rb") as f:
        _gmm = pickle.load(f)
    with open(scaler_path, "rb") as f:
        _scaler = pickle.load(f)
    with open(mapping_path) as f:
        raw = json.load(f)
        _component_map = {int(k): v for k, v in raw.items()}

    logger.info("GMM model loaded: %d components", _gmm.n_components)
    load_hybrid_config()
    return True


def is_loaded() -> bool:
    """Check if model is loaded."""
    return _gmm is not None


def _gmm_classify(extracted_profile: dict[str, Any]) -> dict[str, float]:
    """Pure GMM classification. Returns archetype -> probability dict."""
    from classifier.train import _extract_feature_vector
    vec = _extract_feature_vector(extracted_profile)
    X = np.array([vec], dtype=float)
    X_scaled = _scaler.transform(X)

    component_probs = _gmm.predict_proba(X_scaled)[0]

    archetype_probs: dict[str, float] = {a: 0.0 for a in ARCHETYPES}
    for comp_idx, prob in enumerate(component_probs):
        arch = _component_map.get(comp_idx, "momentum")
        archetype_probs[arch] += prob

    total = sum(archetype_probs.values())
    if total > 0:
        archetype_probs = {k: v / total for k, v in archetype_probs.items()}
    return archetype_probs


def _heuristic_classify(extracted_profile: dict[str, Any]) -> dict[str, float]:
    """Heuristic classification from trait scores. Returns archetype -> probability dict."""
    traits = extracted_profile.get("traits", {})
    score_map = {
        "momentum": max(traits.get("momentum_score", 0), 0),
        "value": max(traits.get("value_score", 0), 0),
        "income": max(traits.get("income_score", 0), 0),
        "swing": max(traits.get("swing_score", 0), 0),
        "day_trader": max(traits.get("day_trading_score", 0), 0),
        "event_driven": max(traits.get("event_driven_score", 0), 0),
        "mean_reversion": max(traits.get("mean_reversion_score", 0), 0),
        "passive_dca": max(traits.get("passive_dca_score", 0), 0),
    }
    total = sum(score_map.values())
    if total <= 0:
        return {k: 1.0 / len(score_map) for k in score_map}
    return {k: v / total for k, v in score_map.items()}


def _confidence_from_probs(probs: dict[str, float]) -> float:
    """Entropy-based confidence score."""
    arr = np.array(list(probs.values()))
    entropy = -np.sum(arr * np.log(arr + 1e-10))
    max_entropy = np.log(len(ARCHETYPES))
    return round(1.0 - (entropy / max_entropy), 4)


# Per-archetype method selection based on validation.
# GMM used where its per-archetype correlation beats heuristics.
# Updated after each training run by validate-and-compare logic.
_GMM_PREFERRED_ARCHETYPES: set[str] = set()


def load_hybrid_config() -> None:
    """Load hybrid config that records which archetypes prefer GMM."""
    global _GMM_PREFERRED_ARCHETYPES
    config_path = MODEL_DIR / "hybrid_config.json"
    if config_path.exists():
        with open(config_path) as f:
            _GMM_PREFERRED_ARCHETYPES = set(json.load(f).get("gmm_preferred", []))
        logger.info("Hybrid config: GMM preferred for %s", _GMM_PREFERRED_ARCHETYPES)


def classify(extracted_profile: dict[str, Any]) -> dict[str, Any]:
    """Hybrid classification: uses best method per archetype.

    Returns dict with archetype_probabilities (summing to 1.0),
    dominant_archetype, confidence_score, and both sub-methods.
    """
    if _gmm is None or _scaler is None:
        if not load_model():
            return _fallback_classification(extracted_profile)

    gmm_probs = _gmm_classify(extracted_profile)
    heuristic_probs = _heuristic_classify(extracted_profile)

    # Hybrid: pick per-archetype from whichever method is stronger
    hybrid_probs: dict[str, float] = {}
    for arch in ARCHETYPES:
        if arch in _GMM_PREFERRED_ARCHETYPES:
            hybrid_probs[arch] = gmm_probs[arch]
        else:
            hybrid_probs[arch] = heuristic_probs[arch]

    # Re-normalize
    total = sum(hybrid_probs.values())
    if total > 0:
        hybrid_probs = {k: v / total for k, v in hybrid_probs.items()}
    hybrid_probs = {k: round(v, 4) for k, v in hybrid_probs.items()}

    dominant = max(hybrid_probs, key=hybrid_probs.get)  # type: ignore[arg-type]
    confidence = _confidence_from_probs(hybrid_probs)

    return {
        "archetype_probabilities": hybrid_probs,
        "dominant_archetype": dominant,
        "confidence_score": confidence,
        "method": "hybrid",
        "gmm_probabilities": {k: round(v, 4) for k, v in gmm_probs.items()},
        "heuristic_probabilities": {k: round(v, 4) for k, v in heuristic_probs.items()},
        "gmm_preferred_archetypes": sorted(_GMM_PREFERRED_ARCHETYPES),
    }


def _fallback_classification(profile: dict[str, Any]) -> dict[str, Any]:
    """Fallback to heuristic scores if GMM model not available."""
    probs = _heuristic_classify(profile)
    probs = {k: round(v, 4) for k, v in probs.items()}
    dominant = max(probs, key=probs.get)  # type: ignore[arg-type]
    confidence = _confidence_from_probs(probs)

    return {
        "archetype_probabilities": probs,
        "dominant_archetype": dominant,
        "confidence_score": confidence,
        "method": "heuristic_fallback",
    }
