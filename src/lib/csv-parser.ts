import { ImportedTrade, ColumnMapping } from "@/types";
import { getSector } from "./sector-map";

// Strip BOM marker if present
function stripBom(text: string): string {
  if (text.charCodeAt(0) === 0xfeff) return text.slice(1);
  return text;
}

// Parse a single CSV line respecting quoted fields
function parseCsvLine(line: string): string[] {
  const fields: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQuotes) {
      if (ch === '"') {
        if (i + 1 < line.length && line[i + 1] === '"') {
          current += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        current += ch;
      }
    } else {
      if (ch === '"') {
        inQuotes = true;
      } else if (ch === ",") {
        fields.push(current.trim());
        current = "";
      } else {
        current += ch;
      }
    }
  }
  fields.push(current.trim());
  return fields;
}

// Clean numeric values: remove $, commas, parentheses (negative)
function cleanNumeric(val: string): number {
  if (!val || val === "-" || val === "" || val === "N/A") return 0;
  let cleaned = val.replace(/[$,\s]/g, "");
  // Handle parentheses for negative: (123.45) -> -123.45
  if (cleaned.startsWith("(") && cleaned.endsWith(")")) {
    cleaned = "-" + cleaned.slice(1, -1);
  }
  const num = parseFloat(cleaned);
  return isNaN(num) ? 0 : num;
}

// Parse various date formats into YYYY-MM-DD
function parseDate(val: string): string {
  if (!val) return "";
  const trimmed = val.trim();

  // Already YYYY-MM-DD
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return trimmed;

  // MM/DD/YYYY or M/D/YYYY
  const slashFull = trimmed.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (slashFull) {
    const [, m, d, y] = slashFull;
    return `${y}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`;
  }

  // M/D/YY
  const slashShort = trimmed.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2})$/);
  if (slashShort) {
    const [, m, d, y] = slashShort;
    const fullYear = parseInt(y) > 50 ? `19${y}` : `20${y}`;
    return `${fullYear}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`;
  }

  // MM-DD-YYYY
  const dashMDY = trimmed.match(/^(\d{1,2})-(\d{1,2})-(\d{4})$/);
  if (dashMDY) {
    const [, m, d, y] = dashMDY;
    return `${y}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`;
  }

  // Try native Date parse as last resort
  const d = new Date(trimmed);
  if (!isNaN(d.getTime())) {
    return d.toISOString().split("T")[0];
  }

  return trimmed;
}

// Detect action from string
function parseAction(val: string): "buy" | "sell" {
  const lower = val.toLowerCase().trim();
  if (
    lower.includes("sell") ||
    lower.includes("sold") ||
    lower === "s" ||
    lower.includes("redemption") ||
    lower.includes("withdraw")
  ) {
    return "sell";
  }
  return "buy";
}

// Auto-detect column mapping from headers
const HEADER_PATTERNS: Record<keyof ColumnMapping, RegExp[]> = {
  date: [/date/i, /trade.?date/i, /settlement/i, /time/i, /executed/i],
  ticker: [/symbol/i, /ticker/i, /stock/i, /security/i, /instrument/i],
  action: [/action/i, /type/i, /side/i, /trans/i, /buy.?sell/i, /direction/i],
  quantity: [/quantity/i, /qty/i, /shares/i, /units/i, /amount/i, /volume/i],
  price: [/price/i, /cost/i, /fill/i, /execution/i, /avg/i],
  total: [/total/i, /net.?amount/i, /proceeds/i, /value/i, /settlement.?amount/i],
};

export function autoDetectColumns(headers: string[]): Partial<ColumnMapping> {
  const mapping: Partial<ColumnMapping> = {};
  const lowerHeaders = headers.map((h) => h.toLowerCase().trim());

  for (const [field, patterns] of Object.entries(HEADER_PATTERNS) as [
    keyof ColumnMapping,
    RegExp[],
  ][]) {
    for (const pattern of patterns) {
      const idx = lowerHeaders.findIndex((h) => pattern.test(h));
      if (idx !== -1 && !Object.values(mapping).includes(headers[idx])) {
        mapping[field] = headers[idx];
        break;
      }
    }
  }

  return mapping;
}

export interface ParseResult {
  headers: string[];
  rows: string[][];
  preview: string[][];
}

// Parse raw CSV text into headers and rows
export function parseCsvText(text: string): ParseResult {
  const cleaned = stripBom(text);
  const lines = cleaned.split(/\r?\n/).filter((line) => line.trim() !== "");

  if (lines.length === 0) {
    return { headers: [], rows: [], preview: [] };
  }

  const headers = parseCsvLine(lines[0]);
  const rows = lines.slice(1).map(parseCsvLine);
  // Filter out rows that are entirely empty
  const validRows = rows.filter((row) => row.some((cell) => cell !== ""));
  const preview = validRows.slice(0, 5);

  return { headers, rows: validRows, preview };
}

// Convert parsed rows to ImportedTrade objects using column mapping
export function mapToTrades(
  rows: string[][],
  headers: string[],
  mapping: ColumnMapping,
): ImportedTrade[] {
  const getIndex = (col: string) => headers.indexOf(col);
  const dateIdx = getIndex(mapping.date);
  const tickerIdx = getIndex(mapping.ticker);
  const actionIdx = getIndex(mapping.action);
  const qtyIdx = getIndex(mapping.quantity);
  const priceIdx = getIndex(mapping.price);
  const totalIdx = getIndex(mapping.total);

  return rows
    .map((row) => {
      const ticker = tickerIdx >= 0 ? row[tickerIdx]?.toUpperCase().trim() : "";
      if (!ticker) return null;

      const quantity = qtyIdx >= 0 ? Math.abs(cleanNumeric(row[qtyIdx])) : 0;
      const price = priceIdx >= 0 ? cleanNumeric(row[priceIdx]) : 0;
      const rawTotal = totalIdx >= 0 ? cleanNumeric(row[totalIdx]) : 0;
      const total = rawTotal !== 0 ? Math.abs(rawTotal) : quantity * price;

      return {
        date: dateIdx >= 0 ? parseDate(row[dateIdx]) : "",
        ticker,
        action: actionIdx >= 0 ? parseAction(row[actionIdx]) : "buy",
        quantity,
        price: Math.abs(price),
        total,
        sector: getSector(ticker),
      } as ImportedTrade;
    })
    .filter((t): t is ImportedTrade => t !== null && t.ticker !== "" && t.quantity > 0);
}
