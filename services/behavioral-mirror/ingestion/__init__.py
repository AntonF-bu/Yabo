"""Universal self-learning trade ingestion system.

Replaces brokerage-specific parsers with a self-learning system that:
1. Checks stored parser configs by header signature
2. If match found → parse instantly (no API call)
3. If no match → send to Claude for normalization + config generation
4. Save config for future use
"""

from ingestion.universal_parser import UniversalParser
from ingestion.config_executor import ConfigExecutor

__all__ = ["UniversalParser", "ConfigExecutor"]
