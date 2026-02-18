# Synthetic Trader Generator

Standalone CLI tool that generates realistic Trading212-format CSV files
from synthetic trader personalities simulated against real market data.

**This is NOT part of the behavioral mirror service.** Zero imports from
`/services/behavioral-mirror/`. Fully standalone.

## Quick Start

```bash
pip install -r requirements.txt

# Test batch (10 traders)
python generate.py --count 10 --output ./output

# Full run (500 traders)
python generate.py --count 500 --output ./output

# Debug a single trader
python generate.py --count 1 --output ./output --verbose
```

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--count` | 10 | Number of traders to generate |
| `--output` | ./output | Output directory |
| `--seed` | 42 | Random seed for reproducibility |
| `--verbose` | off | Print per-trader decision logs |
| `--min-trades` | 15 | Skip traders with fewer trades |

## Output Structure

```
output/
  csvs/
    trader_001.csv      # Trading212 format
    trader_002.csv
    ...
  answer_key/
    personalities.json  # Full personality data (never fed to classifier)
  summary.txt           # Quick stats
```

## File Server (Railway)

After generation, a FastAPI server starts to browse/download CSVs:

| Endpoint | Description |
|----------|-------------|
| `GET /` | HTML listing of all CSVs with download links |
| `GET /csv/{filename}` | Download a specific CSV |
| `GET /summary` | View summary.txt |
| `GET /status` | Generation status: running, complete, failed |

## Docker

```bash
docker build -t trader-generator .
docker run -e TRADER_COUNT=10 -p 8000:8000 trader-generator
```

Environment variables: `TRADER_COUNT`, `MIN_TRADES`, `RANDOM_SEED`, `OUTPUT_DIR`.

## Architecture

- **personalities.py** — Generates unique trader personalities via structured
  randomization (behavioural sliders, life events, instrument comfort, watchlists)
- **market_data.py** — Downloads + caches daily OHLCV from yfinance (2023-06 to 2024-12)
- **simulator.py** — Steps through each trading day, applying personality-driven
  decisions with an emotional state machine
- **outputter.py** — Writes Trading212-format CSVs and answer key JSON
- **generate.py** — CLI entry point
- **server.py** — Minimal FastAPI file server for Railway deployment
