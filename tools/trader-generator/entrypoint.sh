#!/bin/bash
set -e

echo "=== Trader Generator ==="
echo "Count: $TRADER_COUNT | Seed: $RANDOM_SEED | Min trades: $MIN_TRADES"
echo "Output: $OUTPUT_DIR"
echo ""

# Step 1: Generate CSVs
python generate.py \
  --count "$TRADER_COUNT" \
  --seed "$RANDOM_SEED" \
  --min-trades "$MIN_TRADES" \
  --output "$OUTPUT_DIR"

echo ""
echo "=== Starting file server on port $PORT ==="

# Step 2: Serve the files
exec uvicorn server:app --host 0.0.0.0 --port "$PORT"
