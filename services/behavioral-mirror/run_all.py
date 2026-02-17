"""Run the full pipeline: generate -> extract -> validate -> train GMM -> narratives."""

import json
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"


def main() -> None:
    logger.info("=" * 60)
    logger.info("  BEHAVIORAL MIRROR — FULL PIPELINE")
    logger.info("=" * 60)

    # Clear ready flag while pipeline runs
    flag = DATA_DIR / ".pipeline_complete"
    flag.unlink(missing_ok=True)

    logger.info("\n>>> PHASE 1: GENERATOR <<<")
    from run_generator import main as run_gen
    run_gen()

    logger.info("\n>>> PHASE 2: EXTRACTOR <<<")
    from run_extractor import main as run_ext
    run_ext()

    logger.info("\n>>> PHASE 3: VALIDATION (heuristic) <<<")
    from validate import run_validation, print_report
    report = run_validation()
    print_report(report)

    logger.info("\n>>> PHASE 3b: PERSIST PROFILES <<<")
    try:
        from profile_store import save_all_synthetic
        n_saved = save_all_synthetic()
        logger.info("Saved %d synthetic profiles to data/profiles/synthetic/", n_saved)
    except Exception:
        logger.exception("Profile persistence failed (non-fatal)")

    logger.info("\n>>> PHASE 3c: SUPABASE REAL PROFILES <<<")
    try:
        from storage.supabase_client import is_configured, get_profile_count
        if is_configured():
            real_count = get_profile_count()
            logger.info("Supabase connected: %d real profiles available for training", real_count)
        else:
            logger.info("Supabase not configured — real profiles from local filesystem only")
    except Exception:
        logger.exception("Supabase check failed (non-fatal)")

    logger.info("\n>>> PHASE 4: GMM CLASSIFIER <<<")
    try:
        from classifier.train import train_gmm, build_hybrid_config
        metrics = train_gmm()
        logger.info("GMM training metrics: %s", json.dumps(metrics, indent=2))

        # Build hybrid config (compares GMM vs heuristic per-archetype)
        hybrid = build_hybrid_config()
        logger.info("Hybrid config built:")
        logger.info("  GMM preferred for: %s", hybrid["gmm_preferred_archetypes"])
        for arch, comp in hybrid["per_archetype_comparison"].items():
            logger.info("  %-18s GMM=%.4f  Heur=%.4f  -> %s",
                         arch, comp["gmm_corr"], comp["heuristic_corr"], comp["winner"])
        logger.info("  Heuristic overall: %.4f corr | GMM overall: %.4f corr",
                     hybrid["heuristic_overall"]["avg_corr"],
                     hybrid["gmm_overall"]["avg_corr"])
    except Exception:
        logger.exception("GMM training/validation failed (non-fatal)")

    logger.info("\n>>> PHASE 5: NARRATIVE PRE-GENERATION <<<")
    try:
        _pregenerate_narratives()
    except Exception:
        logger.exception("Narrative pre-generation failed (non-fatal)")

    # Signal to the API server that data is ready (file-based flag)
    flag = DATA_DIR / ".pipeline_complete"
    flag.touch()
    logger.info("Pipeline complete — wrote %s", flag)


def _pregenerate_narratives() -> None:
    """Pre-generate narratives for a diverse sample of traders."""
    from classifier.cluster import classify, load_model
    from narrative.generator import generate_narrative

    if not load_model():
        logger.warning("GMM model not available; skipping narrative pre-generation")
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")

    extracted_dir = DATA_DIR / "extracted"
    gt_dir = DATA_DIR / "ground_truth"
    narrative_dir = DATA_DIR / "narratives"
    narrative_dir.mkdir(parents=True, exist_ok=True)

    # Pick diverse sample: one per archetype if possible, plus special cases
    gt_files = sorted(gt_dir.glob("*.json"))
    archetype_picks: dict[str, str] = {}
    pdt_picks: list[str] = []
    intl_picks: list[str] = []
    high_nw_picks: list[str] = []

    us_jurisdictions = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
        "DC",
    }

    for gf in gt_files:
        with open(gf) as f:
            gt = json.load(f)
        weights = gt.get("archetype_weights", {})
        if not weights:
            continue
        dominant = max(weights, key=weights.get)  # type: ignore[arg-type]
        if dominant not in archetype_picks:
            archetype_picks[dominant] = gf.stem

        # Track PDT-constrained traders
        if gt.get("pdt_constrained") and len(pdt_picks) < 2:
            pdt_picks.append(gf.stem)

        # Track international (non-US) traders
        jurisdiction = gt.get("tax_jurisdiction", "")
        if jurisdiction and jurisdiction not in us_jurisdictions and len(intl_picks) < 2:
            intl_picks.append(gf.stem)

        # Track high portfolio_pct_of_net_worth
        nw_pct = gt.get("portfolio_pct_of_net_worth", 0)
        if nw_pct and nw_pct > 80 and len(high_nw_picks) < 2:
            high_nw_picks.append(gf.stem)

    # Combine all picks (dedup)
    sample_ids = list(archetype_picks.values())
    for tid in pdt_picks + intl_picks + high_nw_picks:
        if tid not in sample_ids:
            sample_ids.append(tid)

    logger.info("Pre-generating narratives for %d traders: %s",
                len(sample_ids), sample_ids)

    for tid in sample_ids:
        ext_path = extracted_dir / f"{tid}.json"
        if not ext_path.exists():
            continue

        with open(ext_path) as f:
            profile = json.load(f)

        classification = classify(profile)
        narrative = generate_narrative(profile, classification, api_key=api_key)

        out_path = narrative_dir / f"{tid}.json"
        with open(out_path, "w") as f:
            json.dump(narrative, f, indent=2)

        logger.info("  %s: %s (generated by %s)",
                     tid,
                     narrative.get("headline", "N/A")[:60],
                     narrative.get("_generated_by", "claude"))


if __name__ == "__main__":
    main()
