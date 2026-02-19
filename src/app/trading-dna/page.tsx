"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import Link from "next/link";
import { Upload, AlertCircle, ArrowLeft, RotateCcw, ChevronDown, FlaskConical } from "lucide-react";
import {
  autoParseCSV,
  manualParseCSV,
  parseWithClaudeMapping,
  detectFormat,
  tradesToCSVBlob,
  getClassificationPayload,
} from "@/lib/trading-dna-parser";
import type { StandardTrade, ColumnMapping, ClaudeClassification } from "@/lib/trading-dna-parser";
import { JURISDICTIONS } from "@/lib/jurisdictions";

const BEHAVIORAL_MIRROR_URL = "https://yabo-production.up.railway.app";

const PROCESSING_MESSAGES = [
  "Reading your trade history...",
  "Analyzing entry patterns...",
  "Mapping exit behavior...",
  "Computing risk profile...",
  "Evaluating tax efficiency...",
  "Generating your Trading DNA...",
];

interface NarrativeResult {
  headline: string;
  archetype_summary: string;
  behavioral_deep_dive: string;
  risk_personality: string;
  tax_efficiency: string | null;
  regulatory_context: string | null;
  key_recommendation: string;
  confidence_note: string;
}

interface SampleMeta {
  traderId: string;
  tradeCount?: number;
  tradingPeriod?: string;
  taxJurisdiction?: string;
  archetype?: string;
}

interface DebugInfo {
  format?: string;
  totalRows?: number;
  tradeCount?: number;
  filtered?: number;
  sampleId?: string;
  sampleArchetype?: string;
}

type Phase = "upload" | "processing" | "display" | "column-mapper";

