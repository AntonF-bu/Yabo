"""Retrain GMM classifier using all persisted profiles (synthetic + real).

Usage:
    python -m classifier.retrain

Loads profiles from data/profiles/, extends the feature vector with
holdings_profile features, retrains the GMM, re-evaluates hybrid config,
and prints a comparison report.
"""

from __future__ import annotations

import json
import logging
import pickle
import sys
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

logger = logging.getLogger(__name__)

# Add project root so we can import profile_store, etc.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

DATA_DIR = _PROJECT_ROOT / "data"
MODEL_DIR = DATA_DIR / "models"

ARCHETYPES = [
    "momentum", "value", "income", "swing",
    "day_trader", "event_driven", "mean_reversion", "passive_dca",
]

# Extended feature keys: original 28 + 9 new holdings-based features
FEATURE_KEYS = [
    # --- Original 28 features (same order as train.py) ---
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
    # --- New holdings-based features (9 additional) ---
    "holdings_risk_score",
    "speculative_holdings_ratio",
    "high_vol_sector_pct", "medium_vol_sector_pct", "low_vol_sector_pct",
    "mcap_mega_pct", "mcap_large_pct", "mcap_mid_pct",
    "mcap_small_pct",  # micro is 1 - sum(others), skip to avoid multicollinearity
]


# Extended archetype signatures (add holdings features to each)
_HOLDINGS_SIGNATURES = {
    "momentum": {
        "holdings_risk_score": 45, "speculative_holdings_ratio": 0.2,
        "high_vol_sector_pct": 0.5, "medium_vol_sector_pct": 0.3, "low_vol_sector_pct": 0.2,
        "mcap_mega_pct": 0.2, "mcap_large_pct": 0.3, "mcap_mid_pct": 0.3, "mcap_small_pct": 0.15,
    },
    "value": {
        "holdings_risk_score": 15, "speculative_holdings_ratio": 0.02,
        "high_vol_sector_pct": 0.15, "medium_vol_sector_pct": 0.35, "low_vol_sector_pct": 0.5,
        "mcap_mega_pct": 0.5, "mcap_large_pct": 0.35, "mcap_mid_pct": 0.1, "mcap_small_pct": 0.04,
    },
    "income": {
        "holdings_risk_score": 10, "speculative_holdings_ratio": 0.0,
        "high_vol_sector_pct": 0.1, "medium_vol_sector_pct": 0.2, "low_vol_sector_pct": 0.7,
        "mcap_mega_pct": 0.6, "mcap_large_pct": 0.3, "mcap_mid_pct": 0.05, "mcap_small_pct": 0.03,
    },
    "swing": {
        "holdings_risk_score": 40, "speculative_holdings_ratio": 0.15,
        "high_vol_sector_pct": 0.4, "medium_vol_sector_pct": 0.35, "low_vol_sector_pct": 0.25,
        "mcap_mega_pct": 0.3, "mcap_large_pct": 0.3, "mcap_mid_pct": 0.25, "mcap_small_pct": 0.1,
    },
    "day_trader": {
        "holdings_risk_score": 50, "speculative_holdings_ratio": 0.25,
        "high_vol_sector_pct": 0.5, "medium_vol_sector_pct": 0.3, "low_vol_sector_pct": 0.2,
        "mcap_mega_pct": 0.2, "mcap_large_pct": 0.25, "mcap_mid_pct": 0.3, "mcap_small_pct": 0.15,
    },
    "event_driven": {
        "holdings_risk_score": 35, "speculative_holdings_ratio": 0.1,
        "high_vol_sector_pct": 0.35, "medium_vol_sector_pct": 0.35, "low_vol_sector_pct": 0.3,
        "mcap_mega_pct": 0.35, "mcap_large_pct": 0.35, "mcap_mid_pct": 0.2, "mcap_small_pct": 0.08,
    },
    "mean_reversion": {
        "holdings_risk_score": 35, "speculative_holdings_ratio": 0.12,
        "high_vol_sector_pct": 0.4, "medium_vol_sector_pct": 0.35, "low_vol_sector_pct": 0.25,
        "mcap_mega_pct": 0.3, "mcap_large_pct": 0.35, "mcap_mid_pct": 0.2, "mcap_small_pct": 0.1,
    },
    "passive_dca": {
        "holdings_risk_score": 8, "speculative_holdings_ratio": 0.0,
        "high_vol_sector_pct": 0.1, "medium_vol_sector_pct": 0.15, "low_vol_sector_pct": 0.75,
        "mcap_mega_pct": 0.7, "mcap_large_pct": 0.2, "mcap_mid_pct": 0.05, "mcap_small_pct": 0.03,
    },
}


