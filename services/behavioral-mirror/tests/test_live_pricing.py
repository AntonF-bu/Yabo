"""Test: HoldingsExtractor live pricing integration.

Verifies that _position_value() uses live market prices for equity/ETF
positions and falls back to stored values when live prices are unavailable.

Run:
  python -m tests.test_live_pricing              # mock data only
  SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python -m tests.test_live_pricing DS299  # real data
"""

from __future__ import annotations

import sys
import os

# ── Make features/ importable ────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from features.holdings_extractor import (
    HoldingsExtractor,
    _try_get_live_price,
    _live_price_session_cache,
    _safe_float,
)


# ── Mock holdings resembling a real portfolio ────────────────────────

MOCK_HOLDINGS = [
    {
        "profile_id": "TEST",
        "account_id": "Individual",
        "ticker": "NVDA",
        "quantity": 150,
        "current_value": 18750.00,   # stale: $125/share
        "cost_basis": 12000.00,
        "instrument_type": "equity",
    },
    {
        "profile_id": "TEST",
        "account_id": "Individual",
        "ticker": "AAPL",
        "quantity": 100,
        "current_value": 17500.00,   # stale: $175/share
        "cost_basis": 15000.00,
        "instrument_type": "equity",
    },
    {
        "profile_id": "TEST",
        "account_id": "Individual",
        "ticker": "VOO",
        "quantity": 50,
        "current_value": 22000.00,   # stale: $440/share
        "cost_basis": 20000.00,
        "instrument_type": "etf",
    },
    {
        "profile_id": "TEST",
        "account_id": "IRA",
        "ticker": "MSFT",
        "quantity": 80,
        "current_value": 30400.00,   # stale: $380/share
        "cost_basis": 28000.00,
        "instrument_type": "equity",
    },
    {
        "profile_id": "TEST",
        "account_id": "Individual",
        "ticker": "NVDA",
        "quantity": -2,
        "current_value": None,
        "cost_basis": 1200.00,
        "instrument_type": "options",
        "instrument_details": {
            "option_type": "call",
            "underlying": "NVDA",
            "strike": 140,
            "expiry": "2025-06-20",
        },
    },
]


def test_position_value_with_mock_prices():
    """Test that _position_value uses live prices when available."""
    print("\n" + "=" * 70)
    print("TEST: _position_value() live vs stored pricing")
    print("=" * 70)

    # Phase 1: Without live prices (baseline — same as old behavior)
    _live_price_session_cache.clear()
    hx = HoldingsExtractor(supabase_client=None)
    hx._price_sources.clear()

    print("\n── Phase 1: STORED pricing (baseline) ──")
    stored_total = 0.0
    for h in MOCK_HOLDINGS:
        val = hx._position_value(h)
        stored_total += val
        ticker = h.get("ticker", "?")
        itype = h.get("instrument_type", "?")
        source = hx._price_sources.get(ticker, "none")
        print(f"  {ticker:6s} ({itype:7s}) qty={h.get('quantity'):>6}  →  ${val:>12,.2f}  source={source}")

    print(f"\n  TOTAL (stored): ${stored_total:,.2f}")

    # Phase 2: Inject simulated live prices into session cache
    _live_price_session_cache.clear()
    hx2 = HoldingsExtractor(supabase_client=None)
    hx2._price_sources.clear()

    # Simulated "current" prices (different from stale stored values)
    simulated_live = {
        "NVDA": 142.50,   # was $125 stored
        "AAPL": 195.20,   # was $175 stored
        "VOO": 465.80,    # was $440 stored
        "MSFT": 412.30,   # was $380 stored
    }
    for sym, price in simulated_live.items():
        _live_price_session_cache[sym] = price

    print("\n── Phase 2: LIVE pricing (simulated) ──")
    live_total = 0.0
    for h in MOCK_HOLDINGS:
        val = hx2._position_value(h)
        live_total += val
        ticker = h.get("ticker", "?")
        itype = h.get("instrument_type", "?")
        source = hx2._price_sources.get(ticker, "none")
        print(f"  {ticker:6s} ({itype:7s}) qty={h.get('quantity'):>6}  →  ${val:>12,.2f}  source={source}")

    print(f"\n  TOTAL (live):   ${live_total:,.2f}")
    diff = live_total - stored_total
    diff_pct = (diff / stored_total * 100) if stored_total > 0 else 0
    print(f"  DELTA:          ${diff:>+,.2f} ({diff_pct:+.1f}%)")

    # Phase 3: Verify price source tracking
    print("\n── Phase 3: Price source tracking ──")
    print(f"  Price sources: {dict(hx2._price_sources)}")
    live_count = sum(1 for s in hx2._price_sources.values() if s == "live")
    stored_count = sum(1 for s in hx2._price_sources.values() if s in ("stored", "cost_basis"))
    print(f"  Live: {live_count}, Stored: {stored_count}")

    # Assertions
    assert live_count == 4, f"Expected 4 live prices, got {live_count}"
    assert hx2._price_sources.get("NVDA") == "live", "NVDA should use live"
    assert diff > 0, "Live prices should be higher than stale stored values"
    # Options should NOT get live pricing (uses cost_basis fallback)
    # NVDA appears in both equity (live) and options (cost_basis) — equity wins via setdefault
    print("\n  ✓ All assertions passed")


