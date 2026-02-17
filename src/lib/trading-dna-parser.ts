/**
 * CSV parser for Trading DNA page.
 * Auto-detects brokerage format, normalizes to standard schema for /analyze endpoint.
 */

export interface StandardTrade {
  trader_id: string;
  ticker: string;
  action: "BUY" | "SELL";
  quantity: number;
  price: number;
  date: string;
  fees: number;
}

export interface ParseResult {
  trades: StandardTrade[];
  detectedFormat: string;
  rowsFiltered: number;
  errors: string[];
}

export interface ColumnMapping {
  date: string;
  ticker: string;
  action: string;
  quantity: string;
  price: string;
  fees?: string;
}

interface BrokerageFormat {
  name: string;
  detect: (headers: string[]) => boolean;
  mapping: ColumnMapping;
  actionMap?: Record<string, "BUY" | "SELL">;
  filterRow?: (row: Record<string, string>) => boolean;
}

const BROKERAGE_FORMATS: BrokerageFormat[] = [
  {
    name: "Trading212",
    detect: (h) =>
      h.some((c) => c.includes("Ticker")) &&
      h.some((c) => c.includes("Type")) &&
      (h.some((c) => c.includes("Price / share")) || h.some((c) => c.includes("Price per share"))),
    mapping: {
      date: "Time",
      ticker: "Ticker",
      action: "Type",
      quantity: "No. of shares",
      price: "Price / share",
      fees: "Currency conversion fee",
    },
    actionMap: {
      "Market buy": "BUY", "Market sell": "SELL",
      "Limit buy": "BUY", "Limit sell": "SELL",
      Buy: "BUY", Sell: "SELL",
    },
    filterRow: (row) => {
      const type = (row["Type"] || "").toLowerCase();
      return !type.includes("dividend") && !type.includes("deposit") &&
        !type.includes("withdrawal") && !type.includes("interest") &&
        !type.includes("fee") && !type.includes("transfer");
    },
  },
  {
    name: "Robinhood",
    detect: (h) =>
      h.some((c) => c.includes("Activity Date")) &&
      h.some((c) => c.includes("Trans Code")),
    mapping: {
      date: "Activity Date", ticker: "Instrument",
      action: "Trans Code", quantity: "Quantity", price: "Price",
    },
    actionMap: { Buy: "BUY", Sell: "SELL", BUY: "BUY", SELL: "SELL" },
    filterRow: (row) => {
      const code = (row["Trans Code"] || "").toUpperCase();
      return code === "BUY" || code === "SELL";
    },
  },
  {
    name: "Interactive Brokers",
    detect: (h) =>
      h.some((c) => c.includes("Symbol")) &&
      h.some((c) => c.includes("Buy/Sell") || c.includes("B/S")),
    mapping: {
      date: "Date/Time", ticker: "Symbol",
      action: "Buy/Sell", quantity: "Quantity",
      price: "T. Price", fees: "Comm/Fee",
    },
    actionMap: { BOT: "BUY", SLD: "SELL", BUY: "BUY", SELL: "SELL", B: "BUY", S: "SELL" },
  },
  {
    name: "Schwab",
    detect: (h) =>
      h.some((c) => c === "Action" || c === "action") &&
      h.some((c) => c === "Symbol" || c === "symbol") &&
      h.some((c) => c.includes("Fees")),
    mapping: {
      date: "Date", ticker: "Symbol", action: "Action",
      quantity: "Quantity", price: "Price", fees: "Fees & Comm",
    },
    actionMap: { Buy: "BUY", Sell: "SELL", "Buy to Open": "BUY", "Sell to Close": "SELL" },
    filterRow: (row) => {
      const action = (row["Action"] || "").toLowerCase();
      return action.includes("buy") || action.includes("sell");
    },
  },
  {
    name: "Fidelity",
    detect: (h) =>
      h.some((c) => c.includes("Run Date")) &&
      h.some((c) => c.includes("Commission")),
    mapping: {
      date: "Run Date", ticker: "Symbol", action: "Action",
      quantity: "Quantity", price: "Price", fees: "Commission",
    },
    actionMap: {
      "YOU BOUGHT": "BUY", "YOU SOLD": "SELL",
      BOUGHT: "BUY", SOLD: "SELL", Buy: "BUY", Sell: "SELL",
    },
    filterRow: (row) => {
      const action = (row["Action"] || "").toUpperCase();
      return action.includes("BOUGHT") || action.includes("SOLD") ||
        action.includes("BUY") || action.includes("SELL");
    },
  },
];

