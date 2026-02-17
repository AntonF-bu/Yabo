"""Extract structured trade data from brokerage screenshots using Claude Vision."""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
You are extracting trade data from a brokerage account screenshot.

Look at this screenshot carefully. Extract EVERY trade/transaction visible.

For each trade, extract:
- date: The trade date (format: YYYY-MM-DD). If only month/day visible, assume current year.
- ticker: The stock ticker symbol (e.g., AAPL, NVDA, ORCL)
- side: BUY or SELL
- quantity: Number of shares (decimal ok for fractional)
- price: Price per share in USD (number only, no $ sign)
- total: Total transaction amount in USD (number only)

If you can see the brokerage name, include it.
If you can see account type (margin, cash, IRA), include it.

Return ONLY valid JSON in this exact format, no other text:
{
    "brokerage": "Wells Fargo" or null,
    "account_type": "margin" or "cash" or null,
    "trades": [
        {
            "date": "2025-01-15",
            "ticker": "ORCL",
            "side": "BUY",
            "quantity": 500,
            "price": 168.50,
            "total": 84250.00,
            "confidence": "high"
        }
    ],
    "notes": "any relevant context visible in screenshot"
}

Rules:
- If a value is partially obscured or unclear, set confidence to "low" for that trade
- If you can calculate total from qty * price but the screenshot shows a different number, flag it
- Include ALL visible trades, even partial rows
- Do NOT guess or hallucinate trades that aren't visible
- If the screenshot doesn't contain trade data, return {"trades": [], "notes": "No trade data found"}
"""


def _get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")
    return anthropic.Anthropic(api_key=api_key)


def extract_trades_from_screenshot(
    image_bytes: bytes,
    media_type: str = "image/png",
) -> dict[str, Any]:
    """Extract trades from a single screenshot using Claude Vision."""
    client = _get_client()
    base64_image = base64.standard_b64encode(image_bytes).decode("utf-8")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_image,
                        },
                    },
                    {"type": "text", "text": EXTRACTION_PROMPT},
                ],
            }
        ],
    )

    response_text = response.content[0].text

    # Strip markdown code fences if present
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]

    try:
        result = json.loads(cleaned.strip())
    except json.JSONDecodeError:
        logger.warning("Failed to parse Vision response: %s", cleaned[:200])
        result = {
            "trades": [],
            "notes": f"Failed to parse response: {cleaned[:200]}",
        }

    return result


def extract_from_multiple_screenshots(
    images: list[tuple[bytes, str]],
) -> dict[str, Any]:
    """Extract trades from multiple screenshots.

    Args:
        images: list of (image_bytes, media_type) tuples.

    Returns combined and deduplicated trade list.
    """
    all_trades: list[dict[str, Any]] = []
    brokerage: str | None = None
    account_type: str | None = None
    notes: list[str] = []

    for i, (img_bytes, media_type) in enumerate(images):
        logger.info("Extracting from screenshot %d/%d", i + 1, len(images))
        result = extract_trades_from_screenshot(img_bytes, media_type)

        if result.get("brokerage") and not brokerage:
            brokerage = result["brokerage"]
        if result.get("account_type") and not account_type:
            account_type = result["account_type"]

        for trade in result.get("trades", []):
            trade["source_screenshot"] = i + 1
            all_trades.append(trade)

        if result.get("notes"):
            notes.append(f"Screenshot {i + 1}: {result['notes']}")

    # Deduplicate trades (same date + ticker + side + quantity)
    seen: set[str] = set()
    unique_trades: list[dict[str, Any]] = []
    for trade in all_trades:
        key = (
            f"{trade.get('date')}_{trade.get('ticker')}_"
            f"{trade.get('side')}_{trade.get('quantity')}"
        )
        if key not in seen:
            seen.add(key)
            unique_trades.append(trade)

    return {
        "brokerage": brokerage,
        "account_type": account_type,
        "total_screenshots": len(images),
        "trades_extracted": len(unique_trades),
        "duplicates_removed": len(all_trades) - len(unique_trades),
        "trades": unique_trades,
        "notes": notes,
    }
