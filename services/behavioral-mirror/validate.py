"""Validate extracted profiles against ground truth archetype weights."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"

ARCHETYPE_SCORE_MAP = {
    "momentum": "momentum_score",
    "value": "value_score",
    "income": "income_score",
    "swing": "swing_score",
    "day_trader": "day_trading_score",
    "event_driven": "event_driven_score",
    "mean_reversion": "mean_reversion_score",
    "passive_dca": "passive_dca_score",
}


def _normalize_scores(traits: dict[str, int]) -> dict[str, float]:
    """Normalize trait scores to weights summing to 1.0."""
    archetype_scores = {}
    for archetype, score_key in ARCHETYPE_SCORE_MAP.items():
        archetype_scores[archetype] = max(traits.get(score_key, 0), 0)

    total = sum(archetype_scores.values())
    if total <= 0:
        return {k: 1.0 / len(archetype_scores) for k in archetype_scores}

    return {k: v / total for k, v in archetype_scores.items()}


def run_validation(
    extracted_dir: str | Path | None = None,
    ground_truth_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Compare extracted profiles to ground truth.

    Returns validation report dict.
    """
    ext_dir = Path(extracted_dir or DATA_DIR / "extracted")
    gt_dir = Path(ground_truth_dir or DATA_DIR / "ground_truth")

    if not ext_dir.exists() or not gt_dir.exists():
        return {"error": "Missing extracted or ground_truth directories"}

    ext_files = {p.stem: p for p in ext_dir.glob("*.json")}
    gt_files = {p.stem: p for p in gt_dir.glob("*.json")}

    common_ids = sorted(set(ext_files) & set(gt_files))
    if not common_ids:
        return {"error": "No matching trader IDs between extracted and ground truth"}

    logger.info("Validating %d traders", len(common_ids))

    # Per-archetype tracking
    per_archetype: dict[str, dict[str, list[float]]] = {
        a: {"predicted": [], "actual": []} for a in ARCHETYPE_SCORE_MAP
    }

    dominant_correct = 0
    dominant_total = 0
    top2_correct = 0
    per_trader_results: list[dict[str, Any]] = []

    for tid in common_ids:
        with open(ext_files[tid]) as f:
            ext = json.load(f)
        with open(gt_files[tid]) as f:
            gt = json.load(f)

        gt_weights = gt.get("archetype_weights", {})
        ext_traits = ext.get("traits", {})

        # Normalize extracted scores to weights
        ext_weights = _normalize_scores(ext_traits)

        # Collect per-archetype
        for archetype in ARCHETYPE_SCORE_MAP:
            actual = gt_weights.get(archetype, 0.0)
            predicted = ext_weights.get(archetype, 0.0)
            per_archetype[archetype]["predicted"].append(predicted)
            per_archetype[archetype]["actual"].append(actual)

        # Dominant archetype accuracy
        if gt_weights:
            gt_dominant = max(gt_weights, key=gt_weights.get)  # type: ignore[arg-type]
            ext_dominant = max(ext_weights, key=ext_weights.get)  # type: ignore[arg-type]
            dominant_total += 1
            correct = gt_dominant == ext_dominant
            if correct:
                dominant_correct += 1

            # Top-2 accuracy
            gt_top2 = sorted(gt_weights, key=gt_weights.get, reverse=True)[:2]  # type: ignore[arg-type]
            if ext_dominant in gt_top2:
                top2_correct += 1

            per_trader_results.append({
                "trader_id": tid,
                "gt_dominant": gt_dominant,
                "ext_dominant": ext_dominant,
                "correct": correct,
                "gt_weights": gt_weights,
                "ext_weights": {k: round(v, 4) for k, v in ext_weights.items()},
            })

    # Compute metrics per archetype
    archetype_metrics: dict[str, dict[str, float]] = {}
    for archetype in ARCHETYPE_SCORE_MAP:
        actual = np.array(per_archetype[archetype]["actual"])
        predicted = np.array(per_archetype[archetype]["predicted"])

        mae = float(np.mean(np.abs(actual - predicted)))
        if len(actual) >= 3 and np.std(actual) > 0 and np.std(predicted) > 0:
            corr = float(np.corrcoef(actual, predicted)[0, 1])
        else:
            corr = 0.0

        archetype_metrics[archetype] = {
            "pearson_correlation": round(corr, 4),
            "mae": round(mae, 4),
            "n_samples": len(actual),
        }

    # Overall metrics
    dominant_accuracy = dominant_correct / dominant_total if dominant_total > 0 else 0.0
    top2_accuracy = top2_correct / dominant_total if dominant_total > 0 else 0.0
    avg_correlation = np.mean([m["pearson_correlation"] for m in archetype_metrics.values()])
    avg_mae = np.mean([m["mae"] for m in archetype_metrics.values()])

    # Find misclassified traders
    misclassified = [r for r in per_trader_results if not r["correct"]]

    report = {
        "n_traders": len(common_ids),
        "dominant_archetype_accuracy": round(dominant_accuracy, 4),
        "top2_accuracy": round(top2_accuracy, 4),
        "avg_pearson_correlation": round(float(avg_correlation), 4),
        "avg_mae": round(float(avg_mae), 4),
        "per_archetype": archetype_metrics,
        "misclassified_count": len(misclassified),
        "misclassified_traders": misclassified[:10],  # top 10
    }

    return report


def print_report(report: dict[str, Any]) -> None:
    """Print a human-readable validation report."""
    if "error" in report:
        print(f"Validation error: {report['error']}")
        return

    print("\n" + "=" * 60)
    print("  BEHAVIORAL MIRROR — VALIDATION REPORT")
    print("=" * 60)
    print(f"  Traders evaluated:           {report['n_traders']}")
    print(f"  Dominant archetype accuracy:  {report['dominant_archetype_accuracy']:.1%}")
    print(f"  Top-2 accuracy:              {report['top2_accuracy']:.1%}")
    print(f"  Avg Pearson correlation:     {report['avg_pearson_correlation']:.4f}")
    print(f"  Avg MAE:                     {report['avg_mae']:.4f}")
    print()

    print("  Per-archetype breakdown:")
    print(f"  {'Archetype':<18} {'Correlation':>12} {'MAE':>8}")
    print("  " + "-" * 40)
    for arch, metrics in report["per_archetype"].items():
        print(f"  {arch:<18} {metrics['pearson_correlation']:>12.4f} {metrics['mae']:>8.4f}")

    mc = report.get("misclassified_count", 0)
    print(f"\n  Misclassified: {mc}")
    if mc > 0:
        print(f"  {'Trader':<8} {'Ground Truth':<18} {'Extracted':<18}")
        print("  " + "-" * 44)
        for m in report.get("misclassified_traders", []):
            print(f"  {m['trader_id']:<8} {m['gt_dominant']:<18} {m['ext_dominant']:<18}")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    report = run_validation()
    print_report(report)