function parseLine(line: string, delimiter: string): string[] {
  const result: string[] = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') { current += '"'; i++; }
      else inQuotes = !inQuotes;
    } else if (char === delimiter && !inQuotes) {
      result.push(current); current = "";
    } else { current += char; }
  }
  result.push(current);
  return result;
}

function parseCSVText(text: string): { headers: string[]; rows: Record<string, string>[] } {
  const cleaned = text.replace(/^\uFEFF/, "");
  const lines = cleaned.trim().split(/\r?\n/);
  if (lines.length < 2) return { headers: [], rows: [] };
  const delimiter = lines[0].includes("\t") ? "\t" : ",";
  const headers = parseLine(lines[0], delimiter).map((h) => h.trim());
  const rows: Record<string, string>[] = [];
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    const values = parseLine(line, delimiter);
    const row: Record<string, string> = {};
    headers.forEach((h, idx) => { row[h] = (values[idx] || "").trim(); });
    rows.push(row);
  }
  return { headers, rows };
}

function findColumn(headers: string[], ...patterns: string[]): string | null {
  for (const p of patterns) {
    const lower = p.toLowerCase();
    const match = headers.find((h) => h.toLowerCase().includes(lower));
    if (match) return match;
  }
  return null;
}

function parseDate(dateStr: string): string | null {
  if (!dateStr) return null;
  const iso = dateStr.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;
  const mdy = dateStr.match(/(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (mdy) return `${mdy[3]}-${mdy[1].padStart(2, "0")}-${mdy[2].padStart(2, "0")}`;
  const d = new Date(dateStr);
  if (!isNaN(d.getTime())) return d.toISOString().split("T")[0];
  return null;
}

function parseNumber(str: string): number {
  if (!str) return 0;
  const cleaned = str.replace(/[$,\s]/g, "").replace(/\(([^)]+)\)/, "-$1");
  const num = parseFloat(cleaned);
  return isNaN(num) ? 0 : num;
}

function normalizeAction(
  raw: string, actionMap?: Record<string, "BUY" | "SELL">
): "BUY" | "SELL" | null {
  if (!raw) return null;
  const trimmed = raw.trim();
  if (actionMap) {
    if (actionMap[trimmed]) return actionMap[trimmed];
    const upper = trimmed.toUpperCase();
    for (const [key, val] of Object.entries(actionMap)) {
      if (key.toUpperCase() === upper) return val;
    }
  }
  const lower = trimmed.toLowerCase();
  if (lower === "buy" || lower.includes("buy") || lower === "bot" || lower === "b") return "BUY";
  if (lower === "sell" || lower.includes("sell") || lower === "sld" || lower === "s") return "SELL";
  return null;
}

export function detectFormat(text: string): {
  format: string | null;
  headers: string[];
  sampleRows: Record<string, string>[];
} {
  const { headers, rows } = parseCSVText(text);
  for (const fmt of BROKERAGE_FORMATS) {
    if (fmt.detect(headers)) {
      return { format: fmt.name, headers, sampleRows: rows.slice(0, 5) };
    }
  }
  return { format: null, headers, sampleRows: rows.slice(0, 5) };
}

function parseWithMapping(
  text: string, mapping: ColumnMapping,
  actionMap?: Record<string, "BUY" | "SELL">,
  filterFn?: (row: Record<string, string>) => boolean,
  formatName?: string,
): ParseResult {
  const { rows } = parseCSVText(text);
  const trades: StandardTrade[] = [];
  const errors: string[] = [];
  let filtered = 0;
  const seen = new Set<string>();

  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    if (filterFn && !filterFn(row)) { filtered++; continue; }

    const dateStr = row[mapping.date];
    const ticker = (row[mapping.ticker] || "").replace(/[^A-Za-z0-9.]/g, "").toUpperCase();
    const actionRaw = row[mapping.action];
    const quantity = Math.abs(parseNumber(row[mapping.quantity]));
    const price = Math.abs(parseNumber(row[mapping.price]));
    const fees = mapping.fees ? Math.abs(parseNumber(row[mapping.fees] || "0")) : 0;

    if (!ticker || !quantity || !price) { filtered++; continue; }

    const date = parseDate(dateStr);
    if (!date) { errors.push(`Row ${i + 2}: Could not parse date "${dateStr}"`); continue; }

    const action = normalizeAction(actionRaw, actionMap);
    if (!action) { filtered++; continue; }

    const key = `${date}|${ticker}|${action}|${quantity}|${price}`;
    if (seen.has(key)) { filtered++; continue; }
    seen.add(key);

    trades.push({
      trader_id: "user", ticker, action,
      quantity: Math.round(quantity * 10000) / 10000,
      price: Math.round(price * 100) / 100,
      date, fees: Math.round(fees * 100) / 100,
    });
  }

  trades.sort((a, b) => a.date.localeCompare(b.date));
  return { trades, detectedFormat: formatName || "custom", rowsFiltered: filtered, errors };
}

