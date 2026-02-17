"""Train GMM classifier on extracted feature profiles."""

from __future__ import annotations

import json
import logging
import pickle
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MODEL_DIR = DATA_DIR / "models"

ARCHETYPES = [
    "momentum", "value", "income", "swing",
    "day_trader", "event_driven", "mean_reversion", "passive_dca",
]

# Canonical archetype signatures: what each archetype "looks like" in feature space.
# Values are approximate centroids for the normalized features below.
# Order matches FEATURE_KEYS.
ARCHETYPE_SIGNATURES = {
    "momentum": {
        "mean_hold": 15, "median_hold": 12, "std_hold": 8,
        "breakout_pct": 0.55, "dip_buy_pct": 0.15, "earnings_pct": 0.10,
        "pct_above_ma20": 0.65, "pct_below_ma20": 0.35,
        "avg_rsi_at_entry": 58, "avg_ma_dev": 0.03,
        "avg_vol_ratio": 1.3, "dca_score": 0.0,
        "trade_freq": 14, "win_rate": 0.55, "profit_factor": 1.5,
        "avg_position_pct": 12, "max_position_pct": 20,
        "position_consistency": 0.7, "hhi_index": 0.15,
        "post_loss_sizing": -0.05, "revenge_score": 10,
        "trailing_stop": 1, "stop_loss": 0,
        "intraday_pct": 0.02, "short_pct": 0.15, "long_pct": 0.05,
        "avg_winner_hold": 18, "avg_loser_hold": 10,
    },
    "value": {
        "mean_hold": 120, "median_hold": 100, "std_hold": 50,
        "breakout_pct": 0.10, "dip_buy_pct": 0.60, "earnings_pct": 0.05,
        "pct_above_ma20": 0.35, "pct_below_ma20": 0.65,
        "avg_rsi_at_entry": 42, "avg_ma_dev": -0.02,
        "avg_vol_ratio": 1.0, "dca_score": 0.0,
        "trade_freq": 3, "win_rate": 0.55, "profit_factor": 1.8,
        "avg_position_pct": 10, "max_position_pct": 15,
        "position_consistency": 0.8, "hhi_index": 0.12,
        "post_loss_sizing": -0.02, "revenge_score": 5,
        "trailing_stop": 0, "stop_loss": 0,
        "intraday_pct": 0.0, "short_pct": 0.05, "long_pct": 0.60,
        "avg_winner_hold": 130, "avg_loser_hold": 90,
    },
    "income": {
        "mean_hold": 250, "median_hold": 220, "std_hold": 80,
        "breakout_pct": 0.05, "dip_buy_pct": 0.25, "earnings_pct": 0.02,
        "pct_above_ma20": 0.45, "pct_below_ma20": 0.55,
        "avg_rsi_at_entry": 48, "avg_ma_dev": -0.01,
        "avg_vol_ratio": 0.9, "dca_score": 0.7,
        "trade_freq": 2, "win_rate": 0.50, "profit_factor": 1.3,
        "avg_position_pct": 8, "max_position_pct": 12,
        "position_consistency": 0.85, "hhi_index": 0.10,
        "post_loss_sizing": -0.01, "revenge_score": 2,
        "trailing_stop": 0, "stop_loss": 0,
        "intraday_pct": 0.0, "short_pct": 0.02, "long_pct": 0.80,
        "avg_winner_hold": 260, "avg_loser_hold": 200,
    },
    "swing": {
        "mean_hold": 8, "median_hold": 6, "std_hold": 5,
        "breakout_pct": 0.30, "dip_buy_pct": 0.30, "earnings_pct": 0.05,
        "pct_above_ma20": 0.50, "pct_below_ma20": 0.50,
        "avg_rsi_at_entry": 50, "avg_ma_dev": 0.0,
        "avg_vol_ratio": 1.1, "dca_score": 0.0,
        "trade_freq": 15, "win_rate": 0.52, "profit_factor": 1.3,
        "avg_position_pct": 10, "max_position_pct": 18,
        "position_consistency": 0.65, "hhi_index": 0.14,
        "post_loss_sizing": -0.03, "revenge_score": 15,
        "trailing_stop": 1, "stop_loss": 0,
        "intraday_pct": 0.05, "short_pct": 0.50, "long_pct": 0.02,
        "avg_winner_hold": 9, "avg_loser_hold": 7,
    },
    "day_trader": {
        "mean_hold": 0.5, "median_hold": 0.3, "std_hold": 0.5,
        "breakout_pct": 0.40, "dip_buy_pct": 0.20, "earnings_pct": 0.03,
        "pct_above_ma20": 0.55, "pct_below_ma20": 0.45,
        "avg_rsi_at_entry": 52, "avg_ma_dev": 0.01,
        "avg_vol_ratio": 1.5, "dca_score": 0.0,
        "trade_freq": 50, "win_rate": 0.50, "profit_factor": 1.1,
        "avg_position_pct": 15, "max_position_pct": 25,
        "position_consistency": 0.6, "hhi_index": 0.18,
        "post_loss_sizing": -0.02, "revenge_score": 25,
        "trailing_stop": 0, "stop_loss": 1,
        "intraday_pct": 0.70, "short_pct": 0.90, "long_pct": 0.0,
        "avg_winner_hold": 0.4, "avg_loser_hold": 0.3,
    },
    "event_driven": {
        "mean_hold": 6, "median_hold": 4, "std_hold": 5,
        "breakout_pct": 0.20, "dip_buy_pct": 0.10, "earnings_pct": 0.60,
        "pct_above_ma20": 0.50, "pct_below_ma20": 0.50,
        "avg_rsi_at_entry": 50, "avg_ma_dev": 0.0,
        "avg_vol_ratio": 1.2, "dca_score": 0.0,
        "trade_freq": 8, "win_rate": 0.55, "profit_factor": 1.6,
        "avg_position_pct": 10, "max_position_pct": 16,
        "position_consistency": 0.7, "hhi_index": 0.13,
        "post_loss_sizing": -0.04, "revenge_score": 10,
        "trailing_stop": 0, "stop_loss": 0,
        "intraday_pct": 0.05, "short_pct": 0.35, "long_pct": 0.05,
        "avg_winner_hold": 7, "avg_loser_hold": 5,
    },
    "mean_reversion": {
        "mean_hold": 12, "median_hold": 10, "std_hold": 7,
        "breakout_pct": 0.10, "dip_buy_pct": 0.60, "earnings_pct": 0.03,
        "pct_above_ma20": 0.30, "pct_below_ma20": 0.70,
        "avg_rsi_at_entry": 38, "avg_ma_dev": -0.03,
        "avg_vol_ratio": 1.1, "dca_score": 0.0,
        "trade_freq": 14, "win_rate": 0.60, "profit_factor": 1.4,
        "avg_position_pct": 10, "max_position_pct": 18,
        "position_consistency": 0.7, "hhi_index": 0.15,
        "post_loss_sizing": -0.05, "revenge_score": 10,
        "trailing_stop": 0, "stop_loss": 1,
        "intraday_pct": 0.02, "short_pct": 0.25, "long_pct": 0.03,
        "avg_winner_hold": 10, "avg_loser_hold": 14,
    },
    "passive_dca": {
        "mean_hold": 200, "median_hold": 180, "std_hold": 60,
        "breakout_pct": 0.05, "dip_buy_pct": 0.10, "earnings_pct": 0.02,
        "pct_above_ma20": 0.50, "pct_below_ma20": 0.50,
        "avg_rsi_at_entry": 50, "avg_ma_dev": 0.0,
        "avg_vol_ratio": 0.9, "dca_score": 1.0,
        "trade_freq": 2, "win_rate": 0.48, "profit_factor": 1.2,
        "avg_position_pct": 6, "max_position_pct": 10,
        "position_consistency": 0.90, "hhi_index": 0.08,
        "post_loss_sizing": 0.0, "revenge_score": 0,
        "trailing_stop": 0, "stop_loss": 0,
        "intraday_pct": 0.0, "short_pct": 0.01, "long_pct": 0.70,
        "avg_winner_hold": 210, "avg_loser_hold": 180,
    },
}

