"""Universal self-learning trade CSV parser.

Parses any brokerage CSV format by:
1. Computing a header signature from the CSV columns
2. Looking up a cached parser config matching that signature
3. If found → apply config instantly (no API call)
4. If not found → send header + sample rows to Claude for normalization
5. Claude returns normalized trades AND a reusable parser config
6. Config saved to Supabase for future instant parsing
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ingestion.config_executor import ConfigExecutor
from ingestion.seed_configs import get_seed_configs

logger = logging.getLogger(__name__)

CANONICAL_COLUMNS = ["ticker", "action", "quantity", "price", "date", "fees"]

# Table name in Supabase
PARSER_CONFIGS_TABLE = "parser_configs"


class UniversalParser:
    """Self-learning universal trade CSV parser."""

    def __init__(self) -> None:
        # In-memory config cache: signature -> config
        self._config_cache: dict[str, dict[str, Any]] = {}
        self._configs_loaded = False

    def parse(
        self, csv_path: str | Path,
    ) -> tuple[pd.DataFrame, str, dict[str, Any] | None]:
        """Parse a trade CSV file using cached config or Claude fallback.

        Returns:
            Tuple of (normalized DataFrame, format_name, metadata or None).
            metadata may contain 'cash_flow' and/or 'option_trades' keys.
        """
        csv_path = Path(csv_path)
        df = pd.read_csv(csv_path)

        if df.empty:
            return df, "empty", None

        # Ensure configs are loaded
        self._ensure_configs_loaded()

        # Compute header signature
        signature = self._compute_signature(df)
        logger.info(
            "[UniversalParser] CSV: %s, %d rows, signature: %s",
            csv_path.name, len(df), signature[:50],
        )

        # Try cached config
        config = self._find_config(df, signature)
        if config:
            logger.info(
                "[UniversalParser] CACHE HIT: '%s' (config: %s, used %d times)",
                config["format_name"], config["config_id"],
                config.get("times_used", 0),
            )
            executor = ConfigExecutor(config)

            # Validate config still works
            validation = executor.validate(df)
            if not validation["valid"]:
                logger.warning(
                    "[UniversalParser] Config '%s' validation failed: %s. "
                    "Attempting self-heal...",
                    config["config_id"], validation["issues"],
                )
                healed = self._try_self_heal(config, df, validation["issues"])
                if healed:
                    config = healed
                    executor = ConfigExecutor(config)
                else:
                    # Config broken, fall through to Claude
                    logger.warning(
                        "[UniversalParser] Self-heal failed. Falling back to Claude."
                    )
                    return self._claude_fallback(df, csv_path)

            result, metadata = executor.execute(df)
            self._increment_usage(config["config_id"])
            return result, config["format_name"], metadata

        # No config found — try Claude
        logger.info("[UniversalParser] CACHE MISS: no config for signature. Trying Claude...")
        return self._claude_fallback(df, csv_path)

    def _ensure_configs_loaded(self) -> None:
        """Load seed configs + Supabase configs into memory."""
        if self._configs_loaded:
            return

        # Load seed configs
        for config in get_seed_configs():
            sig = config["header_signature"]
            self._config_cache[sig] = config

        # Load from Supabase
        try:
            configs = self._load_supabase_configs()
            for config in configs:
                sig = config["header_signature"]
                # Supabase configs override seeds if same signature
                self._config_cache[sig] = config
            if configs:
                logger.info(
                    "[UniversalParser] Loaded %d configs from Supabase", len(configs)
                )
        except Exception:
            logger.debug("[UniversalParser] Supabase config load failed (non-fatal)")

        self._configs_loaded = True
        logger.info(
            "[UniversalParser] %d parser configs loaded (seed + stored)",
            len(self._config_cache),
        )

    def _compute_signature(self, df: pd.DataFrame) -> str:
        """Compute a stable header signature from DataFrame columns."""
        return "|".join(sorted(c.strip().lower() for c in df.columns))

    def _find_config(
        self, df: pd.DataFrame, signature: str,
    ) -> dict[str, Any] | None:
        """Find a matching config by exact signature or required header match."""
        # Exact signature match
        if signature in self._config_cache:
            return self._config_cache[signature]

        # Fuzzy match: check if required_headers are a subset of actual columns
        actual_cols_lower = {c.strip().lower() for c in df.columns}
        best_match: dict[str, Any] | None = None
        best_score = 0

        for sig, config in self._config_cache.items():
            required = config.get("required_headers", [])
            if not required:
                continue
            required_lower = {h.strip().lower() for h in required}
            if required_lower <= actual_cols_lower:
                # All required headers present
                score = len(required_lower)
                if score > best_score:
                    best_score = score
                    best_match = config

        return best_match

    def _claude_fallback(
        self, df: pd.DataFrame, csv_path: Path,
    ) -> tuple[pd.DataFrame, str, dict[str, Any] | None]:
        """Send CSV to Claude for normalization and config generation.

        Claude returns both:
        - Normalized trades as JSON
        - A reusable parser config for this format
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning(
                "[UniversalParser] No ANTHROPIC_API_KEY — falling back to legacy parser"
            )
            return self._legacy_fallback(df, csv_path)

        # Prepare sample data (first 10 rows + headers)
        sample_rows = df.head(10).to_csv(index=False)
        headers = list(df.columns)
        total_rows = len(df)

        prompt = self._build_claude_prompt(headers, sample_rows, total_rows)

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = response.content[0].text
            parsed = self._parse_claude_response(response_text)

            if not parsed:
                logger.warning("[UniversalParser] Claude response parsing failed")
                return self._legacy_fallback(df, csv_path)

            trades_data = parsed.get("trades", [])
            config = parsed.get("parser_config")

            # Build DataFrame from Claude's normalized trades
            if trades_data:
                result = self._trades_to_dataframe(trades_data)
            else:
                logger.warning("[UniversalParser] Claude returned no trades")
                return self._legacy_fallback(df, csv_path)

            format_name = "claude_normalized"

            # If Claude generated a config, save it for future use
            if config:
                config["config_id"] = f"claude_{self._compute_config_hash(config)}"
                config["source"] = "claude"
                config["created_at"] = datetime.now(timezone.utc).isoformat()
                config["header_signature"] = self._compute_signature(df)
                config["confidence"] = 0.8
                config["times_used"] = 0
                format_name = config.get("format_name", "claude_normalized")

                # Validate the generated config before saving
                executor = ConfigExecutor(config)
                validation = executor.validate(df)
                if validation["valid"]:
                    self._save_config(config)
                    logger.info(
                        "[UniversalParser] Saved new config '%s' from Claude",
                        config["config_id"],
                    )
                else:
                    logger.warning(
                        "[UniversalParser] Claude-generated config failed validation: %s",
                        validation["issues"],
                    )

            logger.info(
                "[UniversalParser] Claude normalized %d trades from %d rows",
                len(result), total_rows,
            )
            return result, format_name, None

        except Exception as e:
            logger.exception("[UniversalParser] Claude normalization failed: %s", e)
            return self._legacy_fallback(df, csv_path)

    def _build_claude_prompt(
        self, headers: list[str], sample_rows: str, total_rows: int,
    ) -> str:
        """Build the Claude prompt for CSV normalization + config generation."""
        return f"""You are a trade CSV normalization expert. Given a CSV from a trading platform, you must:

1. NORMALIZE the sample trades into a standard format
2. GENERATE a reusable parser config so future uploads of this format parse instantly

## INPUT CSV
Headers: {json.dumps(headers)}
Total rows: {total_rows}

Sample data (first 10 rows):
```
{sample_rows}
```

## REQUIRED OUTPUT FORMAT
Return a JSON object with exactly two keys:

```json
{{
  "trades": [
    {{
      "date": "YYYY-MM-DD",
      "ticker": "SYMBOL",
      "action": "BUY or SELL",
      "quantity": 100,
      "price": 150.50,
      "fees": 0.0
    }}
  ],
  "parser_config": {{
    "format_name": "Human-readable format name",
    "required_headers": ["list", "of", "required", "columns"],
    "column_map": {{
      "date": "actual_csv_column_name_for_dates",
      "ticker": "actual_csv_column_name_for_ticker",
      "action": "actual_csv_column_name_for_action",
      "quantity": "actual_csv_column_name_for_quantity",
      "price": "actual_csv_column_name_for_price",
      "fees": "actual_csv_column_name_for_fees_or_null"
    }},
    "action_map": {{
      "original_action_value": "BUY or SELL",
      "another_value": "BUY or SELL"
    }},
    "skip_actions": ["Dividend", "Interest", "etc"],
    "date_format": "strftime_format_or_null",
    "number_cleanup": ["$", ","]
  }}
}}
```

## RULES
- Only include BUY and SELL trades (skip dividends, deposits, withdrawals, interest, fees)
- Normalize ticker symbols (remove exchange suffixes like .L, keep just the symbol)
- Parse quantities as positive numbers
- Parse prices as positive decimals (remove currency symbols)
- action must be exactly "BUY" or "SELL"
- If a column doesn't exist for fees, set fees to null in column_map
- The parser_config must work for ALL rows of this format, not just the sample
- Return ONLY the JSON object, no markdown fences or explanation
"""

    def _parse_claude_response(self, text: str) -> dict[str, Any] | None:
        """Parse Claude's JSON response, handling markdown fences."""
        # Strip markdown code fences if present
        text = text.strip()
        if text.startswith("```"):
            # Remove opening fence
            first_newline = text.index("\n")
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON in the response
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            logger.warning("[UniversalParser] Could not parse Claude response as JSON")
            return None

    def _trades_to_dataframe(self, trades: list[dict]) -> pd.DataFrame:
        """Convert Claude's normalized trade list to a DataFrame."""
        rows = []
        for t in trades:
            try:
                rows.append({
                    "date": pd.to_datetime(t["date"]),
                    "ticker": str(t["ticker"]).strip().upper(),
                    "action": str(t["action"]).upper(),
                    "quantity": abs(float(t.get("quantity", 0))),
                    "price": abs(float(t.get("price", 0))),
                    "fees": float(t.get("fees", 0) or 0),
                })
            except (ValueError, KeyError) as e:
                logger.debug("[UniversalParser] Skipping malformed trade: %s", e)

        if not rows:
            return pd.DataFrame(columns=CANONICAL_COLUMNS)

        result = pd.DataFrame(rows)
        result = result[result["action"].isin(("BUY", "SELL"))]
        result = result[(result["quantity"] > 0) & (result["price"] > 0)]
        return result[CANONICAL_COLUMNS].reset_index(drop=True)

    def _legacy_fallback(
        self, df: pd.DataFrame, csv_path: Path,
    ) -> tuple[pd.DataFrame, str, dict[str, Any] | None]:
        """Fall back to the existing csv_parsers module."""
        from extractor.csv_parsers import normalize_csv_with_metadata
        logger.info("[UniversalParser] Using legacy parser fallback")
        return normalize_csv_with_metadata(csv_path)

    def _try_self_heal(
        self,
        config: dict[str, Any],
        df: pd.DataFrame,
        issues: list[str],
    ) -> dict[str, Any] | None:
        """Attempt to fix a broken config by remapping columns.

        Simple heuristic: if a column name changed case or gained/lost
        whitespace, try case-insensitive matching.
        """
        healed = dict(config)
        col_map = dict(healed.get("column_map", {}))
        actual_cols = {c.strip().lower(): c for c in df.columns}

        fixed_any = False
        for field in ["date", "ticker", "action", "quantity", "price", "fees"]:
            target = col_map.get(field)
            if target is None:
                continue
            if target in df.columns:
                continue
            # Try case-insensitive
            lower = target.strip().lower()
            if lower in actual_cols:
                col_map[field] = actual_cols[lower]
                fixed_any = True
                logger.info(
                    "[UniversalParser] Self-healed: '%s' -> '%s' for field '%s'",
                    target, actual_cols[lower], field,
                )

        if fixed_any:
            healed["column_map"] = col_map
            healed["version"] = healed.get("version", 1) + 1
            return healed

        return None

    def _save_config(self, config: dict[str, Any]) -> None:
        """Save a parser config to in-memory cache and Supabase."""
        sig = config["header_signature"]
        self._config_cache[sig] = config

        try:
            client = self._get_supabase()
            if client:
                row = {
                    "config_id": config["config_id"],
                    "format_name": config.get("format_name", ""),
                    "header_signature": sig,
                    "config_json": json.dumps(config, default=str),
                    "source": config.get("source", "claude"),
                    "confidence": config.get("confidence", 0.8),
                    "times_used": config.get("times_used", 0),
                    "version": config.get("version", 1),
                    "created_at": config.get(
                        "created_at", datetime.now(timezone.utc).isoformat()
                    ),
                }
                client.table(PARSER_CONFIGS_TABLE).upsert(row).execute()
                logger.info(
                    "[UniversalParser] Saved config '%s' to Supabase", config["config_id"]
                )
        except Exception:
            logger.debug("[UniversalParser] Supabase config save failed (non-fatal)")

    def _increment_usage(self, config_id: str) -> None:
        """Increment the usage counter for a config."""
        for sig, config in self._config_cache.items():
            if config.get("config_id") == config_id:
                config["times_used"] = config.get("times_used", 0) + 1
                break

        # Also update Supabase (best-effort)
        try:
            client = self._get_supabase()
            if client:
                client.rpc("increment_parser_config_usage", {
                    "p_config_id": config_id,
                }).execute()
        except Exception:
            pass  # Non-fatal

    def _load_supabase_configs(self) -> list[dict[str, Any]]:
        """Load all parser configs from Supabase."""
        client = self._get_supabase()
        if client is None:
            return []

        resp = (
            client.table(PARSER_CONFIGS_TABLE)
            .select("*")
            .order("times_used", desc=True)
            .execute()
        )

        configs = []
        for row in resp.data:
            try:
                config = json.loads(row["config_json"])
                config["times_used"] = row.get("times_used", 0)
                configs.append(config)
            except (json.JSONDecodeError, KeyError):
                logger.debug("Skipping invalid config row: %s", row.get("config_id"))
        return configs

    def _get_supabase(self):
        """Get Supabase client (lazy, returns None if not configured)."""
        from storage.supabase_client import _get_client
        return _get_client()

    def _compute_config_hash(self, config: dict[str, Any]) -> str:
        """Compute a short hash for a config."""
        canonical = json.dumps(config.get("column_map", {}), sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()[:8]

    # ─── Public API for config management ────────────────────────────────

    def list_configs(self) -> list[dict[str, Any]]:
        """List all loaded parser configs with metadata."""
        self._ensure_configs_loaded()
        return [
            {
                "config_id": c["config_id"],
                "format_name": c.get("format_name", ""),
                "source": c.get("source", ""),
                "confidence": c.get("confidence", 0),
                "times_used": c.get("times_used", 0),
                "version": c.get("version", 1),
                "has_options": c.get("has_options", False),
            }
            for c in self._config_cache.values()
        ]

    def get_config(self, config_id: str) -> dict[str, Any] | None:
        """Get a specific config by ID."""
        self._ensure_configs_loaded()
        for config in self._config_cache.values():
            if config.get("config_id") == config_id:
                return config
        return None

    def seed_configs(self) -> int:
        """Ensure seed configs are saved to Supabase. Returns count saved."""
        count = 0
        for config in get_seed_configs():
            try:
                self._save_config(config)
                count += 1
            except Exception:
                logger.debug("Failed to seed config: %s", config.get("config_id"))
        return count
