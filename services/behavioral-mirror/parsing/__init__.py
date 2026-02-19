"""Intelligent parsing layer — pattern memory, confidence, and orchestration.

Wraps the existing WFA parser with:
- Pattern hashing for cross-user transaction matching
- Supabase-backed memory of parsed patterns
- Confidence scoring for each parsed transaction
- Claude Haiku batch classification for ambiguous rows
- Review queue for low-confidence transactions
- Orchestrator that ties all layers together
"""

from .confidence import score_confidence
from .pattern_memory import compute_hash, get_memory_stats, lookup, store

# Layer 2 + 3 + orchestrator (imported lazily to avoid pulling in
# anthropic SDK when only using Part 1 functions)

__all__ = [
    # Part 1
    "compute_hash",
    "lookup",
    "store",
    "get_memory_stats",
    "score_confidence",
    # Part 2 (use: from parsing.claude_classifier import classify_batch)
    # Part 2 (use: from parsing.review_queue import flag_for_review, resolve_review)
    # Part 2 (use: from parsing.orchestrator import parse_with_intelligence)
]
