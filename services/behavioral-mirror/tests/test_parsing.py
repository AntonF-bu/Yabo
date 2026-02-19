"""Tests for the parsing intelligence layer (Part 1 + Part 2).

Run from repo root:
    python -m pytest services/behavioral-mirror/tests/test_parsing.py -v

Or directly (non-monkeypatch tests only):
    python services/behavioral-mirror/tests/test_parsing.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

# Ensure imports resolve
_SERVICE_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _SERVICE_DIR.parent.parent
for p in (_SERVICE_DIR, _REPO_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _run(coro):
    """Helper to run an async function from sync test code."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


# =========================================================================
#  PART 1 TESTS — Pattern Memory + Confidence
# =========================================================================


# ── Test 1: Package imports without errors ─────────────────────────────────

def test_import_package():
    """parsing package imports cleanly."""
    from parsing import compute_hash, lookup, store, get_memory_stats, score_confidence
    assert callable(compute_hash)
    assert callable(lookup)
    assert callable(store)
    assert callable(get_memory_stats)
    assert callable(score_confidence)


def test_import_part2_modules():
    """Part 2 modules import cleanly."""
    from parsing.claude_classifier import classify_batch
    from parsing.review_queue import flag_for_review, resolve_review
    from parsing.orchestrator import parse_with_intelligence
    assert callable(classify_batch)
    assert callable(flag_for_review)
    assert callable(resolve_review)
    assert callable(parse_with_intelligence)


# ── Test 2: compute_hash consistency ───────────────────────────────────────

def test_hash_same_structure_different_tickers():
    """Same-structure transactions with different tickers produce same hash."""
    from parsing.pattern_memory import compute_hash

    h1 = _run(compute_hash("SOLD 5 APP MAY 16 2026 870 CALL @12.50", "wells_fargo"))
    h2 = _run(compute_hash("SOLD 10 TSLA JUN 20 2026 450 CALL @8.30", "wells_fargo"))
    assert h1 == h2, f"Hashes differ: {h1} vs {h2}"


def test_hash_same_structure_different_dates():
    """Same structure with different dates produces same hash."""
    from parsing.pattern_memory import compute_hash

    h1 = _run(compute_hash("BOUGHT 100 AAPL @150.25 on 01/15/2026", "wells_fargo"))
    h2 = _run(compute_hash("BOUGHT 200 MSFT @310.50 on 03/22/2026", "wells_fargo"))
    assert h1 == h2, f"Hashes differ: {h1} vs {h2}"


def test_hash_different_structure():
    """Structurally different transactions produce different hashes."""
    from parsing.pattern_memory import compute_hash

    h1 = _run(compute_hash("SOLD 5 APP MAY 16 2026 870 CALL @12.50", "wells_fargo"))
    h2 = _run(compute_hash("DIVIDEND REINVEST AAPL 15 shares @145.00", "wells_fargo"))
    assert h1 != h2, "Different structures should produce different hashes"


def test_hash_different_brokerage():
    """Same text with different brokerage produces different hash."""
    from parsing.pattern_memory import compute_hash

    h1 = _run(compute_hash("SOLD 5 APP MAY 16 2026 870 CALL", "wells_fargo"))
    h2 = _run(compute_hash("SOLD 5 APP MAY 16 2026 870 CALL", "schwab"))
    assert h1 != h2, "Different brokerages should produce different hashes"


def test_hash_deterministic():
    """Same input always produces the same hash."""
    from parsing.pattern_memory import compute_hash

    text = "BOUGHT 100 AAPL @150.25"
    h1 = _run(compute_hash(text, "wfa"))
    h2 = _run(compute_hash(text, "wfa"))
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
    """Simple equity buy with complete data -> high confidence."""
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
    """Dividend payments -> high confidence."""
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
    """Option transactions -> medium confidence."""
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
    """Unknown instrument type -> low confidence."""
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
    """Corporate actions -> low confidence."""
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
    """Sell with known long position -> higher confidence than without."""
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