export default function TradingDNAPage() {
  const [phase, setPhase] = useState<Phase>("upload");
  const [error, setError] = useState<string | null>(null);
  const [narrative, setNarrative] = useState<NarrativeResult | null>(null);
  const [sampleMeta, setSampleMeta] = useState<SampleMeta | null>(null);

  // Upload state
  const [isDragging, setIsDragging] = useState(false);
  const [csvText, setCsvText] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [parsedTrades, setParsedTrades] = useState<StandardTrade[]>([]);
  const [detectedFormat, setDetectedFormat] = useState<string | null>(null);
  const [classifying, setClassifying] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Context inputs
  const [jurisdiction, setJurisdiction] = useState("");
  const [jurisdictionSearch, setJurisdictionSearch] = useState("");
  const [jurisdictionOpen, setJurisdictionOpen] = useState(false);
  const [portfolioPct, setPortfolioPct] = useState(50);
  const [accountSize, setAccountSize] = useState("");

  // Column mapper state
  const [csvHeaders, setCsvHeaders] = useState<string[]>([]);
  const [sampleRows, setSampleRows] = useState<Record<string, string>[]>([]);
  const [manualMapping, setManualMapping] = useState<Partial<ColumnMapping>>({});

  // Debug
  const [debugMode, setDebugMode] = useState(false);
  const [debugInfo, setDebugInfo] = useState<DebugInfo>({});

  // Sample trader dedup
  const lastSampleIdRef = useRef<string | null>(null);

  // Processing message rotation
  const [messageIdx, setMessageIdx] = useState(0);
  useEffect(() => {
    if (phase !== "processing") return;
    const interval = setInterval(() => {
      setMessageIdx((prev) => (prev + 1) % PROCESSING_MESSAGES.length);
    }, 3500);
    return () => clearInterval(interval);
  }, [phase]);

  // Check for ?debug=true on mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setDebugMode(params.has("debug"));
  }, []);

  const filteredJurisdictions = JURISDICTIONS.filter((j) =>
    j.label.toLowerCase().includes(jurisdictionSearch.toLowerCase()) ||
    j.code.toLowerCase().includes(jurisdictionSearch.toLowerCase())
  );

  // ─── Claude CSV classification (Layer 2) ───
  const classifyWithClaude = useCallback(async (text: string): Promise<ClaudeClassification | null> => {
    try {
      setClassifying(true);
      console.log("[DNA Page] Calling Claude CSV classifier...");
      const payload = getClassificationPayload(text);
      const res = await fetch("/api/classify-csv", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        console.log("[DNA Page] Claude classifier failed:", res.status);
        return null;
      }
      const data: ClaudeClassification = await res.json();
      console.log("[DNA Page] Claude classification result:", data);
      if (data.confidence === "low") return data; // return for prefill but don't auto-use
      return data;
    } catch (err) {
      console.log("[DNA Page] Claude classifier error:", err);
      return null;
    } finally {
      setClassifying(false);
    }
  }, []);

  const handleFile = useCallback(async (file: File) => {
    setError(null);
    setSampleMeta(null);
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Please upload a CSV file.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("File too large. Maximum size is 10MB.");
      return;
    }
    setFileName(file.name);
    const text = await file.text();
    if (!text || text.trim().length === 0) {
      setError("File appears to be empty.");
      return;
    }
    setCsvText(text);
    console.log(`[DNA Page] File loaded: ${file.name} (${text.length} chars)`);

    // Layer 1: Try auto-parse (pattern match + generic fallback)
    const result = autoParseCSV(text);
    setDebugInfo({
      format: result.detectedFormat,
      totalRows: text.trim().split("\n").length - 1,
      tradeCount: result.trades.length,
      filtered: result.rowsFiltered,
    });

    if (result.trades.length >= 5) {
      console.log(`[DNA Page] Auto-parse succeeded: ${result.trades.length} trades (${result.detectedFormat})`);
      setParsedTrades(result.trades);
      setDetectedFormat(result.detectedFormat);
      return;
    }

    console.log(`[DNA Page] Auto-parse got ${result.trades.length} trades, trying Claude...`);

    // Layer 2: Claude fallback
    const classification = await classifyWithClaude(text);
    if (classification && classification.confidence !== "low") {
      const claudeResult = parseWithClaudeMapping(text, classification);
      setDebugInfo((prev) => ({
        ...prev,
        format: claudeResult.detectedFormat,
        tradeCount: claudeResult.trades.length,
        filtered: claudeResult.rowsFiltered,
      }));
      if (claudeResult.trades.length >= 5) {
        console.log(`[DNA Page] Claude parse succeeded: ${claudeResult.trades.length} trades`);
        setParsedTrades(claudeResult.trades);
        setDetectedFormat(claudeResult.detectedFormat);
        return;
      }
    }

    // Layer 3: Manual mapper
    console.log("[DNA Page] Falling back to manual mapper");
    const detected = detectFormat(text);
    setCsvHeaders(detected.headers);
    setSampleRows(detected.sampleRows);

    // Pre-fill manual mapper with Claude's best guesses
    if (classification?.mapping) {
      setManualMapping({
        date: detected.headers.includes(classification.mapping.date) ? classification.mapping.date : undefined,
        ticker: detected.headers.includes(classification.mapping.ticker) ? classification.mapping.ticker : undefined,
        action: detected.headers.includes(classification.mapping.action) ? classification.mapping.action : undefined,
        quantity: detected.headers.includes(classification.mapping.quantity) ? classification.mapping.quantity : undefined,
        price: detected.headers.includes(classification.mapping.price) ? classification.mapping.price : undefined,
      });
    }

    if (result.trades.length > 0 && result.trades.length < 5) {
      setError(`Only ${result.trades.length} trades found. We need at least 5 for a meaningful analysis.`);
    }
    setPhase("column-mapper");
  }, [classifyWithClaude]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const handleManualMap = () => {
    if (!csvText || !manualMapping.date || !manualMapping.ticker || !manualMapping.action || !manualMapping.quantity || !manualMapping.price) {
      setError("Please map all required columns.");
      return;
    }
    const result = manualParseCSV(csvText, manualMapping as ColumnMapping);
    if (result.trades.length < 5) {
      setError(`Only ${result.trades.length} trades found after mapping. We need at least 5.`);
      return;
    }
    setParsedTrades(result.trades);
    setDetectedFormat("Manual mapping");
    setDebugInfo((prev) => ({
      ...prev,
      format: "Manual mapping",
      tradeCount: result.trades.length,
      filtered: result.rowsFiltered,
    }));
    setPhase("upload");
  };

  const handleAnalyze = async () => {
    if (parsedTrades.length < 5) {
      setError("We need at least 5 trades to generate a meaningful analysis.");
      return;
    }

    setPhase("processing");
    setError(null);
    setMessageIdx(0);

    const startTime = Date.now();
    try {
      const csvBlob = tradesToCSVBlob(parsedTrades);
      const formData = new FormData();
      formData.append("file", csvBlob, "trades.csv");

      const context: Record<string, unknown> = {};
      if (jurisdiction) context.tax_jurisdiction = jurisdiction;
      if (portfolioPct !== 50) context.portfolio_pct_of_net_worth = portfolioPct;
      if (accountSize) context.account_size = parseFloat(accountSize.replace(/[,$]/g, ""));
      if (Object.keys(context).length > 0) {
        formData.append("context", JSON.stringify(context));
      }

      console.log(`[DNA Page] Sending /analyze: ${parsedTrades.length} trades, CSV size=${csvBlob.size}, context=`, context);

      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 60000);

      const res = await fetch(`${BEHAVIORAL_MIRROR_URL}/analyze`, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });
      clearTimeout(timeout);

      const elapsed = Date.now() - startTime;
      console.log(`[DNA Page] /analyze response: ${res.status} in ${elapsed}ms`);

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        console.log("[DNA Page] /analyze error body:", body);
        throw new Error(body?.error || `Analysis failed (${res.status}). Please try again.`);
      }

      const data = await res.json();
      console.log(`[DNA Page] /analyze success: narrative keys =`, Object.keys(data.narrative || {}));
      setNarrative(data.narrative);
      setPhase("display");
    } catch (err: unknown) {
      const elapsed = Date.now() - startTime;
      console.log(`[DNA Page] /analyze failed after ${elapsed}ms:`, err);
      if (err instanceof DOMException && err.name === "AbortError") {
        setError("Request timed out. The analysis service may be busy. Please try again.");
      } else if (err instanceof TypeError && err.message.includes("fetch")) {
        setError("Unable to reach analysis service. Please check your connection.");
      } else {
        setError(err instanceof Error ? err.message : "Analysis failed. Please try again.");
      }
      setPhase("upload");
    }
  };

  // ─── Sample Trader ───
  const handleSampleTrader = async () => {
    setPhase("processing");
    setError(null);
    setMessageIdx(0);
    setSampleMeta(null);

    try {
      // Fetch all narratives
      console.log("[DNA Page] Fetching /traders/narratives/all...");
      const res = await fetch(`${BEHAVIORAL_MIRROR_URL}/traders/narratives/all`);
      if (!res.ok) throw new Error("narratives-all-failed");

      const data = await res.json();
      const traderIds = Object.keys(data.traders || {});
      console.log(`[DNA Page] Available traders (${traderIds.length}):`, traderIds);

      if (traderIds.length === 0) throw new Error("No sample profiles available.");

      // Pick a random trader, avoiding the last one shown (retry up to 3 times)
      let randomId = traderIds[Math.floor(Math.random() * traderIds.length)];
      if (traderIds.length > 1) {
        for (let attempt = 0; attempt < 3; attempt++) {
          if (randomId !== lastSampleIdRef.current) break;
          randomId = traderIds[Math.floor(Math.random() * traderIds.length)];
        }
      }
      lastSampleIdRef.current = randomId;
      console.log(`[DNA Page] Selected trader: ${randomId}`);

      const traderNarrative = data.traders[randomId];

      // Try to fetch full profile for extra metadata
      let meta: SampleMeta = { traderId: randomId };
      try {
        const profileRes = await fetch(`${BEHAVIORAL_MIRROR_URL}/traders/${randomId}/full_profile`);
        if (profileRes.ok) {
          const profile = await profileRes.json();
          const cls = profile.classification || {};
          meta = {
            traderId: randomId,
            tradeCount: cls.trade_count,
            tradingPeriod: cls.trading_period,
            taxJurisdiction: cls.tax_jurisdiction,
            archetype: cls.primary_archetype,
          };
          console.log("[DNA Page] Trader metadata:", meta);
        }
      } catch {
        // Metadata is optional, continue without it
      }

      setDebugInfo({ sampleId: randomId, sampleArchetype: meta.archetype });
      setSampleMeta(meta);
      setNarrative(traderNarrative);
      console.log(`[DNA Page] Narrative loaded: ${JSON.stringify(traderNarrative).length} chars`);
      setPhase("display");
    } catch (err) {
      console.log("[DNA Page] /traders/narratives/all failed", err);
      setError(err instanceof Error && err.message !== "narratives-all-failed"
        ? err.message
        : "Could not load sample profiles. The analysis service may be starting up.");
      setPhase("upload");
    }
  };

  const handleReset = () => {
    setPhase("upload");
    setError(null);
    setNarrative(null);
    setSampleMeta(null);
    setCsvText(null);
    setFileName(null);
    setParsedTrades([]);
    setDetectedFormat(null);
    setCsvHeaders([]);
    setSampleRows([]);
    setManualMapping({});
    setJurisdiction("");
    setJurisdictionSearch("");
    setPortfolioPct(50);
    setAccountSize("");
    setClassifying(false);
    setDebugInfo({});
    if (inputRef.current) inputRef.current.value = "";
  };

  // ─── Debug Banner ───
  const DebugBanner = () => {
    if (!debugMode) return null;
    const parts: string[] = [];
    if (debugInfo.format) parts.push(`Format: ${debugInfo.format}`);
    if (debugInfo.totalRows !== undefined) parts.push(`Rows: ${debugInfo.totalRows}`);
    if (debugInfo.tradeCount !== undefined) parts.push(`Trades: ${debugInfo.tradeCount}`);
    if (debugInfo.filtered !== undefined) parts.push(`Filtered: ${debugInfo.filtered}`);
    if (debugInfo.sampleId) parts.push(`Sample: ${debugInfo.sampleId}`);
    if (debugInfo.sampleArchetype) parts.push(`Archetype: ${debugInfo.sampleArchetype}`);
    if (parts.length === 0) parts.push("No data yet");
    return (
      <div className="fixed bottom-0 left-0 right-0 z-[9999] bg-black/90 text-green-400 text-xs font-mono px-4 py-2 print:hidden">
        {parts.join(" | ")}
      </div>
    );
  };

  // ─── PHASE 1: UPLOAD ───
  if (phase === "upload" || phase === "column-mapper") {
    const showMapper = phase === "column-mapper";
    const showReadyState = parsedTrades.length >= 5;

    return (
      <div className="min-h-screen bg-bg">
        {/* Nav bar */}
        <nav className="border-b border-border">
          <div className="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2 text-text-sec hover:text-text transition-colors">
              <ArrowLeft className="w-4 h-4" />
              <span className="font-display text-lg font-semibold text-text">Yabo</span>
            </Link>
          </div>
        </nav>

        <div className="max-w-2xl mx-auto px-6 pt-16 pb-24">
          {/* Header */}
          <div className="text-center mb-12" style={{ animation: "fade-up 0.5s ease-out both" }}>
            <h1 className="font-display text-4xl md:text-5xl font-medium text-text mb-4">
              Discover Your Trading DNA
            </h1>
            <p className="font-body text-lg text-text-sec max-w-lg mx-auto">
              Upload your trade history and let the Behavioral Mirror show you how you really trade.
            </p>
            <p className="font-body text-xs text-text-ter mt-3">
              Your data is analyzed in real-time and never stored.
            </p>
          </div>

          {/* CSV Upload Zone */}
          <div className="mb-6" style={{ animation: "fade-up 0.5s ease-out 0.1s both" }}>
            <div
              onDrop={handleDrop}
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={(e) => { e.preventDefault(); setIsDragging(false); }}
              onClick={() => !showReadyState && !classifying && inputRef.current?.click()}
              className={`
                relative border-2 border-dashed rounded-xl
                flex flex-col items-center justify-center gap-4 transition-all duration-200
                ${showReadyState ? "p-8" : "p-12 cursor-pointer"}
                ${classifying ? "pointer-events-none opacity-70" : ""}
                ${isDragging
                  ? "border-teal bg-teal-light scale-[1.01]"
                  : showReadyState
                    ? "border-teal/40 bg-teal-muted"
                    : "border-border hover:border-text-ter hover:bg-surface-hover"
                }
              `}
            >
              <input
                ref={inputRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
              />
              {classifying ? (
                <div className="text-center py-2">
                  <div className="w-48 h-px mx-auto mb-4 relative overflow-hidden">
                    <div
                      className="absolute inset-0"
                      style={{
                        background: "linear-gradient(90deg, transparent 0%, #9A7B5B 50%, transparent 100%)",
                        animation: "pulse-dot 2s ease-in-out infinite",
                      }}
                    />
                  </div>
                  <p className="text-sm font-body text-text-sec">Analyzing your file format...</p>
                </div>
              ) : showReadyState ? (
                <>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-teal/15 flex items-center justify-center">
                      <Upload className="w-5 h-5 text-teal" />
                    </div>
                    <div className="text-left">
                      <p className="text-sm font-semibold text-text font-body">{fileName}</p>
                      <p className="text-xs text-text-sec font-body">
                        {parsedTrades.length} trades detected
                        {detectedFormat && detectedFormat !== "unknown" ? ` (${detectedFormat} format)` : ""}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleReset(); }}
                    className="text-xs text-text-ter hover:text-text-sec font-body underline"
                  >
                    Choose a different file
                  </button>
                </>
              ) : (
                <>
                  <div className={`w-14 h-14 rounded-full flex items-center justify-center transition-colors ${isDragging ? "bg-teal/20" : "bg-surface-hover"}`}>
                    <Upload className={`w-6 h-6 ${isDragging ? "text-teal" : "text-text-ter"}`} />
                  </div>
                  <div className="text-center">
                    <p className="text-sm font-semibold text-text font-body">
                      Drop your trade history CSV here, or click to browse
                    </p>
                    <p className="text-xs text-text-ter mt-1 font-body">
                      Works with most brokerages. We&apos;ll figure out the format.
                    </p>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Sample Trader Divider + Button */}
          {!showReadyState && !showMapper && !classifying && (
            <div className="mb-10" style={{ animation: "fade-up 0.5s ease-out 0.15s both" }}>
              <div className="flex items-center gap-4 mb-5">
                <div className="flex-1 h-px bg-border" />
                <span className="text-xs font-body text-text-ter uppercase tracking-wider">or</span>
                <div className="flex-1 h-px bg-border" />
              </div>
              <button
                onClick={handleSampleTrader}
                className="w-full flex items-center justify-center gap-2.5 py-3 rounded-[10px] border border-border text-sm font-body font-medium text-text-sec hover:text-text hover:border-text-ter hover:bg-surface-hover transition-all"
              >
                <FlaskConical className="w-4 h-4" />
                Explore a Sample Profile
              </button>
            </div>
          )}

          {/* Column Mapper */}
          {showMapper && (
            <div className="mb-10 p-6 rounded-xl border border-border bg-surface" style={{ animation: "fade-up 0.5s ease-out both" }}>
              <h3 className="font-display text-lg font-medium text-text mb-1">Map Your Columns</h3>
              <p className="text-xs text-text-sec font-body mb-5">
                We couldn&apos;t auto-detect your CSV format. Please tell us which column is which.
              </p>

              {/* Sample data preview */}
              {sampleRows.length > 0 && (
                <div className="overflow-x-auto mb-5 rounded-lg border border-border">
                  <table className="text-xs font-mono w-full">
                    <thead>
                      <tr className="bg-surface-hover">
                        {csvHeaders.map((h) => (
                          <th key={h} className="px-3 py-2 text-left text-text-sec font-medium whitespace-nowrap">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {sampleRows.slice(0, 3).map((row, i) => (
                        <tr key={i} className="border-t border-border">
                          {csvHeaders.map((h) => (
                            <td key={h} className="px-3 py-1.5 text-text-sec whitespace-nowrap">{row[h]?.slice(0, 20)}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Column dropdowns */}
              <div className="grid grid-cols-2 gap-3 mb-4">
                {(["date", "ticker", "action", "quantity", "price"] as const).map((field) => (
                  <div key={field}>
                    <label className="block text-xs font-body font-medium text-text-sec mb-1 uppercase tracking-wider">
                      {field} *
                    </label>
                    <select
                      value={manualMapping[field] || ""}
                      onChange={(e) => setManualMapping((prev) => ({ ...prev, [field]: e.target.value }))}
                      className="w-full px-3 py-2 rounded-lg border border-border bg-bg text-sm text-text font-body focus:outline-none focus:border-teal"
                    >
                      <option value="">Select column...</option>
                      {csvHeaders.map((h) => (
                        <option key={h} value={h}>{h}</option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>

              {/* Error within mapper */}
              {error && (
                <div className="flex items-start gap-2 px-4 py-3 rounded-lg bg-red-light text-red text-sm font-body mb-4">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              <button
                onClick={() => { setPhase("column-mapper"); handleManualMap(); }}
                className="w-full py-2.5 rounded-[10px] bg-text text-bg font-body font-semibold text-sm hover:bg-text/80 transition-colors"
              >
                Apply Mapping
              </button>
            </div>
          )}

          {/* Context Inputs — always visible in Phase 1 (no animation to prevent re-render flicker) */}
          {!showMapper && (
            <div className="mb-10" key="context-inputs">
              <p className="text-xs font-body font-semibold text-text-sec uppercase tracking-wider mb-4">
                Improve your analysis (optional)
              </p>
              <div className="space-y-4">
                {/* Tax Jurisdiction */}
                <div className="relative">
                  <label className="block text-sm font-body text-text-sec mb-1.5">Tax jurisdiction</label>
                  <button
                    onClick={() => setJurisdictionOpen(!jurisdictionOpen)}
                    className="w-full flex items-center justify-between px-4 py-2.5 rounded-[10px] border border-border bg-bg text-sm font-body text-text hover:border-text-ter transition-colors"
                  >
                    <span className={jurisdiction ? "text-text" : "text-text-ter"}>
                      {jurisdiction ? JURISDICTIONS.find((j) => j.code === jurisdiction)?.label : "Select jurisdiction..."}
                    </span>
                    <ChevronDown className="w-4 h-4 text-text-ter" />
                  </button>
                  {jurisdictionOpen && (
                    <div className="absolute z-50 mt-1 w-full bg-bg border border-border rounded-xl shadow-lg max-h-64 overflow-hidden">
                      <div className="p-2 border-b border-border">
                        <input
                          type="text"
                          value={jurisdictionSearch}
                          onChange={(e) => setJurisdictionSearch(e.target.value)}
                          placeholder="Search..."
                          className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-sm font-body text-text focus:outline-none focus:border-teal"
                          autoFocus
                        />
                      </div>
                      <div className="overflow-y-auto max-h-48">
                        {filteredJurisdictions.map((j) => (
                          <button
                            key={j.code}
                            onClick={() => { setJurisdiction(j.code); setJurisdictionOpen(false); setJurisdictionSearch(""); }}
                            className={`w-full text-left px-4 py-2 text-sm font-body hover:bg-surface-hover transition-colors ${
                              jurisdiction === j.code ? "text-teal font-medium" : "text-text"
                            }`}
                          >
                            {j.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Portfolio % of net worth */}
                <div>
                  <label className="block text-sm font-body text-text-sec mb-1.5">
                    What percentage of your investable net worth does this account represent?
                  </label>
                  <div className="flex items-center gap-4">
                    <input
                      type="range"
                      min={5}
                      max={100}
                      value={portfolioPct}
                      onChange={(e) => setPortfolioPct(Number(e.target.value))}
                      className="flex-1 accent-[#9A7B5B]"
                    />
                    <span className="text-sm font-mono font-medium text-text w-12 text-right">{portfolioPct}%</span>
                  </div>
                </div>

                {/* Account size */}
                <div>
                  <label className="block text-sm font-body text-text-sec mb-1.5">Approximate account value</label>
                  <div className="relative">
                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-text-ter text-sm font-body">$</span>
                    <input
                      type="text"
                      value={accountSize}
                      onChange={(e) => {
                        const v = e.target.value.replace(/[^0-9.,]/g, "");
                        setAccountSize(v);
                      }}
                      placeholder="50,000"
                      className="w-full pl-8 pr-4 py-2.5 rounded-[10px] border border-border bg-bg text-sm font-mono text-text focus:outline-none focus:border-teal"
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Error */}
          {error && !showMapper && (
            <div className="flex items-start gap-2 px-4 py-3 rounded-lg bg-red-light text-red text-sm font-body mb-6">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Submit Button */}
          {showReadyState && (
            <button
              onClick={handleAnalyze}
              className="w-full py-4 rounded-[10px] bg-text text-bg font-display text-lg font-medium hover:bg-text/80 hover:-translate-y-0.5 transition-all"
              style={{ animation: "fade-up 0.5s ease-out both" }}
            >
              Analyze My Trading
            </button>
          )}
        </div>
        <DebugBanner />
      </div>
    );
  }

  // ─── PHASE 2: PROCESSING ───
  if (phase === "processing") {
    return (
      <div className="min-h-screen bg-bg flex flex-col items-center justify-center px-6">
        <div className="text-center" style={{ animation: "fade-in 0.4s ease-out both" }}>
          {/* Pulsing gold line */}
          <div className="w-48 h-px mx-auto mb-10 relative overflow-hidden">
            <div
              className="absolute inset-0"
              style={{
                background: "linear-gradient(90deg, transparent 0%, #9A7B5B 50%, transparent 100%)",
                animation: "pulse-dot 2s ease-in-out infinite",
              }}
            />
          </div>
          <p className="font-display text-xl text-text transition-opacity duration-300" key={messageIdx}>
            {PROCESSING_MESSAGES[messageIdx]}
          </p>
          <p className="font-body text-xs text-text-ter mt-4">This usually takes 15-30 seconds</p>
        </div>
        <DebugBanner />
      </div>
    );
  }

  // ─── PHASE 3: PROFILE DISPLAY ───
  if (phase === "display" && narrative) {
    return (
      <div className="min-h-screen bg-bg">
        {/* Minimal nav */}
        <nav className="border-b border-border print:hidden">
          <div className="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2 text-text-sec hover:text-text transition-colors">
              <ArrowLeft className="w-4 h-4" />
              <span className="font-display text-lg font-semibold text-text">Yabo</span>
            </Link>
            <button
              onClick={handleReset}
              className="flex items-center gap-1.5 text-sm font-body text-text-sec hover:text-text transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              New Analysis
            </button>
          </div>
        </nav>

        {/* Profile document */}
        <article className="max-w-2xl mx-auto px-6 pt-12 pb-24">
          {/* Sample profile banner */}
          {sampleMeta && (
            <div
              className="mb-8 px-5 py-3.5 rounded-lg border border-border bg-surface"
              style={{ animation: "fade-up 0.5s ease-out both" }}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-body font-semibold text-text-ter uppercase tracking-wider mb-1">
                    Sample Profile
                  </p>
                  <p className="text-sm font-body text-text-sec">
                    {sampleMeta.traderId}
                    {sampleMeta.archetype && <span className="text-text-ter"> / {sampleMeta.archetype}</span>}
                  </p>
                </div>
                <div className="text-right">
                  {sampleMeta.tradeCount != null && sampleMeta.tradeCount > 0 && (
                    <p className="text-xs font-mono text-text-ter">{sampleMeta.tradeCount} trades</p>
                  )}
                  {sampleMeta.tradingPeriod && (
                    <p className="text-xs font-mono text-text-ter">{sampleMeta.tradingPeriod}</p>
                  )}
                  {sampleMeta.taxJurisdiction && (
                    <p className="text-xs font-mono text-text-ter">{sampleMeta.taxJurisdiction}</p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Header */}
          <header className="text-center mb-10" style={{ animation: "fade-up 0.5s ease-out both" }}>
            <h1 className="font-display text-2xl md:text-3xl font-medium text-text leading-snug mb-5">
              {narrative.headline}
            </h1>
            <p className="font-display text-base md:text-lg text-text-sec italic leading-relaxed max-w-xl mx-auto">
              {narrative.archetype_summary}
            </p>
            {/* Gold divider */}
            <div className="mt-8 mx-auto w-48 h-px" style={{ background: "linear-gradient(90deg, transparent, #9A7B5B, transparent)" }} />
          </header>

          {/* Sections */}
          <div className="space-y-10">
            {/* Behavioral Analysis */}
            <section style={{ animation: "fade-up 0.5s ease-out 0.1s both" }}>
              <h2 className="font-body text-[11px] font-semibold tracking-[0.15em] uppercase text-text-ter mb-4">
                Behavioral Analysis
              </h2>
              <div className="font-body text-[15px] leading-[1.8] text-text whitespace-pre-line">
                {narrative.behavioral_deep_dive}
              </div>
            </section>

            {/* Risk Personality */}
            <section style={{ animation: "fade-up 0.5s ease-out 0.2s both" }}>
              <h2 className="font-body text-[11px] font-semibold tracking-[0.15em] uppercase text-text-ter mb-4">
                Risk Personality
              </h2>
              <div className="font-body text-[15px] leading-[1.8] text-text whitespace-pre-line">
                {narrative.risk_personality}
              </div>
            </section>

            {/* Tax Efficiency */}
            {narrative.tax_efficiency && (
              <section style={{ animation: "fade-up 0.5s ease-out 0.3s both" }}>
                <h2 className="font-body text-[11px] font-semibold tracking-[0.15em] uppercase text-text-ter mb-4">
                  Tax Efficiency
                </h2>
                <div className="font-body text-[15px] leading-[1.8] text-text whitespace-pre-line">
                  {narrative.tax_efficiency}
                </div>
              </section>
            )}

            {/* Regulatory Context */}
            {narrative.regulatory_context && (
              <section style={{ animation: "fade-up 0.5s ease-out 0.35s both" }}>
                <h2 className="font-body text-[11px] font-semibold tracking-[0.15em] uppercase text-text-ter mb-4">
                  Regulatory Context
                </h2>
                <div className="font-body text-[15px] leading-[1.8] text-text whitespace-pre-line">
                  {narrative.regulatory_context}
                </div>
              </section>
            )}

            {/* Key Recommendation */}
            <section style={{ animation: "fade-up 0.5s ease-out 0.4s both" }}>
              <div className="border-l-2 border-teal pl-6 py-2 bg-teal-muted rounded-r-lg">
                <h2 className="font-body text-[11px] font-semibold tracking-[0.15em] uppercase text-teal mb-3">
                  Key Recommendation
                </h2>
                <div className="font-body text-[16px] leading-[1.8] text-text font-medium">
                  {narrative.key_recommendation}
                </div>
              </div>
            </section>
          </div>

          {/* Footer */}
          <footer className="mt-16 pt-8 border-t border-border text-center" style={{ animation: "fade-up 0.5s ease-out 0.5s both" }}>
            <p className="font-body text-xs text-text-ter mb-2">
              {narrative.confidence_note}
            </p>
            <p className="font-body text-[10px] text-text-ter/60 tracking-wider uppercase">
              Powered by The Proving Ground Behavioral Mirror
            </p>
            <button
              onClick={handleReset}
              className="mt-6 px-6 py-2.5 rounded-[10px] border border-border text-sm font-body font-medium text-text-sec hover:text-text hover:border-text-ter transition-all print:hidden"
            >
              Start Over
            </button>
          </footer>
        </article>
        <DebugBanner />
      </div>
    );
  }

  return null;
}
