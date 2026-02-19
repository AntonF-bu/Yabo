"""Format detection for uploaded brokerage CSV files.

Checks uploaded files against known format_signatures stored in Supabase.
Falls back to Claude API classification for unknown formats.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FormatMatch:
    signature_id: str | None
    brokerage: str
    format_name: str
    parser_config: dict[str, Any]
    data_types: list[str]
    is_new: bool


class FormatDetector:
    def __init__(self, supabase_client: Any):
        self.supabase = supabase_client

    def detect(self, file_content: str, filename: str) -> FormatMatch:
        """Detect the format of a CSV file.

        1. Read first 20 lines
        2. Check against known format_signatures
        3. Fall back to Claude API if no match
        """
        lines = file_content.split("\n")[:20]

        # Query all format signatures
        resp = self.supabase.table("format_signatures").select("*").execute()
        signatures = resp.data or []

        for sig in signatures:
            rules = sig.get("detection_rules") or {}

            # Check header_contains
            header_match = False
            if "header_contains" in rules:
                for line in lines:
                    for pattern in rules["header_contains"]:
                        if pattern.lower() in line.lower():
                            header_match = True
                            break
                    if header_match:
                        break

            # Check columns_contain
            col_match = False
            if "columns_contain" in rules:
                for line in lines:
                    cols = [c.strip().strip('"') for c in line.split(",")]
                    cols_lower = [c.lower() for c in cols]
                    if all(
                        req.lower() in cols_lower
                        for req in rules["columns_contain"]
                    ):
                        col_match = True
                        break

            if header_match and col_match:
                # Increment times_matched
                try:
                    self.supabase.table("format_signatures").update(
                        {"times_matched": (sig.get("times_matched") or 0) + 1}
                    ).eq("id", sig["id"]).execute()
                except Exception:
                    logger.debug("Failed to increment times_matched (non-fatal)")

                logger.info(
                    "Format matched: %s (%s)",
                    sig["format_name"],
                    sig["brokerage"],
                )
                return FormatMatch(
                    signature_id=sig["id"],
                    brokerage=sig["brokerage"],
                    format_name=sig["format_name"],
                    parser_config=sig.get("parser_config") or {},
                    data_types=sig.get("data_types") or [],
                    is_new=False,
                )

        # No match — classify with Claude
        logger.info("No format match for %s, attempting Claude classification", filename)
        return self._classify_with_claude(lines, filename)

    def _classify_with_claude(self, lines: list[str], filename: str) -> FormatMatch:
        """Send sample lines to Claude API for format classification."""
        import os

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("No ANTHROPIC_API_KEY — returning unknown format")
            return FormatMatch(
                signature_id=None,
                brokerage="unknown",
                format_name="Unknown CSV Format",
                parser_config={},
                data_types=["unknown"],
                is_new=True,
            )

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            sample = "\n".join(lines)

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Classify this brokerage CSV export.\n"
                            f"Filename: {filename}\n"
                            f"First 20 lines:\n```\n{sample}\n```\n\n"
                            f"Respond in JSON with:\n"
                            f'{{"brokerage": "name", "format_name": "description", '
                            f'"data_types": ["trades","holdings","income","fees"], '
                            f'"header_row": number, "columns_contain": ["col1","col2"]}}'
                        ),
                    }
                ],
            )

            import json

            text = response.content[0].text
            # Try to extract JSON from response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(text[start:end])
            else:
                parsed = {}

            brokerage = parsed.get("brokerage", "unknown")
            format_name = parsed.get("format_name", "Unknown Format")
            data_types = parsed.get("data_types", ["unknown"])

            # Save new signature for future matching
            try:
                sig_data = {
                    "signature": f"auto_{brokerage}_{hash(sample) % 10000}",
                    "brokerage": brokerage,
                    "format_name": format_name,
                    "data_types": data_types,
                    "parser_config": parsed,
                    "sample_headers": parsed.get("columns_contain", []),
                    "detection_rules": {
                        "header_contains": [],
                        "columns_contain": parsed.get("columns_contain", []),
                    },
                }
                result = (
                    self.supabase.table("format_signatures")
                    .insert(sig_data)
                    .execute()
                )
                sig_id = result.data[0]["id"] if result.data else None
            except Exception:
                logger.debug("Failed to save new format signature (non-fatal)")
                sig_id = None

            return FormatMatch(
                signature_id=sig_id,
                brokerage=brokerage,
                format_name=format_name,
                parser_config=parsed,
                data_types=data_types,
                is_new=True,
            )

        except Exception as e:
            logger.error("Claude classification failed: %s", e, exc_info=True)
            return FormatMatch(
                signature_id=None,
                brokerage="unknown",
                format_name="Unknown CSV Format",
                parser_config={},
                data_types=["unknown"],
                is_new=True,
            )