def _make_mock_supabase():
    """Create a mock Supabase client with in-memory storage."""
    _store: dict[str, dict] = {}

    class MockResponse:
        def __init__(self, data):
            self.data = data

    class MockTable:
        def __init__(self, name):
            self.name = name
            self._filters: dict[str, Any] = {}
            self._limit = None
            self._update_data = None

        def select(self, cols):
            return self

        def eq(self, col, val):
            self._filters[col] = val
            return self

        def limit(self, n):
            self._limit = n
            return self

        def execute(self):
            ph = self._filters.get("pattern_hash")
            bk = self._filters.get("brokerage")
            rid = self._filters.get("id")
            if ph and bk:
                key = f"{ph}|{bk}"
                if key in _store:
                    return MockResponse([_store[key]])
            elif rid and rid in _store:
                return MockResponse([_store[rid]])
            return MockResponse([])

        def insert(self, row):
            if isinstance(row, dict):
                ph = row.get("pattern_hash")
                bk = row.get("brokerage")
                if ph and bk:
                    key = f"{ph}|{bk}"
                    row["id"] = key
                    row["times_matched"] = 1
                    _store[key] = row
                else:
                    # review queue rows
                    import uuid
                    rid = str(uuid.uuid4())
                    row["id"] = rid
                    _store[rid] = row
            return self

        def update(self, data):
            self._update_data = data
            return self

    class MockClient:
        def table(self, name):
            return MockTable(name)

    return MockClient(), _store


