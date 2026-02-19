"""Tests for the parsing intelligence layer.

Run from repo root:
    python -m pytest services/behavioral-mirror/tests/test_parsing.py -v

Or directly:
    python services/behavioral-mirror/tests/test_parsing.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure imports resolve
_SERVICE_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _SERVICE_DIR.parent.parent
for p in (_SERVICE_DIR, _REPO_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


# ── Test 1: Package imports without errors ─────────────────────────────────

def test_import_package():
    """parsing package imports cleanly."""
    from parsing import compute_hash, lookup, store, get_memory_stats, score_confidence
    assert callable(compute_hash)
    assert callable(lookup)
    assert callable(store)
    assert callable(get_memory_stats)
    assert callable(score_confidence)


# ── Test 2: compute_hash consistency ───────────────────────────────────────

def test_hash_same_structure_different_tickers():
    """Same-structure transactions with different tickers produce same hash."""
    from parsing.pattern_memory import compute_hash

    h1 = asyncio.get_event_loop().run_until_complete(
        compute_hash("SOLD 5 APP MAY 16 2026 870 CALL @12.50", "wells_fargo")
    )
    h2 = asyncio.get_event_loop().run_until_complete(
        compute_hash("SOLD 10 TSLA JUN 20 2026 450 CALL @8.30", "wells_fargo")
    )
    assert h1 == h2, f"Hashes differ: {h1} vs {h2}"


def test_hash_same_structure_different_dates():
    """Same structure with different dates produces same hash."""
    from parsing.pattern_memory import compute_hash

    h1 = asyncio.get_event_loop().run_until_complete(
        compute_hash("BOUGHT 100 AAPL @150.25 on 01/15/2026", "wells_fargo")
    )
    h2 = asyncio.get_event_loop().run_until_complete(
        compute_hash("BOUGHT 200 MSFT @310.50 on 03/22/2026", "wells_fargo")
    )
    assert h1 == h2, f"Hashes differ: {h1} vs {h2}"


def test_hash_different_structure():
    """Structurally different transactions produce different hashes."""
    from parsing.pattern_memory import compute_hash

    h1 = asyncio.get_event_loop().run_until_complete(
        compute_hash("SOLD 5 APP MAY 16 2026 870 CALL @12.50", "wells_fargo")
    )
    h2 = asyncio.get_event_loop().run_until_complete(
        compute_hash("DIVIDEND REINVEST AAPL 15 shares @145.00", "wells_fargo")
    )
    assert h1 != h2, "Different structures should produce different hashes"


def test_hash_different_brokerage():
    """Same text with different brokerage produces different hash."""
    from parsing.pattern_memory import compute_hash

    h1 = asyncio.get_event_loop().run_until_complete(
        compute_hash("SOLD 5 APP MAY 16 2026 870 CALL", "wells_fargo")
    )
    h2 = asyncio.get_event_loop().run_until_complete(
        compute_hash("SOLD 5 APP MAY 16 2026 870 CALL", "schwab")
    )
    assert h1 != h2, "Different brokerages should produce different hashes"


def test_hash_deterministic():
    """Same input always produces the same hash."""
    from parsing.pattern_memory import compute_hash

    text = "BOUGHT 100 AAPL @150.25"
    h1 = asyncio.get_event_loop().run_until_complete(compute_hash(text, "wfa"))
    h2 = asyncio.get_event_loop().run_until_complete(compute_hash(text, "wfa"))
    assert h1 == h2


# ── Test 3: Normalization internals ────────────────────────────────────────

def test_normalize_strips_amounts():
    """Dollar amounts and quantities are replaced."""
    from parsing.pattern_memory import _normalize

    result = _normalize("SOLD 5 APP MAY 16 2026 870 CALL @12.50")
    assert "$" not in result
    assert "12.50" not in result
    assert "870" not in result


def test_normalize_replaces_tickers():
    """Ticker symbols become TICKER."""
    from parsing.pattern_memory import _normalize

    result = _normalize("SOLD APP CALL")
    assert "TICKER" in result
    assert "APP" not in result


def test_normalize_preserves_keywords():
    """Action verbs and instrument words survive normalization."""
    from parsing.pattern_memory import _normalize

    result = _normalize("SOLD 5 APP MAY 16 2026 870 CALL")
    assert "SOLD" in result
    assert "CALL" in result


# ── Test 4: score_confidence ───────────────────────────────────────────────

def test_confidence_simple_equity_buy():
    """Simple equity buy with complete data → high confidence."""
    from parsing.confidence import score_confidence

    txn = {
        "action": "buy",
        "instrument_type": "equity",
        "symbol": "AAPL",
        "quantity": 100,
        "price": 150.0,
        "amount": 15000.0,
        "description": "BOUGHT 100 AAPL @150.00",
    }
    score = score_confidence(txn, "BOUGHT 100 AAPL @150.00")
    assert score >= 0.95, f"Simple equity buy should be high confidence, got {score}"


def test_confidence_dividend():
    """Dividend payments → high confidence."""
    from parsing.confidence import score_confidence

    txn = {
        "action": "dividend",
        "instrument_type": "equity",
        "symbol": "AAPL",
        "quantity": 0,
        "price": 0,
        "amount": 125.0,
        "description": "DIVIDEND AAPL",
    }
    score = score_confidence(txn, "DIVIDEND AAPL $125.00")
    assert score >= 0.90, f"Dividend should be high confidence, got {score}"


def test_confidence_option_medium():
    """Option transactions → medium confidence."""
    from parsing.confidence import score_confidence

    txn = {
        "action": "sell",
        "instrument_type": "options",
        "symbol": "APP260516C870",
        "quantity": 5,
        "price": 12.50,
        "amount": 6250.0,
        "description": "SOLD 5 APP MAY 16 2026 870 CALL",
    }
    score = score_confidence(txn, "SOLD 5 APP MAY 16 2026 870 CALL @12.50")
    assert 0.50 <= score <= 0.90, f"Option sell should be medium confidence, got {score}"


def test_confidence_unknown_instrument():
    """Unknown instrument type → low confidence."""
    from parsing.confidence import score_confidence

    txn = {
        "action": "other",
        "instrument_type": "unknown",
        "symbol": "",
        "quantity": 0,
        "price": 0,
        "amount": 500.0,
        "description": "MISCELLANEOUS ADJUSTMENT",
    }
    score = score_confidence(txn, "MISCELLANEOUS ADJUSTMENT $500")
    assert score <= 0.50, f"Unknown instrument should be low confidence, got {score}"


def test_confidence_corporate_action_low():
    """Corporate actions → low confidence."""
    from parsing.confidence import score_confidence

    txn = {
        "action": "other",
        "instrument_type": "equity",
        "symbol": "XYZ",
        "quantity": 50,
        "price": 0,
        "amount": 0,
        "description": "MANDATORY SPINOFF XYZ INTO ABC",
    }
    score = score_confidence(txn, "MANDATORY SPINOFF XYZ INTO ABC 50 SHARES")
    assert score <= 0.55, f"Corporate action should be low confidence, got {score}"


def test_confidence_memory_boost():
    """Memory corroboration boosts score to >= 0.95."""
    from parsing.confidence import score_confidence

    txn = {
        "action": "sell",
        "instrument_type": "options",
        "symbol": "APP260516C870",
        "quantity": 5,
        "price": 12.50,
        "amount": 6250.0,
        "description": "SOLD 5 APP MAY 16 2026 870 CALL",
    }
    score = score_confidence(
        txn, "SOLD 5 APP MAY 16 2026 870 CALL @12.50",
        memory_confidence=0.92,
    )
    assert score >= 0.95, f"Memory-boosted score should be >= 0.95, got {score}"


def test_confidence_sell_with_position_context():
    """Sell with known long position → higher confidence than without."""
    from parsing.confidence import score_confidence

    txn = {
        "action": "sell",
        "instrument_type": "equity",
        "symbol": "AAPL",
        "quantity": 50,
        "price": 160.0,
        "amount": 8000.0,
        "description": "SOLD 50 AAPL @160.00",
    }
    raw = "SOLD 50 AAPL @160.00"

    score_no_ctx = score_confidence(txn, raw)
    score_with_ctx = score_confidence(txn, raw, account_positions={"AAPL": 100})
    assert score_with_ctx >= score_no_ctx, (
        f"Position context should not decrease confidence: "
        f"no_ctx={score_no_ctx}, with_ctx={score_with_ctx}"
    )


# ── Test 5: store / lookup round-trip (mocked Supabase) ───────────────────

def test_store_and_lookup_roundtrip(monkeypatch):
    """store() then lookup() returns the stored classification.

    Uses an in-memory mock instead of a real Supabase connection.
    """
    from parsing import pattern_memory

    # In-memory store
    _store: dict[str, dict] = {}

    class MockResponse:
        def __init__(self, data):
            self.data = data

    class MockTable:
        def __init__(self, name):
            self.name = name
            self._filters = {}
            self._limit = None

        def select(self, cols):
            return self

        def eq(self, col, val):
            self._filters[col] = val
            return self

        def limit(self, n):
            self._limit = n
            return self

        def execute(self):
            # Lookup path
            ph = self._filters.get("pattern_hash")
            bk = self._filters.get("brokerage")
            key = f"{ph}|{bk}"
            if key in _store:
                return MockResponse([_store[key]])
            return MockResponse([])

        def insert(self, row):
            ph = row["pattern_hash"]
            bk = row["brokerage"]
            key = f"{ph}|{bk}"
            row["id"] = key
            row["times_matched"] = 1
            _store[key] = row
            return self

        def update(self, data):
            self._update_data = data
            return self

    class MockClient:
        def table(self, name):
            return MockTable(name)

    monkeypatch.setattr(pattern_memory, "_get_supabase", lambda: MockClient())

    loop = asyncio.get_event_loop()

    classification = {
        "instrument_type": "option",
        "action": "sell_to_open",
        "strategy": "covered_call",
        "underlying": "APP",
    }

    # Store
    loop.run_until_complete(pattern_memory.store(
        pattern_hash="abc123",
        raw_text="SOLD 5 APP CALL",
        brokerage="wells_fargo",
        classification=classification,
        confidence=0.92,
        source="parser",
    ))

    # Lookup
    result = loop.run_until_complete(pattern_memory.lookup(
        pattern_hash="abc123",
        brokerage="wells_fargo",
        min_confidence=0.85,
    ))

    assert result is not None, "Lookup should find the stored pattern"
    assert result["instrument_type"] == "option"
    assert result["strategy"] == "covered_call"


def test_lookup_returns_none_low_confidence(monkeypatch):
    """lookup() returns None when stored confidence is below threshold."""
    from parsing import pattern_memory

    _store: dict[str, dict] = {}

    class MockResponse:
        def __init__(self, data):
            self.data = data

    class MockTable:
        def __init__(self, name):
            self._filters = {}

        def select(self, cols):
            return self

        def eq(self, col, val):
            self._filters[col] = val
            return self

        def limit(self, n):
            return self

        def execute(self):
            ph = self._filters.get("pattern_hash")
            bk = self._filters.get("brokerage")
            key = f"{ph}|{bk}"
            if key in _store:
                return MockResponse([_store[key]])
            return MockResponse([])

        def insert(self, row):
            key = f"{row['pattern_hash']}|{row['brokerage']}"
            row["id"] = key
            row["times_matched"] = 1
            _store[key] = row
            return self

        def update(self, data):
            return self

    class MockClient:
        def table(self, name):
            return MockTable(name)

    monkeypatch.setattr(pattern_memory, "_get_supabase", lambda: MockClient())

    loop = asyncio.get_event_loop()

    # Store with low confidence
    loop.run_until_complete(pattern_memory.store(
        pattern_hash="low123",
        raw_text="SOMETHING WEIRD",
        brokerage="schwab",
        classification={"instrument_type": "unknown"},
        confidence=0.50,
        source="parser",
    ))

    result = loop.run_until_complete(pattern_memory.lookup(
        pattern_hash="low123",
        brokerage="schwab",
        min_confidence=0.85,
    ))

    assert result is None, "Should return None for low-confidence patterns"


# ── Runner ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Parsing Intelligence Layer — Test Suite")
    print("=" * 60)

    passed = 0
    failed = 0
    tests = [
        ("Import package", test_import_package),
        ("Hash: same structure, different tickers", test_hash_same_structure_different_tickers),
        ("Hash: same structure, different dates", test_hash_same_structure_different_dates),
        ("Hash: different structures differ", test_hash_different_structure),
        ("Hash: different brokerage differs", test_hash_different_brokerage),
        ("Hash: deterministic", test_hash_deterministic),
        ("Normalize: strips amounts", test_normalize_strips_amounts),
        ("Normalize: replaces tickers", test_normalize_replaces_tickers),
        ("Normalize: preserves keywords", test_normalize_preserves_keywords),
        ("Confidence: simple equity buy (high)", test_confidence_simple_equity_buy),
        ("Confidence: dividend (high)", test_confidence_dividend),
        ("Confidence: option (medium)", test_confidence_option_medium),
        ("Confidence: unknown (low)", test_confidence_unknown_instrument),
        ("Confidence: corporate action (low)", test_confidence_corporate_action_low),
        ("Confidence: memory boost", test_confidence_memory_boost),
        ("Confidence: sell with position context", test_confidence_sell_with_position_context),
    ]

    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {name}: {e}")
            failed += 1

    print()
    print(f"  {passed} passed, {failed} failed out of {len(tests)}")
    print("  (store/lookup round-trip tests require pytest with monkeypatch)")
    print("=" * 60)
    sys.exit(1 if failed else 0)
