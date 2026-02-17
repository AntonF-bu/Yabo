"""Run the feature extractor on all synthetic trader CSVs."""

import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from extractor.pipeline import extract_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"


def main() -> None:
    trades_dir = DATA_DIR / "trades"
    output_dir = DATA_DIR / "extracted"

    # Build context map from trader_profiles.json
    profiles_path = DATA_DIR / "trader_profiles.json"
    context_map: dict[str, dict] = {}

    if profiles_path.exists():
        with open(profiles_path) as f:
            profiles = json.load(f)
        for p in profiles:
            tid = p["trader_id"]
            context_map[tid] = {
                "tax_jurisdiction": p.get("tax_jurisdiction"),
                "account_size": p.get("account_size"),
                "portfolio_pct_of_net_worth": p.get("portfolio_pct_of_net_worth"),
                "brokerage_platform": p.get("brokerage_platform"),
                "options_approval_level": p.get("options_approval_level"),
            }
        logger.info("Loaded context for %d traders", len(context_map))
    else:
        logger.warning("No trader_profiles.json found — extracting without context")

    logger.info("=== Running feature extraction ===")
    profiles_out = extract_all(
        trades_dir=trades_dir,
        output_dir=output_dir,
        context_map=context_map,
    )

    logger.info("=== EXTRACTOR COMPLETE ===")
    logger.info("  Profiles extracted: %d", len(profiles_out))

    if profiles_out:
        total_trades = sum(p.get("metadata", {}).get("total_trades", 0) for p in profiles_out)
        avg_confidence = sum(p.get("metadata", {}).get("confidence_score", 0) for p in profiles_out) / len(profiles_out)
        logger.info("  Total trades processed: %d", total_trades)
        logger.info("  Average confidence: %.1f", avg_confidence)


if __name__ == "__main__":
    main()
