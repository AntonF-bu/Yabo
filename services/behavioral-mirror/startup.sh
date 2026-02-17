#!/bin/bash
set -e

echo "=== Starting API server ==="
uvicorn api:app --host 0.0.0.0 --port "${PORT:-8000}" &
UVICORN_PID=$!

sleep 3
echo "=== Server started (PID $UVICORN_PID), running pipeline ==="
python run_all.py || echo "WARNING: Pipeline failed (non-fatal)"

echo "=== Pipeline complete, waiting on server ==="
wait $UVICORN_PID
