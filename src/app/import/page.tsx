"use client";

import { useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Upload,
  Image as ImageIcon,
  CheckCircle2,
  Loader2,
  Brain,
  Trash2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Pencil,
  Camera,
  FileText,
} from "lucide-react";

/* ─── Types ─────────────────────────────────────────────────────────────────── */

interface Screenshot {
  file: File;
  preview: string;
}

interface ExtractedTrade {
  date: string;
  ticker: string;
  side: string;
  qty: number;
  price: number;
  total: number;
  status: "confirmed" | "needs_review";
  confidence?: string;
  source_screenshot?: number;
}

interface BrokerGuide {
  id: string;
  name: string;
  steps: string[];
}

type Phase = 1 | 2 | 3;

/* ─── Broker guides ─────────────────────────────────────────────────────────── */

const BROKER_GUIDES: BrokerGuide[] = [
  {
    id: "wellsfargo",
    name: "Wells Fargo",
    steps: [
      "Log into Wells Fargo Advisors, then select your Brokerage Account",
      "Go to Account Activity or Transaction History",
      "Set the date range to capture all trades",
      "Screenshot each page of the transaction list",
      "Upload all screenshots here",
    ],
  },
  {
    id: "merrill",
    name: "Merrill Lynch / Edge",
    steps: [
      "Log into Merrill Edge or Merrill Lynch",
      "Navigate to Accounts, then Activity & Statements",
      "Filter by Trade Confirmations or Transaction History",
      "Set the date range and screenshot each page",
      "Upload all screenshots here",
    ],
  },
  {
    id: "morganstanley",
    name: "Morgan Stanley",
    steps: [
      "Log into Morgan Stanley Online",
      "Go to Account Overview, then Transaction History",
      "Filter for stock trades and set your date range",
      "Screenshot each page of results",
      "Upload all screenshots here",
    ],
  },
  {
    id: "jpmorgan",
    name: "JP Morgan",
    steps: [
      "Log into J.P. Morgan Self-Directed Investing or Wealth Management",
      "Navigate to Activity & Statements",
      "Filter by transaction type (trades)",
      "Screenshot the transaction list pages",
      "Upload all screenshots here",
    ],
  },
  {
    id: "ubs",
    name: "UBS",
    steps: [
      "Log into UBS Online Services",
      "Go to Portfolio & Activity",
      "Select Transaction History with your date range",
      "Screenshot each page of trades",
      "Upload all screenshots here",
    ],
  },
  {
    id: "schwab",
    name: "Charles Schwab",
    steps: [
      "Log into Schwab.com",
      "Go to Accounts, then History",
      "Filter by date range and select Trades",
      "Screenshot or export as CSV (CSV preferred)",
      "Upload screenshots or use CSV import",
    ],
  },
  {
    id: "other",
    name: "Other Brokerage",
    steps: [
      "Log into your brokerage account",
      "Find your trade history or transaction log",
      "Set the date range to capture all trades you want analyzed",
      "Take screenshots of each page showing dates, tickers, buy/sell, quantity, and price",
      "Upload all screenshots here",
    ],
  },
];

const MIRROR_API =
  process.env.NEXT_PUBLIC_MIRROR_API_URL ?? "http://localhost:8000";

/* ─── Phase bar ─────────────────────────────────────────────────────────────── */

const phases = [
  { num: 1 as const, label: "Upload Screenshots" },
  { num: 2 as const, label: "Review Trades" },
  { num: 3 as const, label: "Analyze" },
];

/* ─── Component ─────────────────────────────────────────────────────────────── */