# Feature keys extracted from each profile JSON, in stable order.
FEATURE_KEYS = [
    "mean_hold", "median_hold", "std_hold",
    "breakout_pct", "dip_buy_pct", "earnings_pct",
    "pct_above_ma20", "pct_below_ma20",
    "avg_rsi_at_entry", "avg_ma_dev",
    "avg_vol_ratio", "dca_score",
    "trade_freq", "win_rate", "profit_factor",
    "avg_position_pct", "max_position_pct",
    "position_consistency", "hhi_index",
    "post_loss_sizing", "revenge_score",
    "trailing_stop", "stop_loss",
    "intraday_pct", "short_pct", "long_pct",
    "avg_winner_hold", "avg_loser_hold",
]


def _extract_feature_vector(profile: dict[str, Any]) -> list[float]:
    """Pull a flat numeric vector from an extracted profile JSON."""
    patterns = profile.get("patterns", {})
    hold = patterns.get("holding_period", {})
    entry = patterns.get("entry_patterns", {})
    exit_p = patterns.get("exit_patterns", {})
    risk = profile.get("risk_profile", {})
    stress = profile.get("stress_response", {})
    dist = hold.get("distribution", {})
    tc = patterns.get("ticker_concentration", {})

    dca_hard = 1.0 if entry.get("dca_pattern_detected") else 0.0
    dca_soft = 0.5 if entry.get("dca_soft_detected") else 0.0
    dca_score = max(dca_hard, dca_soft)

    short_pct = dist.get("intraday", 0) + dist.get("1_5_days", 0)
    long_pct = dist.get("90_365_days", 0) + dist.get("365_plus_days", 0)

    return [
        hold.get("mean_days", 30),
        hold.get("median_days", 30),
        hold.get("std_days", 10),
        entry.get("breakout_pct", 0),
        entry.get("dip_buy_pct", 0),
        entry.get("earnings_proximity_pct", 0),
        entry.get("pct_above_ma20", 0.5),
        entry.get("pct_below_ma20", 0.5),
        entry.get("avg_rsi_at_entry", 50),
        entry.get("avg_entry_ma20_deviation", 0),
        entry.get("avg_vol_ratio_at_entry", 1.0),
        dca_score,
        patterns.get("trade_frequency_per_month", 5),
        patterns.get("win_rate", 0.5),
        patterns.get("profit_factor", 1.0),
        risk.get("avg_position_pct", 10),
        risk.get("max_position_pct", 15),
        risk.get("position_size_consistency", 0.7),
        tc.get("hhi_index", 0.15),
        stress.get("post_loss_sizing_change", 0),
        stress.get("revenge_trading_score", 0),
        1.0 if exit_p.get("trailing_stop_detected") else 0.0,
        1.0 if exit_p.get("stop_loss_detected") else 0.0,
        dist.get("intraday", 0),
        short_pct,
        long_pct,
        exit_p.get("avg_winner_hold_days", 30),
        exit_p.get("avg_loser_hold_days", 30),
    ]