def test_try_get_live_price():
    """Test _try_get_live_price with actual yfinance (if available)."""
    print("\n" + "=" * 70)
    print("TEST: _try_get_live_price() — real yfinance fetch")
    print("=" * 70)

    _live_price_session_cache.clear()
    test_symbols = ["AAPL", "NVDA", "VOO", "MSFT", "FAKEXYZ123"]

    for sym in test_symbols:
        price = _try_get_live_price(sym)
        if price is not None:
            print(f"  {sym:12s} → ${price:>10,.2f}  ✓ live")
        else:
            print(f"  {sym:12s} → None         (fallback to stored)")

    cached = sum(1 for v in _live_price_session_cache.values() if v is not None)
    print(f"\n  Session cache: {cached} live prices cached")


def test_with_supabase(profile_id: str):
    """Test with real holdings data from Supabase."""
    print("\n" + "=" * 70)
    print(f"TEST: Real Supabase data for {profile_id}")
    print("=" * 70)

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        # Try Next.js env vars
        url = url or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
        key = key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")

    if not url or not key:
        print("  ⚠ No SUPABASE_URL / SUPABASE_SERVICE_KEY set — skipping")
        return

    from supabase import create_client
    client = create_client(url, key)

    # Fetch holdings
    resp = client.table("holdings").select("*").eq("profile_id", profile_id).execute()
    holdings = resp.data or []
    print(f"  Found {len(holdings)} holdings rows")

    if not holdings:
        print("  ⚠ No holdings data — nothing to test")
        return

    # Show ticker breakdown
    tickers = {}
    for h in holdings:
        t = h.get("ticker", "?")
        itype = (h.get("instrument_type") or "equity").lower()
        cv = h.get("current_value")
        cb = h.get("cost_basis")
        qty = h.get("quantity")
        tickers[t] = {"type": itype, "qty": qty, "current_value": cv, "cost_basis": cb}

    print(f"  Unique tickers: {len(tickers)}")
    print(f"\n  {'Ticker':<10} {'Type':<10} {'Qty':>8} {'CV':>12} {'CB':>12}")
    print(f"  {'─' * 52}")
    for t, info in sorted(tickers.items()):
        cv_str = f"${info['current_value']:,.2f}" if info['current_value'] else "—"
        cb_str = f"${info['cost_basis']:,.2f}" if info['cost_basis'] else "—"
        print(f"  {t:<10} {info['type']:<10} {info['qty'] or 0:>8} {cv_str:>12} {cb_str:>12}")

    # Run HoldingsExtractor
    _live_price_session_cache.clear()
    hx = HoldingsExtractor(supabase_client=client)
    features = hx.extract(profile_id)

    if features:
        print(f"\n  ── Extracted features ──")
        print(f"  h_total_value:              ${features.get('h_total_value', 0):>12,.2f}")
        print(f"  h_stress_test_20pct:        ${features.get('h_stress_test_20pct', 0):>12,.2f}")
        print(f"  h_max_single_position_loss: ${features.get('h_max_single_position_loss', 0):>12,.2f}")
        print(f"  h_top1_pct:                 {features.get('h_top1_pct', 0):>10.2%}")
        print(f"  h_top3_pct:                 {features.get('h_top3_pct', 0):>10.2%}")
        print(f"\n  ── Price source metadata ──")
        print(f"  _meta_live_price_count:   {features.get('_meta_live_price_count', 0)}")
        print(f"  _meta_stored_price_count: {features.get('_meta_stored_price_count', 0)}")
        sources = features.get("_meta_price_sources", {})
        for ticker, source in sorted(sources.items()):
            print(f"    {ticker:<10} → {source}")

    # Compare: what would old behavior produce?
    print(f"\n  ── Old vs New comparison ──")
    _live_price_session_cache.clear()

    # Force all lookups to return None (simulating no live pricing)
    import unittest.mock
    with unittest.mock.patch("features.holdings_extractor._try_get_live_price", return_value=None):
        hx_old = HoldingsExtractor(supabase_client=client)
        old_features = hx_old.extract(profile_id)

    if old_features and features:
        old_val = old_features.get("h_total_value", 0) or 0
        new_val = features.get("h_total_value", 0) or 0
        delta = new_val - old_val
        pct = (delta / old_val * 100) if old_val > 0 else 0
        print(f"  h_total_value (old/stored): ${old_val:>12,.2f}")
        print(f"  h_total_value (new/live):   ${new_val:>12,.2f}")
        print(f"  DELTA:                      ${delta:>+12,.2f} ({pct:+.1f}%)")


if __name__ == "__main__":
    # Always run mock tests
    test_position_value_with_mock_prices()
    test_try_get_live_price()

    # If a profile ID is given, test with real Supabase data
    if len(sys.argv) > 1:
        test_with_supabase(sys.argv[1])
    else:
        print("\n─────────────────────────────────────────")
        print("Tip: pass a profile ID to test with real data:")
        print("  SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python -m tests.test_live_pricing DS299")

    print("\n✓ Done")
