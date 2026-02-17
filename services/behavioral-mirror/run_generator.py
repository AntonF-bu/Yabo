"""Run the synthetic trader generator: download data, generate profiles, simulate trades."""

import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from generator.market_data import download_and_cache
from generator.profiles import generate_profiles, save_profiles
from generator.simulate import simulate_trader, save_trades, save_ground_truth, save_manifest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("=== STEP 1: Download & cache market data ===")
    market_data = download_and_cache()
    logger.info("Market data: %d rows, %d columns", len(market_data), len(market_data.columns))

    logger.info("=== STEP 2: Generate trader profiles ===")
    profiles = generate_profiles()
    save_profiles(profiles)
    logger.info("Generated %d profiles", len(profiles))

    logger.info("=== STEP 3: Simulate trades ===")
    total_trades = 0
    for i, profile in enumerate(profiles):
        trades, ground_truth = simulate_trader(profile, market_data)
        save_trades(profile["trader_id"], trades)
        save_ground_truth(profile["trader_id"], ground_truth)
        total_trades += len(trades)
        if (i + 1) % 10 == 0:
            logger.info("  Simulated %d/%d traders (%d trades so far)",
                        i + 1, len(profiles), total_trades)

    save_manifest(profiles)

    logger.info("=== GENERATOR COMPLETE ===")
    logger.info("  Traders: %d", len(profiles))
    logger.info("  Total trades: %d", total_trades)
    logger.info("  Date range: %s to %s",
                market_data.index[0].strftime("%Y-%m-%d"),
                market_data.index[-1].strftime("%Y-%m-%d"))


if __name__ == "__main__":
    main()
