"""Run the 212-feature engine + classifier_v2 on all synthetic trader CSVs."""

import json
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from features.coordinator import extract_all_features
from classifier_v2 import classify_v2, load_classifier_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"


def _sanitize(features: dict[str, Any]) -> dict[str, Any]:
    """Convert numpy types to JSON-safe Python types."""
    sanitized: dict[str, Any] = {}
    for k, v in features.items():
        if isinstance(v, (np.integer,)):
            sanitized[k] = int(v)
        elif isinstance(v, (np.floating,)):
            sanitized[k] = None if np.isnan(v) else float(v)
        elif isinstance(v, (np.bool_,)):
            sanitized[k] = bool(v)
        elif isinstance(v, np.ndarray):
            sanitized[k] = v.tolist()
        else:
            sanitized[k] = v
    return sanitized


def _read_trades_csv(csv_path: Path) -> pd.DataFrame:
    """Read a synthetic trader CSV into the canonical DataFrame format."""
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower() for c in df.columns]

    # Rename common variants
    renames = {}
    for col in df.columns:
        if col in ("symbol", "stock", "name"):
            renames[col] = "ticker"
        elif col in ("side", "type", "trade_type"):
            renames[col] = "action"
        elif col in ("shares", "qty", "amount_shares"):
            renames[col] = "quantity"
        elif col in ("cost", "trade_price", "fill_price"):
            renames[col] = "price"
        elif col in ("trade_date", "time", "datetime", "timestamp"):
            renames[col] = "date"
        elif col in ("commission", "fee"):
            renames[col] = "fees"
    if renames:
        df = df.rename(columns=renames)

    # Ensure required columns exist
    for req in ("ticker", "action", "quantity", "price", "date"):
        if req not in df.columns:
            raise ValueError(f"Missing required column: {req}")

    if "fees" not in df.columns:
        df["fees"] = 0.0

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["action"] = df["action"].astype(str).str.upper().str.strip()
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").abs().fillna(0)
    df["price"] = pd.to_numeric(df["price"], errors="coerce").abs().fillna(0)
    df["fees"] = pd.to_numeric(df["fees"], errors="coerce").abs().fillna(0)
    df = df[df["quantity"] > 0]
    df = df.sort_values("date").reset_index(drop=True)

    return df


def main() -> None:
    trades_dir = DATA_DIR / "trades"
    output_dir = DATA_DIR / "extracted"
    output_dir.mkdir(parents=True, exist_ok=True)

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

    # Pre-load classifier config once (Supabase or None)
    config = load_classifier_config()
    if config:
        logger.info("Classifier config loaded from Supabase")
    else:
        logger.info("Using hardcoded classifier weights (Supabase unavailable)")

    csv_files = sorted(trades_dir.glob("*.csv"))
    logger.info("=== Running 212-feature extraction on %d CSVs ===", len(csv_files))

    results: list[dict[str, Any]] = []
    for csv_path in csv_files:
        trader_id = csv_path.stem
        try:
            trades_df = _read_trades_csv(csv_path)
            if len(trades_df) < 2:
                logger.warning("  %s: only %d trades, skipping", trader_id, len(trades_df))
                continue

            # Extract 212 features
            features = extract_all_features(trades_df)
            features = _sanitize(features)

            # Classify via V2
            classification = classify_v2(features, config=config)

            # Build output (features + classification together)
            output = {
                "trader_id": trader_id,
                "features": features,
                "classification_v2": classification,
                "context": context_map.get(trader_id, {}),
                "metadata": {
                    "total_trades": len(trades_df),
                    "feature_count": len(features),
                    "primary_archetype": classification.get("primary_archetype"),
                    "archetype_confidence": classification.get("archetype_confidence"),
                },
            }
            results.append(output)

            out_path = output_dir / f"{trader_id}.json"
            with open(out_path, "w") as f:
                json.dump(output, f, indent=2, default=str)

            logger.info(
                "  %s: %d trades → %d features, archetype=%s (%.0f%%)",
                trader_id,
                len(trades_df),
                len(features),
                classification.get("primary_archetype", "?"),
                (classification.get("archetype_confidence", 0) or 0) * 100,
            )

        except Exception:
            logger.exception("Failed to extract %s", trader_id)

    logger.info("=== EXTRACTOR COMPLETE ===")
    logger.info("  Profiles extracted: %d / %d", len(results), len(csv_files))

    if results:
        total_trades = sum(r["metadata"]["total_trades"] for r in results)
        total_features = sum(r["metadata"]["feature_count"] for r in results)
        logger.info("  Total trades processed: %d", total_trades)
        logger.info("  Average features per profile: %d", total_features // len(results))


if __name__ == "__main__":
    main()
