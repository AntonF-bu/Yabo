"""Run the full pipeline: generate -> extract -> validate."""

import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("=" * 60)
    logger.info("  BEHAVIORAL MIRROR — FULL PIPELINE")
    logger.info("=" * 60)

    logger.info("\n>>> PHASE 1: GENERATOR <<<")
    from run_generator import main as run_gen
    run_gen()

    logger.info("\n>>> PHASE 2: EXTRACTOR <<<")
    from run_extractor import main as run_ext
    run_ext()

    logger.info("\n>>> PHASE 3: VALIDATION <<<")
    from validate import run_validation, print_report
    report = run_validation()
    print_report(report)

    logger.info("Pipeline complete.")


if __name__ == "__main__":
    main()
