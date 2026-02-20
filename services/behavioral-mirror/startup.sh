#!/bin/bash
set -e

echo "=== Starting API server ==="
uvicorn api:app --host 0.0.0.0 --port "${PORT:-8000}"