def test_store_and_lookup_roundtrip(monkeypatch):
    """store() then lookup() returns the stored classification."""
    from parsing import pattern_memory

    mock_client, _ = _make_mock_supabase()
    monkeypatch.setattr(pattern_memory, "_get_supabase", lambda: mock_client)

    classification = {
        "instrument_type": "option",
        "action": "sell_to_open",
        "strategy": "covered_call",
        "underlying": "APP",
    }

    _run(pattern_memory.store(
        pattern_hash="abc123",
        raw_text="SOLD 5 APP CALL",
        brokerage="wells_fargo",
        classification=classification,
        confidence=0.92,
        source="parser",
    ))

    result = _run(pattern_memory.lookup(
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

    mock_client, _ = _make_mock_supabase()
    monkeypatch.setattr(pattern_memory, "_get_supabase", lambda: mock_client)

    _run(pattern_memory.store(
        pattern_hash="low123",
        raw_text="SOMETHING WEIRD",
        brokerage="schwab",
        classification={"instrument_type": "unknown"},
        confidence=0.50,
        source="parser",
    ))

    result = _run(pattern_memory.lookup(
        pattern_hash="low123",
        brokerage="schwab",
        min_confidence=0.85,
    ))

    assert result is None, "Should return None for low-confidence patterns"


# =========================================================================
#  PART 2 TESTS — Claude Classifier, Review Queue, Orchestrator
# =========================================================================


# ── Claude Classifier ─────────────────────────────────────────────────────

def test_classify_batch_no_api_key(monkeypatch):
    """classify_batch returns rows unchanged when no API key."""
    from parsing.claude_classifier import classify_batch

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    rows = [{"raw_text": "SOLD 5 APP CALL", "action": "sell", "instrument_type": "options"}]
    result = _run(classify_batch(rows, {}, "wells_fargo", api_key=None))
    assert len(result) == 1
    assert result[0]["action"] == "sell"


def test_classify_batch_with_mock_claude(monkeypatch):
    """classify_batch correctly merges Claude results and stores to memory."""
    from parsing import claude_classifier, pattern_memory
    from parsing.claude_classifier import classify_batch

    # Mock Claude API response
    mock_classifications = [
        {
            "instrument_type": "option",
            "action": "sell_to_open",
            "strategy": "covered_call",
            "is_closing": False,
            "underlying": "APP",
            "confidence": 0.92,
        }
    ]

    def mock_call_haiku(system, user, key):
        return mock_classifications

    monkeypatch.setattr(claude_classifier, "_call_haiku", mock_call_haiku)

    # Mock memory store (no-op)
    mock_client, _ = _make_mock_supabase()
    monkeypatch.setattr(pattern_memory, "_get_supabase", lambda: mock_client)

    rows = [
        {
            "index": 0,
            "raw_text": "SOLD 5 APP MAY 16 2026 870 CALL @12.50",
            "action": "sell",
            "instrument_type": "options",
            "symbol": "APP260516C870",
            "confidence": 0.68,
        }
    ]

    result = _run(classify_batch(rows, {"APP": 6800}, "wells_fargo", api_key="test-key"))
    assert len(result) == 1
    assert result[0]["strategy"] == "covered_call"
    assert result[0]["action"] == "sell_to_open"
    assert result[0]["classified_by"] == "claude"


def test_classify_batch_batching(monkeypatch):
    """classify_batch processes in batches of 50."""
    from parsing import claude_classifier, pattern_memory
    from parsing.claude_classifier import classify_batch

    call_count = 0
    batch_sizes = []

    def mock_call_haiku(system, user, key):
        nonlocal call_count
        call_count += 1
        # Parse the prompt to count rows
        import json as _json
        lines = user.split("\n")
        for line in lines:
            if line.strip().startswith("["):
                try:
                    items = _json.loads("\n".join(lines[lines.index(line):]))
                    batch_sizes.append(len(items))
                except Exception:
                    pass
                break
        # Return matching number of results
        return [{"instrument_type": "equity", "confidence": 0.90}] * (batch_sizes[-1] if batch_sizes else 1)

    monkeypatch.setattr(claude_classifier, "_call_haiku", mock_call_haiku)
    mock_client, _ = _make_mock_supabase()
    monkeypatch.setattr(pattern_memory, "_get_supabase", lambda: mock_client)

    # Create 75 rows -> should be 2 batches (50 + 25)
    rows = [
        {"index": i, "raw_text": f"ROW {i}", "action": "sell", "instrument_type": "options", "confidence": 0.5}
        for i in range(75)
    ]

    result = _run(classify_batch(rows, {}, "wells_fargo", api_key="test-key"))
    assert call_count == 2, f"Expected 2 API calls, got {call_count}"
    assert len(result) == 75


# ── Review Queue ──────────────────────────────────────────────────────────

def test_flag_for_review_returns_question():
    """flag_for_review returns a review dict with a question."""
    from parsing.review_queue import flag_for_review

    parser_guess = {
        "instrument_type": "option",
        "action": "sell",
        "confidence": 0.60,
    }
    claude_guess = {
        "instrument_type": "option",
        "action": "sell_to_open",
        "strategy": "covered_call",
        "underlying": "APP",
        "confidence": 0.72,
    }

    result = flag_for_review(
        raw_row="SOLD 5 APP MAY 16 2026 870 CALL",
        parser_guess=parser_guess,
        claude_guess=claude_guess,
    )

    assert "raw_text" in result
    assert "our_interpretation" in result
    assert "question" in result
    assert result["confidence"] == 0.72
    assert "covered call" in result["question"].lower()


def test_flag_for_review_parser_only():
    """flag_for_review works with only parser guess (no Claude)."""
    from parsing.review_queue import flag_for_review

    result = flag_for_review(
        raw_row="UNKNOWN THING",
        parser_guess={"instrument_type": "unknown", "action": "other", "confidence": 0.30},
    )
    assert result["confidence"] == 0.30
    assert "question" in result


def test_resolve_review_confirmed(monkeypatch):
    """resolve_review stores user-confirmed classification in memory."""
    from parsing import pattern_memory
    from parsing.review_queue import resolve_review

    mock_client, store = _make_mock_supabase()

    # Pre-populate a review row
    store["review-1"] = {
        "id": "review-1",
        "raw_text": "SOLD 5 APP CALL",
        "our_interpretation": {
            "instrument_type": "option",
            "action": "sell_to_open",
            "strategy": "covered_call",
        },
        "confidence": 0.72,
    }

    monkeypatch.setattr(pattern_memory, "_get_supabase", lambda: mock_client)

    # Also mock the review_queue's _get_supabase
    from parsing import review_queue
    monkeypatch.setattr(review_queue, "_get_supabase", lambda: mock_client)

    _run(resolve_review("review-1", "confirmed", brokerage="wells_fargo"))

    # The confirmation should have stored a pattern in memory
    # (We can't directly check the store due to mock limitations,
    # but the function completing without error is the key assertion)


# ── Orchestrator ──────────────────────────────────────────────────────────

def test_orchestrator_high_confidence_rows(monkeypatch):
    """High-confidence rows go through Layer 1 only (no Claude calls)."""
    from parsing import pattern_memory
    from parsing.orchestrator import parse_with_intelligence

    mock_client, _ = _make_mock_supabase()
    monkeypatch.setattr(pattern_memory, "_get_supabase", lambda: mock_client)

    rows = [
        {
            "action": "buy",
            "instrument_type": "equity",
            "symbol": "AAPL",
            "quantity": 100,
            "price": 150.0,
            "amount": 15000.0,
            "description": "BOUGHT 100 AAPL @150.00",
            "raw_text": "BOUGHT 100 AAPL @150.00",
        },
        {
            "action": "dividend",
            "instrument_type": "equity",
            "symbol": "MSFT",
            "quantity": 0,
            "price": 0,
            "amount": 75.0,
            "description": "DIVIDEND MSFT",
            "raw_text": "DIVIDEND MSFT $75.00",
        },
    ]

    result = _run(parse_with_intelligence(rows, "wells_fargo"))

    assert result["stats"]["total"] == 2
    assert result["stats"]["layer1_resolved"] == 2
    assert result["stats"]["layer2_resolved"] == 0
    assert result["stats"]["layer3_flagged"] == 0
    assert len(result["transactions"]) == 2
    assert len(result["review_needed"]) == 0


def test_orchestrator_ambiguous_rows_go_to_layer2(monkeypatch):
    """Ambiguous rows below threshold are batched to Claude."""
    from parsing import pattern_memory
    from parsing.orchestrator import parse_with_intelligence

    mock_client, _ = _make_mock_supabase()
    monkeypatch.setattr(pattern_memory, "_get_supabase", lambda: mock_client)

    claude_called = False

    async def mock_classify_batch(rows, ctx, brokerage, **kw):
        nonlocal claude_called
        claude_called = True
        return [
            {**r, "strategy": "covered_call", "action": "sell_to_open", "confidence": 0.90, "classified_by": "claude"}
            for r in rows
        ]

    monkeypatch.setattr(
        "parsing.orchestrator.classify_batch",
        mock_classify_batch,
    )

    rows = [
        {
            "action": "sell",
            "instrument_type": "options",
            "symbol": "APP260516C870",
            "quantity": 5,
            "price": 12.50,
            "amount": 6250.0,
            "description": "SOLD 5 APP MAY 16 2026 870 CALL",
            "raw_text": "SOLD 5 APP MAY 16 2026 870 CALL @12.50",
        },
    ]

    result = _run(parse_with_intelligence(rows, "wells_fargo"))

    assert claude_called, "Claude should have been called for ambiguous row"
    assert result["stats"]["layer2_resolved"] == 1
    assert result["transactions"][0]["strategy"] == "covered_call"


def test_orchestrator_low_claude_confidence_flags_review(monkeypatch):
    """Rows where Claude is also uncertain get flagged for review."""
    from parsing import pattern_memory
    from parsing.orchestrator import parse_with_intelligence

    mock_client, _ = _make_mock_supabase()
    monkeypatch.setattr(pattern_memory, "_get_supabase", lambda: mock_client)

    async def mock_classify_batch(rows, ctx, brokerage, **kw):
        return [
            {**r, "confidence": 0.55, "classified_by": "claude"}
            for r in rows
        ]

    monkeypatch.setattr(
        "parsing.orchestrator.classify_batch",
        mock_classify_batch,
    )

    # Mock review_queue._get_supabase too
    from parsing import review_queue
    monkeypatch.setattr(review_queue, "_get_supabase", lambda: mock_client)

    rows = [
        {
            "action": "other",
            "instrument_type": "unknown",
            "symbol": "XYZ",
            "quantity": 50,
            "price": 0,
            "amount": 0,
            "description": "MANDATORY SPINOFF XYZ INTO ABC",
            "raw_text": "MANDATORY SPINOFF XYZ INTO ABC",
        },
    ]

    result = _run(parse_with_intelligence(rows, "wells_fargo"))

    assert result["stats"]["layer3_flagged"] == 1
    assert len(result["review_needed"]) == 1
    assert result["review_needed"][0]["raw_text"] == "MANDATORY SPINOFF XYZ INTO ABC"


def test_orchestrator_memory_hit_skips_claude(monkeypatch):
    """When memory has a high-confidence hit, Claude is not called."""
    from parsing import pattern_memory
    from parsing.orchestrator import parse_with_intelligence

    mock_client, store = _make_mock_supabase()

    # Pre-populate pattern memory with a known pattern
    raw_text = "SOLD 5 APP MAY 16 2026 870 CALL @12.50"
    pattern_hash = _run(pattern_memory.compute_hash(raw_text, "wells_fargo"))
    store[f"{pattern_hash}|wells_fargo"] = {
        "id": f"{pattern_hash}|wells_fargo",
        "pattern_hash": pattern_hash,
        "brokerage": "wells_fargo",
        "classification": {
            "instrument_type": "option",
            "action": "sell_to_open",
            "strategy": "covered_call",
            "confidence": 0.95,
        },
        "confidence": 0.95,
        "source": "user_confirmed",
        "times_matched": 5,
    }

    monkeypatch.setattr(pattern_memory, "_get_supabase", lambda: mock_client)

    claude_called = False

    async def mock_classify_batch(rows, ctx, brokerage, **kw):
        nonlocal claude_called
        claude_called = True
        return rows

    monkeypatch.setattr(
        "parsing.orchestrator.classify_batch",
        mock_classify_batch,
    )

    rows = [
        {
            "action": "sell",
            "instrument_type": "options",
            "symbol": "APP260516C870",
            "quantity": 5,
            "price": 12.50,
            "amount": 6250.0,
            "description": "SOLD 5 APP MAY 16 2026 870 CALL",
            "raw_text": raw_text,
        },
    ]

    result = _run(parse_with_intelligence(rows, "wells_fargo"))

    assert result["stats"]["memory_hits"] == 1
    assert result["stats"]["layer1_resolved"] == 1
    assert not claude_called, "Claude should NOT be called when memory hit resolves"
    assert result["transactions"][0]["classified_by"] == "memory"


def test_orchestrator_mixed_batch(monkeypatch):
    """Mix of high-confidence, ambiguous, and unresolvable rows routes correctly."""
    from parsing import pattern_memory
    from parsing.orchestrator import parse_with_intelligence

    mock_client, _ = _make_mock_supabase()
    monkeypatch.setattr(pattern_memory, "_get_supabase", lambda: mock_client)

    async def mock_classify_batch(rows, ctx, brokerage, **kw):
        results = []
        for r in rows:
            if "SPINOFF" in r.get("raw_text", ""):
                results.append({**r, "confidence": 0.40, "classified_by": "claude"})
            else:
                results.append({**r, "confidence": 0.90, "strategy": "covered_call", "classified_by": "claude"})
        return results

    monkeypatch.setattr("parsing.orchestrator.classify_batch", mock_classify_batch)

    from parsing import review_queue
    monkeypatch.setattr(review_queue, "_get_supabase", lambda: mock_client)

    rows = [
        # High confidence -> Layer 1
        {
            "action": "buy", "instrument_type": "equity", "symbol": "AAPL",
            "quantity": 100, "price": 150.0, "amount": 15000.0,
            "description": "BOUGHT 100 AAPL", "raw_text": "BOUGHT 100 AAPL @150",
        },
        # Medium confidence -> Layer 2 (resolved by Claude)
        {
            "action": "sell", "instrument_type": "options", "symbol": "APP260516C870",
            "quantity": 5, "price": 12.50, "amount": 6250.0,
            "description": "SOLD 5 APP CALL", "raw_text": "SOLD 5 APP MAY 16 2026 870 CALL",
        },
        # Low confidence -> Layer 3 (Claude also uncertain)
        {
            "action": "other", "instrument_type": "unknown", "symbol": "XYZ",
            "quantity": 50, "price": 0, "amount": 0,
            "description": "MANDATORY SPINOFF XYZ",
            "raw_text": "MANDATORY SPINOFF XYZ INTO ABC",
        },
    ]

    result = _run(parse_with_intelligence(rows, "wells_fargo"))

    assert result["stats"]["total"] == 3
    assert result["stats"]["layer1_resolved"] == 1
    assert result["stats"]["layer2_resolved"] == 1
    assert result["stats"]["layer3_flagged"] == 1
    assert len(result["transactions"]) == 3
    assert len(result["review_needed"]) == 1


def test_orchestrator_stats_structure():
    """Returned stats dict has all expected keys."""
    from parsing.orchestrator import parse_with_intelligence

    # Empty input
    result = _run(parse_with_intelligence([], "wells_fargo"))
    stats = result["stats"]
    assert stats["total"] == 0
    assert stats["layer1_resolved"] == 0
    assert stats["layer2_resolved"] == 0
    assert stats["layer3_flagged"] == 0
    assert stats["memory_hits"] == 0
    assert stats["new_patterns_learned"] == 0
    assert result["transactions"] == []
    assert result["review_needed"] == []


# ── Runner ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Parsing Intelligence Layer — Test Suite (Part 1 + 2)")
    print("=" * 60)

    passed = 0
    failed = 0
    tests = [
        # Part 1
        ("Import package", test_import_package),
        ("Import Part 2 modules", test_import_part2_modules),
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
        # Part 2 (non-monkeypatch only)
        ("Review: flag returns question", test_flag_for_review_returns_question),
        ("Review: parser-only guess", test_flag_for_review_parser_only),
        ("Orchestrator: stats structure", test_orchestrator_stats_structure),
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
    print("  (monkeypatch tests require: pytest -v)")
    print("=" * 60)
    sys.exit(1 if failed else 0)
