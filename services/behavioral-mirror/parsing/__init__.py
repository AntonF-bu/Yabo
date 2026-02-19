"""Intelligent parsing layer — pattern memory and confidence scoring.

Wraps the existing WFA parser with:
- Pattern hashing for cross-user transaction matching
- Supabase-backed memory of parsed patterns
- Confidence scoring for each parsed transaction
"""

from .confidence import score_confidence
from .pattern_memory import compute_hash, get_memory_stats, lookup, store

__all__ = [
    "compute_hash",
    "lookup",
    "store",
    "get_memory_stats",
    "score_confidence",
]
