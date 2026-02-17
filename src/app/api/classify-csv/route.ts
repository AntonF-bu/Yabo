import { NextResponse } from "next/server";
import Anthropic from "@anthropic-ai/sdk";

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || "",
});

export async function POST(request: Request) {
  try {
    if (!process.env.ANTHROPIC_API_KEY) {
      return NextResponse.json(
        { error: "API key not configured" },
        { status: 503 }
      );
    }

    const { headers, sampleRows } = await request.json();

    if (!headers || !Array.isArray(headers) || headers.length === 0) {
      return NextResponse.json(
        { error: "No headers provided" },
        { status: 400 }
      );
    }

    const rowsText = sampleRows
      .map((row: string[], i: number) => `Row ${i + 1}: ${row.join(" | ")}`)
      .join("\n");

    const prompt = `You are a CSV column classifier for a trading platform. Given these CSV headers and sample rows, identify which columns map to these required fields:
- date: the trade execution date
- ticker: the stock symbol/ticker
- action: buy or sell indicator
- quantity: number of shares
- price: price per share

Also identify if there are rows that should be filtered out (dividends, deposits, withdrawals, interest, fees-only rows).

Respond ONLY with valid JSON, no markdown, no explanation:
{
  "mapping": {
    "date": "exact header name",
    "ticker": "exact header name",
    "action": "exact header name",
    "quantity": "exact header name",
    "price": "exact header name"
  },
  "filter_out": ["list of Action/Type values to exclude, e.g. 'Dividend', 'Deposit'"],
  "action_mapping": {
    "buy_values": ["values that mean BUY, e.g. 'Buy', 'BUY', 'B', 'Market Buy'"],
    "sell_values": ["values that mean SELL, e.g. 'Sell', 'SELL', 'S', 'Market Sell'"]
  },
  "confidence": "high" or "medium" or "low"
}

Headers: ${headers.join(" | ")}
Sample rows:
${rowsText}`;

    const message = await anthropic.messages.create({
      model: "claude-haiku-4-5-20251001",
      max_tokens: 500,
      messages: [{ role: "user", content: prompt }],
    });

    const text =
      message.content[0].type === "text" ? message.content[0].text : "";

    // Parse and validate the response
    const result = JSON.parse(text);

    // Ensure all required fields exist
    if (
      !result.mapping?.date ||
      !result.mapping?.ticker ||
      !result.mapping?.action ||
      !result.mapping?.quantity ||
      !result.mapping?.price
    ) {
      return NextResponse.json(
        {
          ...result,
          confidence: "low",
        },
        { status: 200 }
      );
    }

    // Verify mapped headers actually exist in the CSV
    const headerSet = new Set(headers);
    for (const [field, headerName] of Object.entries(result.mapping)) {
      if (!headerSet.has(headerName as string)) {
        // Try case-insensitive match
        const match = headers.find(
          (h: string) =>
            h.toLowerCase() === (headerName as string).toLowerCase()
        );
        if (match) {
          result.mapping[field] = match;
        } else {
          result.confidence = "low";
        }
      }
    }

    return NextResponse.json(result);
  } catch (error) {
    console.error("CSV classification error:", error);
    return NextResponse.json(
      { error: "Failed to classify CSV columns" },
      { status: 500 }
    );
  }
}