export function autoParseCSV(text: string): ParseResult {
  const { headers } = parseCSVText(text);

  for (const fmt of BROKERAGE_FORMATS) {
    if (fmt.detect(headers)) {
      const mapping = { ...fmt.mapping };
      // Fuzzy match headers
      for (const [key, pattern] of Object.entries(mapping)) {
        if (!headers.includes(pattern)) {
          const fuzzy = headers.find((h) =>
            h.toLowerCase().replace(/\s+/g, "") === pattern.toLowerCase().replace(/\s+/g, "")
          );
          if (fuzzy) (mapping as Record<string, string>)[key] = fuzzy;
        }
      }
      return parseWithMapping(text, mapping, fmt.actionMap, fmt.filterRow, fmt.name);
    }
  }

  // Generic fallback
  const dateCol = findColumn(headers, "date", "time", "run date", "activity date");
  const tickerCol = findColumn(headers, "ticker", "symbol", "instrument", "stock");
  const actionCol = findColumn(headers, "action", "type", "side", "trans code", "buy/sell");
  const qtyCol = findColumn(headers, "quantity", "qty", "shares", "no. of shares");
  const priceCol = findColumn(headers, "price", "price per share", "t. price", "fill price");
  const feesCol = findColumn(headers, "fees", "commission", "comm", "fee");

  if (dateCol && tickerCol && actionCol && qtyCol && priceCol) {
    return parseWithMapping(text, {
      date: dateCol, ticker: tickerCol, action: actionCol,
      quantity: qtyCol, price: priceCol, fees: feesCol || undefined,
    }, undefined, undefined, "Generic (auto-detected)");
  }

  return {
    trades: [], detectedFormat: "unknown",
    rowsFiltered: 0, errors: ["Could not auto-detect CSV format. Please map columns manually."],
  };
}

export function manualParseCSV(text: string, mapping: ColumnMapping): ParseResult {
  return parseWithMapping(text, mapping, undefined, undefined, "Manual mapping");
}

export function tradesToCSVBlob(trades: StandardTrade[]): Blob {
  const header = "trader_id,ticker,action,quantity,price,date,fees";
  const lines = trades.map(
    (t) => `${t.trader_id},${t.ticker},${t.action},${t.quantity},${t.price},${t.date},${t.fees}`
  );
  return new Blob([header + "\n" + lines.join("\n")], { type: "text/csv" });
}
