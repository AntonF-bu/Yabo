#!/bin/bash
set -e

echo "=== Running full pipeline ==="
python run_all.py

echo "=== Starting API server ==="
exec uvicorn api:app --host 0.0.0.0 --port "${PORT:-8000}"
