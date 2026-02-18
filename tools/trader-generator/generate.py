#!/usr/bin/env python3
"""
CLI entry point for the synthetic trader generator.

Usage:
  python generate.py --count 10 --output ./output          # test batch
  python generate.py --count 500 --output ./output          # full run
  python generate.py --count 1 --output ./output --verbose  # debug single trader
"""

import argparse
import os
import sys
import time

from personalities import generate_traders, get_all_tickers
from market_data import download_market_data
from simulator import simulate_trader
from outputter import write_trader_csv, write_answer_key, write_summary


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic trader CSV files in Trading212 format."
    )
    parser.add_argument(
        "--count", type=int, default=10,
        help="Number of traders to generate (default: 10)",
    )
    parser.add_argument(
        "--output", type=str, default="./output",
        help="Output directory (default: ./output)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print detailed personality + decision log for each trader",
    )
    parser.add_argument(
        "--min-trades", type=int, default=15,
        help="Skip traders who generated fewer than N trades (default: 15)",
    )
    args = parser.parse_args()

    # Write status file for server.py to read
    status_file = os.path.join(args.output, ".status")
    os.makedirs(args.output, exist_ok=True)
    _write_status(status_file, "running")

    try:
        _run(args, status_file)
    except Exception as e:
        _write_status(status_file, f"failed: {e}")
        raise


def _write_status(path: str, status: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(status)


def _run(args, status_file: str):
    t0 = time.time()

    # --- Step 1: Generate personalities ---
    print(f"[1/4] Generating {args.count} trader personalities (seed={args.seed})...")
    traders = generate_traders(args.count, seed=args.seed)
    print(f"  Generated {len(traders)} traders")

    if args.verbose and len(traders) <= 3:
        for t in traders:
            _print_personality(t)

    # --- Step 2: Download market data ---
    print("[2/4] Downloading market data...")
    all_tickers = get_all_tickers(traders)
    print(f"  Ticker universe: {len(all_tickers)} symbols")
    market_data = download_market_data(all_tickers, verbose=args.verbose)

    # --- Step 3: Simulate trading ---
    print(f"[3/4] Simulating trading for {len(traders)} traders...")
    csv_dir = os.path.join(args.output, "csvs")
    key_dir = os.path.join(args.output, "answer_key")
    os.makedirs(csv_dir, exist_ok=True)
    os.makedirs(key_dir, exist_ok=True)

    all_trades = {}
    kept_traders = []
    skipped = 0

    for i, trader in enumerate(traders):
        tid = trader["trader_id"]
        if args.verbose:
            print(f"\n--- Trader {tid}/{len(traders)} ---")

        trades = simulate_trader(trader, market_data, seed=args.seed,
                                 verbose=args.verbose)

        if len(trades) < args.min_trades:
            skipped += 1
            if args.verbose:
                print(f"  SKIPPED: only {len(trades)} trades "
                      f"(min={args.min_trades})")
            continue

        all_trades[tid] = trades
        kept_traders.append(trader)

        # Write CSV immediately
        csv_path = os.path.join(csv_dir, f"trader_{tid:03d}.csv")
        write_trader_csv(trades, csv_path)

        if not args.verbose:
            # Progress bar
            pct = (i + 1) / len(traders) * 100
            bar_len = 40
            filled = int(bar_len * (i + 1) / len(traders))
            bar = "=" * filled + "-" * (bar_len - filled)
            print(f"\r  [{bar}] {pct:5.1f}% ({i+1}/{len(traders)}) "
                  f"trades={len(trades):>4}", end="", flush=True)

    if not args.verbose:
        print()  # newline after progress bar

    if skipped:
        print(f"  Skipped {skipped} traders with <{args.min_trades} trades")
    print(f"  Kept {len(kept_traders)} traders")

    # --- Step 4: Write answer key + summary ---
    print("[4/4] Writing answer key and summary...")
    write_answer_key(kept_traders, os.path.join(key_dir, "personalities.json"))
    write_summary(kept_traders, all_trades, args.output)

    elapsed = time.time() - t0
    total_trades = sum(len(t) for t in all_trades.values())
    print(f"\nDone! {len(kept_traders)} traders, {total_trades} total trades "
          f"in {elapsed:.1f}s")
    print(f"Output: {os.path.abspath(args.output)}")

    _write_status(status_file, "complete")


def _print_personality(t):
    """Pretty-print a trader personality for --verbose mode."""
    print(f"\n  Trader #{t['trader_id']}")
    print(f"    Age: {t['age']} | Sector: {t['job_sector']} | "
          f"Exp: {t['experience_years']}yr")
    print(f"    Account: ${t['account_size']:,.2f} | "
          f"Time: {t['time_availability']} | "
          f"Source: {t['discovery_source']}")
    print(f"    Patience={t['patience']:.2f}  Risk={t['risk_appetite']:.2f}  "
          f"Conviction={t['conviction']:.2f}  LossAversion={t['loss_aversion']:.2f}")
    print(f"    FOMO={t['fomo_susceptibility']:.2f}  "
          f"Discipline={t['discipline']:.2f}  "
          f"Overconf={t['overconfidence_after_wins']:.2f}  "
          f"Revenge={t['revenge_trade_tendency']:.2f}")
    print(f"    Watchlist: {t['core_watchlist']}")
    print(f"    Options: calls={t['instrument_comfort']['options_calls']:.2f} "
          f"puts={t['instrument_comfort']['options_puts']:.2f}")
    print(f"    Life events: {len(t['life_events'])}")


if __name__ == "__main__":
    main()