export default function ScreenshotImportPage() {
  const router = useRouter();

  // Phase state
  const [phase, setPhase] = useState<Phase>(1);

  // Phase 1: screenshots
  const [screenshots, setScreenshots] = useState<Screenshot[]>([]);
  const [extracting, setExtracting] = useState(false);
  const [extractProg, setExtractProg] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);

  // Phase 2: trades
  const [trades, setTrades] = useState<ExtractedTrade[]>([]);
  const [editIdx, setEditIdx] = useState<number | null>(null);
  const [detectedBrokerage, setDetectedBrokerage] = useState<string | null>(
    null,
  );

  // Phase 3: analyze
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeProgress, setAnalyzeProgress] = useState("");

  // Trader info
  const [traderName, setTraderName] = useState("");
  const [traderEmail, setTraderEmail] = useState("");
  const [selectedBrokerage, setSelectedBrokerage] = useState("");
  const [referredBy, setReferredBy] = useState("Daniel Starr");

  // Broker guide
  const [expandedGuide, setExpandedGuide] = useState<string | null>(null);

  // Error
  const [error, setError] = useState<string | null>(null);

  /* ─── Phase 1: File handling ────────────────────────────────── */

  const handleFiles = useCallback((files: FileList) => {
    const newScreenshots: Screenshot[] = [];
    Array.from(files).forEach((file) => {
      if (!file.type.startsWith("image/")) return;
      if (file.size > 10 * 1024 * 1024) return; // 10MB limit
      newScreenshots.push({
        file,
        preview: URL.createObjectURL(file),
      });
    });
    setScreenshots((prev) => [...prev, ...newScreenshots]);
  }, []);

  const removeScreenshot = useCallback((idx: number) => {
    setScreenshots((prev) => {
      URL.revokeObjectURL(prev[idx].preview);
      return prev.filter((_, i) => i !== idx);
    });
  }, []);

  /* ─── Phase 1 → 2: Extract from screenshots ────────────────── */

  const extractFromScreenshots = useCallback(async () => {
    if (screenshots.length === 0) return;
    setExtracting(true);
    setExtractProg(0);
    setError(null);

    const formData = new FormData();
    screenshots.forEach((s) => {
      formData.append("files", s.file);
    });

    try {
      setExtractProg(20);

      const response = await fetch(`${MIRROR_API}/extract_screenshots`, {
        method: "POST",
        body: formData,
      });

      setExtractProg(80);

      if (!response.ok) {
        const err = await response.json().catch(() => ({
          error: "Extraction failed",
        }));
        throw new Error(err.error || `Server error ${response.status}`);
      }

      const result = await response.json();

      if (result.brokerage) {
        setDetectedBrokerage(result.brokerage);
        if (!selectedBrokerage) {
          setSelectedBrokerage(result.brokerage);
        }
      }

      const mappedTrades: ExtractedTrade[] = (result.trades || []).map(
        (t: {
          date: string;
          ticker: string;
          side: string;
          quantity: number;
          price: number;
          total?: number;
          confidence?: string;
          source_screenshot?: number;
        }) => ({
          date: t.date,
          ticker: t.ticker,
          side: t.side,
          qty: t.quantity,
          price: t.price,
          total: t.total || t.quantity * t.price,
          status: t.confidence === "high" ? "confirmed" : "needs_review",
          confidence: t.confidence,
          source_screenshot: t.source_screenshot,
        }),
      );

      setTrades(mappedTrades);
      setExtractProg(100);
      await new Promise((r) => setTimeout(r, 300));
      setPhase(2);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Screenshot extraction failed",
      );
    } finally {
      setExtracting(false);
    }
  }, [screenshots, selectedBrokerage]);

  /* ─── Phase 2: Trade editing ────────────────────────────────── */

  const updateTrade = useCallback(
    (idx: number, field: keyof ExtractedTrade, value: string | number) => {
      setTrades((prev) =>
        prev.map((t, i) => {
          if (i !== idx) return t;
          const updated = { ...t, [field]: value, status: "confirmed" as const };
          if (field === "qty" || field === "price") {
            updated.total =
              (field === "qty" ? (value as number) : t.qty) *
              (field === "price" ? (value as number) : t.price);
          }
          return updated;
        }),
      );
    },
    [],
  );

  const removeTrade = useCallback((idx: number) => {
    setTrades((prev) => prev.filter((_, i) => i !== idx));
    setEditIdx(null);
  }, []);

  const addTrade = useCallback(() => {
    setTrades((prev) => [
      ...prev,
      {
        date: new Date().toISOString().slice(0, 10),
        ticker: "",
        side: "BUY",
        qty: 0,
        price: 0,
        total: 0,
        status: "needs_review",
      },
    ]);
    setEditIdx(trades.length);
  }, [trades.length]);

  /* ─── Phase 3: Analyze ──────────────────────────────────────── */

  const runAnalysis = useCallback(async () => {
    if (trades.length === 0) return;
    if (!traderName.trim()) {
      setError("Please enter the trader's name before analyzing.");
      return;
    }
    setAnalyzing(true);
    setAnalyzeProgress("Sending trades to analysis pipeline...");
    setError(null);
    setPhase(3);

    const payload = new FormData();
    payload.append("trades", JSON.stringify(trades.map((t) => ({
      date: t.date,
      ticker: t.ticker,
      side: t.side,
      quantity: t.qty,
      price: t.price,
      total: t.total,
    }))));

    const ctx: Record<string, unknown> = {};
    if (selectedBrokerage) ctx.brokerage = selectedBrokerage;
    payload.append("context", JSON.stringify(ctx));

    if (traderName) payload.append("trader_name", traderName);
    if (traderEmail) payload.append("trader_email", traderEmail);
    if (selectedBrokerage) payload.append("brokerage", selectedBrokerage);
    if (referredBy) payload.append("referred_by", referredBy);

    try {
      setAnalyzeProgress("Extracting behavioral features...");

      const response = await fetch(`${MIRROR_API}/import_and_analyze`, {
        method: "POST",
        body: payload,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({
          error: "Analysis failed",
        }));
        throw new Error(err.error || `Server error ${response.status}`);
      }

      setAnalyzeProgress("Analysis complete! Redirecting...");
      await new Promise((r) => setTimeout(r, 1200));
      router.push("/dashboard?tab=mirror");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Analysis pipeline failed",
      );
      setAnalyzing(false);
      setPhase(2);
    }
  }, [trades, traderName, traderEmail, selectedBrokerage, referredBy, router]);

  /* ─── Counts ────────────────────────────────────────────────── */

  const confirmedCount = trades.filter(
    (t) => t.status === "confirmed",
  ).length;
  const reviewCount = trades.filter(
    (t) => t.status === "needs_review",
  ).length;

  /* ─── Phase 3: Loading screen ───────────────────────────────── */

  if (phase === 3 && analyzing) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center p-6">
        <div className="max-w-md w-full text-center space-y-6 animate-fade-up">
          <div className="w-20 h-20 rounded-full bg-teal-light flex items-center justify-center mx-auto">
            <Brain className="w-10 h-10 text-teal animate-pulse" />
          </div>
          <div>
            <h2 className="font-display text-[28px] text-text">
              Generating Trading DNA
            </h2>
            <p className="text-sm text-text-ter mt-2 font-body">
              {analyzeProgress}
            </p>
          </div>
          <div className="flex items-center justify-center gap-2">
            <Loader2 className="w-4 h-4 text-teal animate-spin" />
            <span className="text-xs text-text-ter font-mono">
              Analyzing {trades.length} trades...
            </span>
          </div>
          {error && (
            <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-light text-red text-sm font-body">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {error}
            </div>
          )}
        </div>
      </div>
    );
  }

  /* ─── Main render ───────────────────────────────────────────── */

  return (
    <div className="min-h-screen bg-bg">
      {/* Header */}
      <div className="border-b border-border bg-surface">
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-center gap-4">
          <Link
            href="/dashboard"
            className="p-2 rounded-lg hover:bg-surface-hover transition-colors text-text-ter hover:text-text"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="font-display text-xl text-text">
              Import from Screenshots
            </h1>
            <p className="text-xs text-text-ter mt-0.5 font-body">
              Upload brokerage screenshots to extract trade data
            </p>
          </div>
        </div>
      </div>

      {/* Phase bar */}
      <div className="max-w-3xl mx-auto px-6 py-6">
        <div className="flex items-center justify-between mb-8">
          {phases.map((p, i) => {
            const isActive = phase === p.num;
            const isComplete = phase > p.num;
            return (
              <div key={p.num} className="flex items-center gap-3 flex-1">
                <div className="flex items-center gap-2.5">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 transition-colors ${
                      isComplete
                        ? "bg-green text-bg"
                        : isActive
                          ? "bg-text text-bg"
                          : "bg-surface-hover text-text-ter"
                    }`}
                  >
                    {isComplete ? (
                      <CheckCircle2 className="w-4 h-4" />
                    ) : (
                      <span className="text-xs font-mono font-bold">
                        {p.num}
                      </span>
                    )}
                  </div>
                  <span
                    className={`text-xs font-semibold whitespace-nowrap font-body ${
                      isActive ? "text-text" : "text-text-ter"
                    }`}
                  >
                    {p.label}
                  </span>
                </div>
                {i < phases.length - 1 && (
                  <div
                    className={`flex-1 h-px mx-2 ${
                      isComplete ? "bg-green" : "bg-border"
                    }`}
                  />
                )}
              </div>
            );
          })}
        </div>

        {error && phase !== 3 && (
          <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-light text-red text-sm font-body mb-6">
            <AlertCircle className="w-4 h-4 shrink-0" />
            {error}
            <button
              onClick={() => setError(null)}
              className="ml-auto text-xs underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* ─── Phase 1: Upload ──────────────────────────────────── */}
        {phase === 1 && (
          <div className="space-y-6">
            {/* Trader info */}
            <div className="bg-surface rounded-xl border border-border p-6 space-y-4">
              <p className="text-xs font-semibold text-text-ter uppercase tracking-wider font-mono">
                Trader Information
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-text-sec mb-1.5 font-body">
                    Name <span className="text-red">*</span>
                  </label>
                  <input
                    type="text"
                    value={traderName}
                    onChange={(e) => setTraderName(e.target.value)}
                    placeholder="Full name"
                    className="w-full px-3 py-2.5 rounded-lg border border-border bg-bg text-sm text-text font-body placeholder:text-text-ter focus:outline-none focus:border-teal"
                  />
                </div>
                <div>
                  <label className="block text-xs text-text-sec mb-1.5 font-body">
                    Email (optional)
                  </label>
                  <input
                    type="email"
                    value={traderEmail}
                    onChange={(e) => setTraderEmail(e.target.value)}
                    placeholder="trader@example.com"
                    className="w-full px-3 py-2.5 rounded-lg border border-border bg-bg text-sm text-text font-body placeholder:text-text-ter focus:outline-none focus:border-teal"
                  />
                </div>
                <div>
                  <label className="block text-xs text-text-sec mb-1.5 font-body">
                    Brokerage
                  </label>
                  <select
                    value={selectedBrokerage}
                    onChange={(e) => setSelectedBrokerage(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-lg border border-border bg-bg text-sm text-text font-body focus:outline-none focus:border-teal"
                  >
                    <option value="">Auto-detect from screenshots</option>
                    {BROKER_GUIDES.map((b) => (
                      <option key={b.id} value={b.name}>
                        {b.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-text-sec mb-1.5 font-body">
                    Referred by
                  </label>
                  <input
                    type="text"
                    value={referredBy}
                    onChange={(e) => setReferredBy(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-lg border border-border bg-bg text-sm text-text font-body placeholder:text-text-ter focus:outline-none focus:border-teal"
                  />
                </div>
              </div>
            </div>

            {/* Screenshot upload area */}
            <div className="bg-surface rounded-xl border border-border p-6 space-y-4">
              <p className="text-xs font-semibold text-text-ter uppercase tracking-wider font-mono">
                Screenshots
              </p>

              <div
                onClick={() => fileRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  handleFiles(e.dataTransfer.files);
                }}
                className="border-2 border-dashed rounded-xl p-10 flex flex-col items-center justify-center gap-3 cursor-pointer border-border hover:border-text-ter hover:bg-surface-hover transition-all"
              >
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  multiple
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files) handleFiles(e.target.files);
                  }}
                />
                <div className="w-12 h-12 rounded-full bg-surface-hover flex items-center justify-center">
                  <Camera className="w-5 h-5 text-text-ter" />
                </div>
                <div className="text-center">
                  <p className="text-sm font-semibold text-text font-body">
                    Drop screenshots here
                  </p>
                  <p className="text-xs text-text-ter mt-1 font-body">
                    PNG, JPG, or WebP. Max 10MB each.
                  </p>
                </div>
              </div>

              {/* Screenshot previews */}
              {screenshots.length > 0 && (
                <div className="grid grid-cols-3 md:grid-cols-4 gap-3">
                  {screenshots.map((s, i) => (
                    <div
                      key={i}
                      className="relative group rounded-lg overflow-hidden border border-border"
                    >
                      <img
                        src={s.preview}
                        alt={`Screenshot ${i + 1}`}
                        className="w-full h-24 object-cover"
                      />
                      <button
                        onClick={() => removeScreenshot(i)}
                        className="absolute top-1 right-1 p-1 rounded bg-text/70 text-bg opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                      <div className="absolute bottom-0 left-0 right-0 bg-text/60 px-2 py-0.5">
                        <span className="text-[10px] text-bg font-mono">
                          {i + 1}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Extract button */}
              <button
                onClick={extractFromScreenshots}
                disabled={screenshots.length === 0 || extracting}
                className={`w-full py-3.5 rounded-xl text-sm font-semibold transition-colors font-body flex items-center justify-center gap-2 ${
                  screenshots.length > 0 && !extracting
                    ? "bg-text text-bg hover:bg-text/80"
                    : "bg-border text-text-ter cursor-not-allowed"
                }`}
              >
                {extracting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Extracting trades... {extractProg}%
                  </>
                ) : (
                  <>
                    <ImageIcon className="w-4 h-4" />
                    Extract Trades from {screenshots.length} Screenshot
                    {screenshots.length !== 1 ? "s" : ""}
                  </>
                )}
              </button>
            </div>

            {/* Broker guides */}
            <div className="bg-surface rounded-xl border border-border p-6 space-y-3">
              <p className="text-xs font-semibold text-text-ter uppercase tracking-wider font-mono">
                How to Export from Your Brokerage
              </p>
              {BROKER_GUIDES.map((guide) => (
                <div key={guide.id} className="border border-border rounded-lg">
                  <button
                    onClick={() =>
                      setExpandedGuide(
                        expandedGuide === guide.id ? null : guide.id,
                      )
                    }
                    className="w-full flex items-center justify-between px-4 py-3 text-sm text-text font-body hover:bg-surface-hover transition-colors rounded-lg"
                  >
                    <span>{guide.name}</span>
                    {expandedGuide === guide.id ? (
                      <ChevronUp className="w-4 h-4 text-text-ter" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-text-ter" />
                    )}
                  </button>
                  {expandedGuide === guide.id && (
                    <div className="px-4 pb-4">
                      <ol className="space-y-2">
                        {guide.steps.map((step, i) => (
                          <li
                            key={i}
                            className="flex items-start gap-2 text-xs text-text-sec font-body"
                          >
                            <span className="font-mono text-text-ter shrink-0 w-4 text-right">
                              {i + 1}.
                            </span>
                            <span>{step}</span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* CSV fallback link */}
            <div className="text-center">
              <Link
                href="/dashboard/import"
                className="text-xs text-teal hover:underline font-body inline-flex items-center gap-1.5"
              >
                <FileText className="w-3.5 h-3.5" />
                Have a CSV file instead? Use CSV import
              </Link>
            </div>
          </div>
        )}

        {/* ─── Phase 2: Review trades ───────────────────────────── */}
        {phase === 2 && (
          <div className="space-y-6">
            {/* Summary bar */}
            <div className="bg-surface rounded-xl border border-border p-6">
              <div className="flex items-center justify-between mb-4">
                <p className="text-xs font-semibold text-text-ter uppercase tracking-wider font-mono">
                  Extracted Trades
                </p>
                {detectedBrokerage && (
                  <span className="text-xs text-teal font-body px-2.5 py-1 rounded-lg bg-teal-light">
                    Detected: {detectedBrokerage}
                  </span>
                )}
              </div>

              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="bg-bg rounded-lg border border-border p-3 text-center">
                  <p className="font-mono text-xl font-bold text-text">
                    {trades.length}
                  </p>
                  <p className="text-[10px] text-text-ter font-mono uppercase mt-0.5">
                    Total
                  </p>
                </div>
                <div className="bg-bg rounded-lg border border-border p-3 text-center">
                  <p className="font-mono text-xl font-bold text-green">
                    {confirmedCount}
                  </p>
                  <p className="text-[10px] text-text-ter font-mono uppercase mt-0.5">
                    Confirmed
                  </p>
                </div>
                <div className="bg-bg rounded-lg border border-border p-3 text-center">
                  <p className="font-mono text-xl font-bold text-yellow">
                    {reviewCount}
                  </p>
                  <p className="text-[10px] text-text-ter font-mono uppercase mt-0.5">
                    Needs Review
                  </p>
                </div>
              </div>

              {/* Trade table */}
              <div className="overflow-x-auto rounded-lg border border-border max-h-[500px] overflow-y-auto">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-surface-hover">
                    <tr className="border-b border-border">
                      <th className="px-3 py-2 text-left text-text-ter font-semibold font-mono">
                        Status
                      </th>
                      <th className="px-3 py-2 text-left text-text-ter font-semibold font-mono">
                        Date
                      </th>
                      <th className="px-3 py-2 text-left text-text-ter font-semibold font-mono">
                        Ticker
                      </th>
                      <th className="px-3 py-2 text-left text-text-ter font-semibold font-mono">
                        Side
                      </th>
                      <th className="px-3 py-2 text-right text-text-ter font-semibold font-mono">
                        Qty
                      </th>
                      <th className="px-3 py-2 text-right text-text-ter font-semibold font-mono">
                        Price
                      </th>
                      <th className="px-3 py-2 text-right text-text-ter font-semibold font-mono">
                        Total
                      </th>
                      <th className="px-3 py-2 w-16"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map((trade, i) => (
                      <tr
                        key={i}
                        className={`border-b border-border last:border-b-0 ${
                          trade.status === "needs_review"
                            ? "bg-yellow-light/30"
                            : "hover:bg-surface-hover/50"
                        }`}
                      >
                        <td className="px-3 py-2">
                          <span
                            className={`inline-block w-2 h-2 rounded-full ${
                              trade.status === "confirmed"
                                ? "bg-green"
                                : "bg-yellow"
                            }`}
                          />
                        </td>
                        {editIdx === i ? (
                          <>
                            <td className="px-1 py-1">
                              <input
                                type="date"
                                value={trade.date}
                                onChange={(e) =>
                                  updateTrade(i, "date", e.target.value)
                                }
                                className="w-full px-2 py-1 rounded border border-border bg-bg text-xs font-mono focus:outline-none focus:border-teal"
                              />
                            </td>
                            <td className="px-1 py-1">
                              <input
                                type="text"
                                value={trade.ticker}
                                onChange={(e) =>
                                  updateTrade(
                                    i,
                                    "ticker",
                                    e.target.value.toUpperCase(),
                                  )
                                }
                                className="w-full px-2 py-1 rounded border border-border bg-bg text-xs font-mono focus:outline-none focus:border-teal"
                              />
                            </td>
                            <td className="px-1 py-1">
                              <select
                                value={trade.side}
                                onChange={(e) =>
                                  updateTrade(i, "side", e.target.value)
                                }
                                className="w-full px-2 py-1 rounded border border-border bg-bg text-xs font-mono focus:outline-none focus:border-teal"
                              >
                                <option value="BUY">BUY</option>
                                <option value="SELL">SELL</option>
                              </select>
                            </td>
                            <td className="px-1 py-1">
                              <input
                                type="number"
                                value={trade.qty}
                                onChange={(e) =>
                                  updateTrade(
                                    i,
                                    "qty",
                                    parseFloat(e.target.value) || 0,
                                  )
                                }
                                className="w-full px-2 py-1 rounded border border-border bg-bg text-xs font-mono text-right focus:outline-none focus:border-teal"
                              />
                            </td>
                            <td className="px-1 py-1">
                              <input
                                type="number"
                                step="0.01"
                                value={trade.price}
                                onChange={(e) =>
                                  updateTrade(
                                    i,
                                    "price",
                                    parseFloat(e.target.value) || 0,
                                  )
                                }
                                className="w-full px-2 py-1 rounded border border-border bg-bg text-xs font-mono text-right focus:outline-none focus:border-teal"
                              />
                            </td>
                            <td className="px-3 py-2 font-mono text-right text-text font-medium">
                              ${trade.total.toFixed(2)}
                            </td>
                            <td className="px-2 py-2">
                              <button
                                onClick={() => setEditIdx(null)}
                                className="text-green hover:underline text-[10px] font-mono"
                              >
                                Done
                              </button>
                            </td>
                          </>
                        ) : (
                          <>
                            <td className="px-3 py-2 font-mono text-text-sec">
                              {trade.date}
                            </td>
                            <td className="px-3 py-2 font-mono font-semibold text-text">
                              {trade.ticker}
                            </td>
                            <td className="px-3 py-2">
                              <span
                                className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold font-mono ${
                                  trade.side === "BUY"
                                    ? "bg-green-light text-green"
                                    : "bg-red-light text-red"
                                }`}
                              >
                                {trade.side}
                              </span>
                            </td>
                            <td className="px-3 py-2 font-mono text-right text-text-sec">
                              {trade.qty}
                            </td>
                            <td className="px-3 py-2 font-mono text-right text-text-sec">
                              ${trade.price.toFixed(2)}
                            </td>
                            <td className="px-3 py-2 font-mono text-right text-text font-medium">
                              ${trade.total.toFixed(2)}
                            </td>
                            <td className="px-2 py-2 flex gap-1">
                              <button
                                onClick={() => setEditIdx(i)}
                                className="p-1 rounded hover:bg-surface-hover text-text-ter hover:text-text transition-colors"
                              >
                                <Pencil className="w-3 h-3" />
                              </button>
                              <button
                                onClick={() => removeTrade(i)}
                                className="p-1 rounded hover:bg-red-light text-text-ter hover:text-red transition-colors"
                              >
                                <Trash2 className="w-3 h-3" />
                              </button>
                            </td>
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Add trade */}
              <button
                onClick={addTrade}
                className="mt-3 w-full py-2.5 rounded-lg border border-dashed border-border text-xs text-text-ter hover:text-text hover:border-text-ter transition-colors font-body"
              >
                + Add trade manually
              </button>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => setPhase(1)}
                className="px-6 py-3 rounded-xl border border-border text-sm font-semibold text-text-sec hover:bg-surface-hover transition-colors font-body"
              >
                Back
              </button>
              <button
                onClick={runAnalysis}
                disabled={trades.length === 0}
                className={`flex-1 py-3 rounded-xl text-sm font-semibold transition-colors font-body flex items-center justify-center gap-2 ${
                  trades.length > 0
                    ? "bg-text text-bg hover:bg-text/80"
                    : "bg-border text-text-ter cursor-not-allowed"
                }`}
              >
                <Brain className="w-4 h-4" />
                Generate Trading DNA ({trades.length} trades)
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