def _build_signature_matrix() -> np.ndarray:
    """Build matrix of archetype signature vectors for component mapping."""
    rows = []
    for arch in ARCHETYPES:
        sig = ARCHETYPE_SIGNATURES[arch]
        rows.append([sig[k] for k in FEATURE_KEYS])
    return np.array(rows, dtype=float)


def train_gmm(n_components: int = 8) -> dict[str, Any]:
    """Train GMM on extracted profiles and save model artifacts.

    Returns training metrics dict.
    """
    extracted_dir = DATA_DIR / "extracted"
    if not extracted_dir.exists():
        raise FileNotFoundError(f"No extracted data at {extracted_dir}")

    profiles: list[dict] = []
    trader_ids: list[str] = []
    for p in sorted(extracted_dir.glob("*.json")):
        with open(p) as f:
            prof = json.load(f)
        profiles.append(prof)
        trader_ids.append(p.stem)

    if len(profiles) < n_components:
        raise ValueError(f"Need >= {n_components} profiles, found {len(profiles)}")

    # Build feature matrix
    X = np.array([_extract_feature_vector(p) for p in profiles], dtype=float)
    logger.info("Feature matrix: %d traders x %d features", X.shape[0], X.shape[1])

    # Standardize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Fit GMM
    gmm = GaussianMixture(
        n_components=n_components,
        covariance_type="full",
        n_init=5,
        max_iter=300,
        random_state=42,
    )
    gmm.fit(X_scaled)
    logger.info("GMM converged: %s (n_iter=%d)", gmm.converged_, gmm.n_iter_)

    # Map components to archetypes using signature proximity
    sig_matrix = _build_signature_matrix()  # (8, n_features)
    sig_scaled = scaler.transform(sig_matrix)  # scale with same scaler

    # GMM means: (n_components, n_features)
    component_means = gmm.means_

    # Compute distances from each component to each archetype signature
    # Use cosine-like similarity: normalize then dot product
    from sklearn.metrics.pairwise import euclidean_distances
    distances = euclidean_distances(component_means, sig_scaled)

    # Greedy assignment: assign each component to nearest unassigned archetype
    component_to_archetype: dict[int, str] = {}
    archetype_to_component: dict[str, int] = {}
    used_components: set[int] = set()
    used_archetypes: set[str] = set()

    # Sort all (distance, component, archetype_idx) pairs
    pairs = []
    for c in range(n_components):
        for a_idx in range(len(ARCHETYPES)):
            pairs.append((distances[c, a_idx], c, a_idx))
    pairs.sort()

    for dist_val, c, a_idx in pairs:
        if c in used_components or a_idx >= len(ARCHETYPES):
            continue
        arch = ARCHETYPES[a_idx]
        if arch in used_archetypes:
            continue
        component_to_archetype[c] = arch
        archetype_to_component[arch] = c
        used_components.add(c)
        used_archetypes.add(arch)
        if len(component_to_archetype) == min(n_components, len(ARCHETYPES)):
            break

    # Handle any unmapped components (if n_components > len(ARCHETYPES))
    for c in range(n_components):
        if c not in component_to_archetype:
            # Assign to nearest archetype (allowing duplicates)
            nearest = int(np.argmin(distances[c]))
            component_to_archetype[c] = ARCHETYPES[nearest]

    logger.info("Component-to-archetype mapping:")
    for c in range(n_components):
        arch = component_to_archetype[c]
        logger.info("  Component %d -> %s (distance: %.3f)",
                     c, arch, distances[c, ARCHETYPES.index(arch)])

    # Compute silhouette score
    labels = gmm.predict(X_scaled)
    sil_score = silhouette_score(X_scaled, labels) if len(set(labels)) > 1 else 0.0
    logger.info("Silhouette score: %.4f", sil_score)

    # Save model artifacts
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_DIR / "gmm_classifier.pkl", "wb") as f:
        pickle.dump(gmm, f)
    with open(MODEL_DIR / "feature_scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)
    with open(MODEL_DIR / "component_mapping.json", "w") as f:
        json.dump(component_to_archetype, f, indent=2)

    logger.info("Model saved to %s", MODEL_DIR)

    return {
        "n_traders": len(profiles),
        "n_components": n_components,
        "n_features": X.shape[1],
        "silhouette_score": round(sil_score, 4),
        "converged": gmm.converged_,
        "n_iterations": gmm.n_iter_,
        "component_weights": [round(w, 4) for w in gmm.weights_.tolist()],
        "component_mapping": {str(k): v for k, v in component_to_archetype.items()},
    }


def _validate_method(method_fn, method_name: str) -> dict[str, Any]:
    """Validate a classification method against ground truth.

    Args:
        method_fn: callable(profile_dict) -> dict[str, float] of archetype probs
        method_name: label for the report
    """
    extracted_dir = DATA_DIR / "extracted"
    gt_dir = DATA_DIR / "ground_truth"

    ext_files = {p.stem: p for p in sorted(extracted_dir.glob("*.json"))}
    gt_files = {p.stem: p for p in sorted(gt_dir.glob("*.json"))}
    common_ids = sorted(set(ext_files) & set(gt_files))

    if not common_ids:
        return {"error": "No matching trader IDs"}

    per_archetype: dict[str, dict[str, list[float]]] = {
        a: {"predicted": [], "actual": []} for a in ARCHETYPES
    }
    dominant_correct = 0
    top2_correct = 0
    total = 0

    for tid in common_ids:
        with open(ext_files[tid]) as f:
            ext = json.load(f)
        with open(gt_files[tid]) as f:
            gt = json.load(f)

        gt_weights = gt.get("archetype_weights", {})
        if not gt_weights:
            continue

        pred_weights = method_fn(ext)

        for arch in ARCHETYPES:
            per_archetype[arch]["predicted"].append(pred_weights.get(arch, 0.0))
            per_archetype[arch]["actual"].append(gt_weights.get(arch, 0.0))

        gt_dominant = max(gt_weights, key=gt_weights.get)  # type: ignore[arg-type]
        pred_dominant = max(pred_weights, key=pred_weights.get)  # type: ignore[arg-type]
        total += 1
        if gt_dominant == pred_dominant:
            dominant_correct += 1

        gt_top2 = sorted(gt_weights, key=gt_weights.get, reverse=True)[:2]  # type: ignore[arg-type]
        if pred_dominant in gt_top2:
            top2_correct += 1

    archetype_metrics: dict[str, dict[str, float]] = {}
    for arch in ARCHETYPES:
        actual = np.array(per_archetype[arch]["actual"])
        predicted = np.array(per_archetype[arch]["predicted"])
        mae = float(np.mean(np.abs(actual - predicted)))
        if len(actual) >= 3 and np.std(actual) > 0 and np.std(predicted) > 0:
            corr = float(np.corrcoef(actual, predicted)[0, 1])
        else:
            corr = 0.0
        archetype_metrics[arch] = {
            "pearson_correlation": round(corr, 4),
            "mae": round(mae, 4),
            "n_samples": len(actual),
        }

    avg_corr = np.mean([m["pearson_correlation"] for m in archetype_metrics.values()])

    return {
        "method": method_name,
        "n_traders": total,
        "dominant_archetype_accuracy": round(dominant_correct / max(total, 1), 4),
        "top2_accuracy": round(top2_correct / max(total, 1), 4),
        "avg_pearson_correlation": round(float(avg_corr), 4),
        "per_archetype": archetype_metrics,
    }


def validate_gmm() -> dict[str, Any]:
    """Validate pure GMM classification against ground truth."""
    from classifier.cluster import load_model, _gmm_classify

    load_model()
    return _validate_method(_gmm_classify, "gmm")


def build_hybrid_config() -> dict[str, Any]:
    """Compare GMM vs heuristic per-archetype and save hybrid config.

    Returns comparison report showing which method won each archetype.
    """
    from classifier.cluster import load_model, _gmm_classify, _heuristic_classify

    load_model()

    gmm_report = _validate_method(_gmm_classify, "gmm")
    heur_report = _validate_method(_heuristic_classify, "heuristic")

    gmm_preferred: list[str] = []
    comparison: dict[str, dict[str, Any]] = {}

    for arch in ARCHETYPES:
        g_corr = gmm_report["per_archetype"][arch]["pearson_correlation"]
        h_corr = heur_report["per_archetype"][arch]["pearson_correlation"]
        winner = "gmm" if g_corr > h_corr else "heuristic"
        if winner == "gmm":
            gmm_preferred.append(arch)
        comparison[arch] = {
            "gmm_corr": g_corr,
            "heuristic_corr": h_corr,
            "winner": winner,
        }

    # Save config
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    config = {"gmm_preferred": gmm_preferred}
    with open(MODEL_DIR / "hybrid_config.json", "w") as f:
        json.dump(config, f, indent=2)

    logger.info("Hybrid config saved: GMM preferred for %s", gmm_preferred)

    return {
        "gmm_preferred_archetypes": gmm_preferred,
        "per_archetype_comparison": comparison,
        "gmm_overall": {
            "avg_corr": gmm_report["avg_pearson_correlation"],
            "dominant_acc": gmm_report["dominant_archetype_accuracy"],
        },
        "heuristic_overall": {
            "avg_corr": heur_report["avg_pearson_correlation"],
            "dominant_acc": heur_report["dominant_archetype_accuracy"],
        },
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    print("\n=== Training GMM Classifier ===")
    metrics = train_gmm()
    print(json.dumps(metrics, indent=2))

    print("\n=== Building Hybrid Config ===")
    hybrid = build_hybrid_config()
    print(json.dumps(hybrid, indent=2))