def _extract_feature_vector(profile: dict[str, Any]) -> list[float]:
    """Pull extended feature vector from profile (original 28 + 9 holdings features).

    Handles both raw extracted profiles and the wrapped profile_store format.
    """
    # Handle wrapped format (profile_store saves features nested under "features")
    features = profile.get("features", profile)

    patterns = features.get("patterns", {})
    hold = patterns.get("holding_period", {})
    entry = patterns.get("entry_patterns", {})
    exit_p = patterns.get("exit_patterns", {})
    risk = features.get("risk_profile", {})
    stress = features.get("stress_response", {})
    dist = hold.get("distribution", {})
    tc = patterns.get("ticker_concentration", {})

    dca_hard = 1.0 if entry.get("dca_pattern_detected") else 0.0
    dca_soft = 0.5 if entry.get("dca_soft_detected") else 0.0
    dca_score = max(dca_hard, dca_soft)

    short_pct = dist.get("intraday", 0) + dist.get("1_5_days", 0)
    long_pct = dist.get("90_365_days", 0) + dist.get("365_plus_days", 0)

    # Original 28 features
    vec = [
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

    # Holdings-based features (9 additional)
    # Check both top-level holdings_profile and features-nested
    hp = profile.get("holdings_profile") or features.get("holdings_profile") or {}
    vol_exp = hp.get("sector_volatility_exposure", {})
    mcap = hp.get("market_cap_distribution", {})

    vec.extend([
        hp.get("holdings_risk_score", 50),  # neutral default for older profiles
        hp.get("speculative_holdings_ratio", 0.0),
        vol_exp.get("high", 0.33),
        vol_exp.get("medium", 0.34),
        vol_exp.get("low", 0.33),
        mcap.get("mega", 0.2),
        mcap.get("large", 0.2),
        mcap.get("mid", 0.2),
        mcap.get("small", 0.2),
    ])

    return vec


def _build_signature_matrix() -> np.ndarray:
    """Build extended archetype signature matrix (8 archetypes x 37 features)."""
    from classifier.train import ARCHETYPE_SIGNATURES

    rows = []
    for arch in ARCHETYPES:
        base_sig = ARCHETYPE_SIGNATURES[arch]
        base_keys = [
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
        row = [base_sig[k] for k in base_keys]

        # Add holdings signature values
        h_sig = _HOLDINGS_SIGNATURES[arch]
        row.extend([
            h_sig["holdings_risk_score"],
            h_sig["speculative_holdings_ratio"],
            h_sig["high_vol_sector_pct"],
            h_sig["medium_vol_sector_pct"],
            h_sig["low_vol_sector_pct"],
            h_sig["mcap_mega_pct"],
            h_sig["mcap_large_pct"],
            h_sig["mcap_mid_pct"],
            h_sig["mcap_small_pct"],
        ])
        rows.append(row)

    return np.array(rows, dtype=float)


def retrain(n_components: int = 8) -> dict[str, Any]:
    """Retrain GMM on all persisted profiles (synthetic + real).

    Returns a results dict with accuracy comparison.
    """
    from profile_store import load_all_profiles, update_retrain_timestamp

    profiles = load_all_profiles()
    if not profiles:
        raise ValueError("No profiles found in data/profiles/")

    synthetic = [p for p in profiles if p.get("source") == "synthetic"]
    real = [p for p in profiles if p.get("source") == "real"]

    logger.info("Loaded %d profiles (%d synthetic, %d real)",
                len(profiles), len(synthetic), len(real))

    if len(profiles) < n_components:
        raise ValueError(
            f"Need >= {n_components} profiles, found {len(profiles)}"
        )

    # ── Capture old model accuracy before retraining ──
    old_metrics = _evaluate_current_model(synthetic)

    # ── Build feature matrix ──
    X = np.array([_extract_feature_vector(p) for p in profiles], dtype=float)
    logger.info("Feature matrix: %d x %d", X.shape[0], X.shape[1])

    # Handle any NaN/inf values
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # ── Try multiple component counts if enough data ──
    component_counts = [n_components]
    if len(profiles) > 200:
        component_counts.extend([9, 10])

    best_gmm = None
    best_scaler = scaler
    best_sil = -1.0
    best_n = n_components
    sil_scores: dict[int, float] = {}

    for nc in component_counts:
        if nc > len(profiles):
            continue
        gmm = GaussianMixture(
            n_components=nc,
            covariance_type="full",
            n_init=5,
            max_iter=300,
            random_state=42,
        )
        gmm.fit(X_scaled)
        labels = gmm.predict(X_scaled)
        n_unique = len(set(labels))
        sil = silhouette_score(X_scaled, labels) if n_unique > 1 else 0.0
        sil_scores[nc] = round(sil, 4)
        logger.info("  n_components=%d  silhouette=%.4f  converged=%s",
                     nc, sil, gmm.converged_)
        if sil > best_sil:
            best_sil = sil
            best_gmm = gmm
            best_n = nc

    logger.info("Best: n_components=%d (silhouette=%.4f)", best_n, best_sil)

    # ── Map components to archetypes ──
    sig_matrix = _build_signature_matrix()
    sig_scaled = scaler.transform(sig_matrix)

    from sklearn.metrics.pairwise import euclidean_distances
    distances = euclidean_distances(best_gmm.means_, sig_scaled)

    component_to_archetype: dict[int, str] = {}
    used_components: set[int] = set()
    used_archetypes: set[str] = set()

    pairs = []
    for c in range(best_n):
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
        used_components.add(c)
        used_archetypes.add(arch)
        if len(component_to_archetype) == min(best_n, len(ARCHETYPES)):
            break

    for c in range(best_n):
        if c not in component_to_archetype:
            nearest = int(np.argmin(distances[c]))
            component_to_archetype[c] = ARCHETYPES[nearest]

    # ── Save model artifacts ──
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_DIR / "gmm_classifier.pkl", "wb") as f:
        pickle.dump(best_gmm, f)
    with open(MODEL_DIR / "feature_scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)
    with open(MODEL_DIR / "component_mapping.json", "w") as f:
        json.dump(component_to_archetype, f, indent=2)

    logger.info("Model artifacts saved to %s", MODEL_DIR)

    # ── Reload model in cluster.py ──
    try:
        from classifier.cluster import load_model
        load_model()
    except Exception:
        pass

    # ── Build hybrid config ──
    hybrid_report = _build_hybrid_config(synthetic)

    # ── Evaluate new model accuracy ──
    new_metrics = _evaluate_current_model(synthetic)

    # ── Update manifest ──
    update_retrain_timestamp()

    # ── Build results report ──
    results = {
        "total_profiles": len(profiles),
        "synthetic": len(synthetic),
        "real": len(real),
        "n_components": best_n,
        "silhouette_scores": sil_scores,
        "component_mapping": {str(k): v for k, v in component_to_archetype.items()},
        "previous_accuracy": old_metrics,
        "new_accuracy": new_metrics,
        "hybrid_config": hybrid_report,
    }

    _print_report(results)
    return results


def _evaluate_current_model(
    synthetic_profiles: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate the current model against synthetic ground truth."""
    from classifier.cluster import is_loaded, load_model, _heuristic_classify

    if not is_loaded():
        try:
            load_model()
        except Exception:
            return {"error": "model_not_loaded"}

    from classifier.cluster import classify

    dominant_correct = 0
    total = 0
    all_corrs: list[float] = []

    per_archetype: dict[str, dict[str, list[float]]] = {
        a: {"predicted": [], "actual": []} for a in ARCHETYPES
    }

    for prof in synthetic_profiles:
        gt = prof.get("ground_truth", {})
        if not gt:
            continue

        features = prof.get("features", prof)
        try:
            result = classify(features)
        except Exception:
            continue

        probs = result.get("archetype_probabilities", {})
        total += 1

        gt_dominant = max(gt, key=lambda k: gt.get(k, 0))
        pred_dominant = result.get("dominant_archetype", "")
        if gt_dominant == pred_dominant:
            dominant_correct += 1

        for arch in ARCHETYPES:
            per_archetype[arch]["predicted"].append(probs.get(arch, 0.0))
            per_archetype[arch]["actual"].append(gt.get(arch, 0.0))

    if total == 0:
        return {"error": "no_ground_truth_profiles"}

    # Per-archetype correlation
    arch_corrs = {}
    for arch in ARCHETYPES:
        actual = np.array(per_archetype[arch]["actual"])
        predicted = np.array(per_archetype[arch]["predicted"])
        if len(actual) >= 3 and np.std(actual) > 0 and np.std(predicted) > 0:
            corr = float(np.corrcoef(actual, predicted)[0, 1])
        else:
            corr = 0.0
        arch_corrs[arch] = round(corr, 4)
        all_corrs.append(corr)

    return {
        "avg_correlation": round(float(np.mean(all_corrs)), 4),
        "dominant_accuracy": round(dominant_correct / max(total, 1), 4),
        "n_evaluated": total,
        "per_archetype": arch_corrs,
    }


def _build_hybrid_config(
    synthetic_profiles: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare GMM vs heuristic per-archetype and save hybrid config."""
    from classifier.cluster import _gmm_classify, _heuristic_classify

    gmm_corrs: dict[str, float] = {}
    heur_corrs: dict[str, float] = {}

    per_arch_gmm: dict[str, dict[str, list]] = {a: {"pred": [], "actual": []} for a in ARCHETYPES}
    per_arch_heur: dict[str, dict[str, list]] = {a: {"pred": [], "actual": []} for a in ARCHETYPES}

    for prof in synthetic_profiles:
        gt = prof.get("ground_truth", {})
        if not gt:
            continue

        features = prof.get("features", prof)
        try:
            gmm_probs = _gmm_classify(features)
            heur_probs = _heuristic_classify(features)
        except Exception:
            continue

        for arch in ARCHETYPES:
            per_arch_gmm[arch]["pred"].append(gmm_probs.get(arch, 0.0))
            per_arch_gmm[arch]["actual"].append(gt.get(arch, 0.0))
            per_arch_heur[arch]["pred"].append(heur_probs.get(arch, 0.0))
            per_arch_heur[arch]["actual"].append(gt.get(arch, 0.0))

    gmm_preferred: list[str] = []
    comparison: dict[str, dict[str, Any]] = {}

    for arch in ARCHETYPES:
        g_actual = np.array(per_arch_gmm[arch]["actual"])
        g_pred = np.array(per_arch_gmm[arch]["pred"])
        h_pred = np.array(per_arch_heur[arch]["pred"])

        g_corr = 0.0
        h_corr = 0.0
        if len(g_actual) >= 3:
            if np.std(g_actual) > 0 and np.std(g_pred) > 0:
                g_corr = float(np.corrcoef(g_actual, g_pred)[0, 1])
            if np.std(g_actual) > 0 and np.std(h_pred) > 0:
                h_corr = float(np.corrcoef(g_actual, h_pred)[0, 1])

        winner = "gmm" if g_corr > h_corr else "heuristic"
        if winner == "gmm":
            gmm_preferred.append(arch)

        gmm_corrs[arch] = round(g_corr, 4)
        heur_corrs[arch] = round(h_corr, 4)
        comparison[arch] = {
            "gmm_corr": round(g_corr, 4),
            "heuristic_corr": round(h_corr, 4),
            "winner": winner,
        }

    # Save config
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    config = {"gmm_preferred": gmm_preferred}
    with open(MODEL_DIR / "hybrid_config.json", "w") as f:
        json.dump(config, f, indent=2)

    return {
        "gmm_preferred_archetypes": gmm_preferred,
        "per_archetype": comparison,
    }


def _print_report(results: dict[str, Any]) -> None:
    """Print a human-readable retrain report."""
    print()
    print("=" * 60)
    print("  RETRAIN RESULTS")
    print("=" * 60)
    print(f"Total profiles: {results['total_profiles']} "
          f"({results['synthetic']} synthetic, {results['real']} real)")
    print(f"Components: {results['n_components']}")
    print()

    # Silhouette scores
    for nc, sil in results["silhouette_scores"].items():
        marker = " <-- selected" if nc == results["n_components"] else ""
        print(f"  n_components={nc}: silhouette={sil}{marker}")
    print()

    # Accuracy comparison
    old = results.get("previous_accuracy", {})
    new = results.get("new_accuracy", {})

    if "error" not in old and "error" not in new:
        print(f"Previous accuracy: {old.get('avg_correlation', 0):.4f} correlation, "
              f"{old.get('dominant_accuracy', 0):.0%} dominant")
        print(f"New accuracy:      {new.get('avg_correlation', 0):.4f} correlation, "
              f"{new.get('dominant_accuracy', 0):.0%} dominant")
        print()

        # Per-archetype changes
        old_per = old.get("per_archetype", {})
        new_per = new.get("per_archetype", {})
        print("Per-archetype changes:")
        for arch in ARCHETYPES:
            o = old_per.get(arch, 0)
            n = new_per.get(arch, 0)
            delta = n - o
            print(f"  {arch:20s}: {o:.4f} -> {n:.4f} ({delta:+.4f})")
    print()

    # Hybrid config
    hybrid = results.get("hybrid_config", {})
    per_arch = hybrid.get("per_archetype", {})
    if per_arch:
        print("Hybrid config (per-archetype method selection):")
        for arch in ARCHETYPES:
            comp = per_arch.get(arch, {})
            print(f"  {arch:20s}: GMM={comp.get('gmm_corr', 0):.4f}  "
                  f"Heur={comp.get('heuristic_corr', 0):.4f}  "
                  f"-> {comp.get('winner', '?')}")
        print(f"\nGMM preferred for: {hybrid.get('gmm_preferred_archetypes', [])}")

    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    results = retrain()
