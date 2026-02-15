"use client";

import { useState, useCallback, useEffect } from "react";
import { useUser } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Upload, Columns, CheckCircle2, Loader2, Brain, FileText, TrendingUp, TrendingDown, Hash, Calendar, DollarSign, BarChart3, Percent, Target, AlertCircle } from "lucide-react";
import { parseCsvText, autoDetectColumns, mapToTrades } from "@/lib/csv-parser";
import { computePortfolio } from "@/lib/trade-analytics";
import { importTradesToSupabase } from "@/lib/import-engine";
import { analyzeAndSave } from "@/lib/analyze";
import { ImportedTrade, ColumnMapping, ComputedPortfolio } from "@/types";
import CsvUploader from "@/components/import/CsvUploader";
import ColumnMapper from "@/components/import/ColumnMapper";
import GuidePanel from "@/components/guide/GuidePanel";

type Step = 1 | 2 | 3 | 4;

const steps = [
  { num: 1, label: "Upload", icon: Upload },
  { num: 2, label: "Map Columns", icon: Columns },
  { num: 3, label: "Review & Import", icon: CheckCircle2 },
  { num: 4, label: "AI Analysis", icon: Brain },
];

export default function ImportPage() {
  const { user } = useUser();
  const router = useRouter();
  const [step, setStep] = useState<Step>(1);
  const [headers, setHeaders] = useState<string[]>([]);
  const [rows, setRows] = useState<string[][]>([]);
  const [preview, setPreview] = useState<string[][]>([]);
  const [mapping, setMapping] = useState<Partial<ColumnMapping>>({});
  const [trades, setTrades] = useState<ImportedTrade[]>([]);
  const [portfolio, setPortfolio] = useState<ComputedPortfolio | null>(null);
  const [importing, setImporting] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeProgress, setAnalyzeProgress] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [guideActive, setGuideActive] = useState(false);
  useEffect(() => {
    setGuideActive(localStorage.getItem("yabo_guide") === "true");
  }, []);

  const handleFileLoaded = useCallback((text: string) => {
    const result = parseCsvText(text);
    setHeaders(result.headers);
    setRows(result.rows);
    setPreview(result.preview);
    const detectedMapping = autoDetectColumns(result.headers);
    setMapping(detectedMapping);
    setStep(2);
  }, []);

  const handleProceedToReview = useCallback(() => {
    const requiredKeys: (keyof ColumnMapping)[] = ["date", "ticker", "action", "quantity", "price"];
    const missing = requiredKeys.filter((k) => !mapping[k]);
    if (missing.length > 0) return;

    const parsed = mapToTrades(rows, headers, mapping as ColumnMapping);
    setTrades(parsed);
    const computed = computePortfolio(parsed);
    setPortfolio(computed);
    setStep(3);
  }, [rows, headers, mapping]);

  const handleImportAndAnalyze = useCallback(async () => {
    if (!user || !portfolio || trades.length === 0) return;
    setError(null);

    try {
      // Step 1: Import to Supabase
      setImporting(true);
      setAnalyzeProgress("Importing trades to database...");
      await importTradesToSupabase(user.id, trades);
      setImporting(false);

      // Step 2: AI Analysis
      setStep(4);
      setAnalyzing(true);
      setAnalyzeProgress("Generating your Trading DNA...");

      const positionsForAnalysis = portfolio.positions
        .filter((p) => p.shares > 0)
        .map((p) => ({
          ticker: p.ticker,
          shares: p.shares,
          avgCost: p.avgCost,
          currentPrice: p.avgCost, // use avgCost as proxy
          sector: p.sector,
        }));

      const cashBalance = 100000 - trades.reduce((sum, t) => {
        if (t.action === "buy") return sum + t.total;
        return sum - t.total;
      }, 0);

      await analyzeAndSave(
        user.id,
        trades.map((t) => ({ ...t, action: t.action })),
        positionsForAnalysis,
        portfolio.totalValue,
        cashBalance,
      );

      setAnalyzeProgress("Analysis complete! Redirecting...");

      // Redirect to dashboard mirror tab after brief delay
      setTimeout(() => {
        router.push("/dashboard?tab=mirror");
      }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed. Please try again.");
      setImporting(false);
      setAnalyzing(false);
    }
  }, [user, portfolio, trades, router]);

  // Load demo CSV
  const handleLoadDemo = useCallback(async () => {
    try {
      const res = await fetch("/demo-trades.csv");
      const text = await res.text();
      handleFileLoaded(text);
    } catch {
      setError("Failed to load demo data.");
    }
  }, [handleFileLoaded]);

  const requiredMapped = (["date", "ticker", "action", "quantity", "price"] as const).every(
    (k) => mapping[k],
  );

  // Analysis loading screen
  if (step === 4 && analyzing) {
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
            <span className="text-xs text-text-ter font-mono">Analyzing {trades.length} trades...</span>
          </div>
          {error && (
            <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-light text-red text-sm font-body">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {error}
              <button
                onClick={() => { setStep(3); setAnalyzing(false); setError(null); }}
                className="ml-auto text-xs underline"
              >
                Go back
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

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
            <h1 className="font-display text-xl text-text">Import Trades</h1>
            <p className="text-xs text-text-ter mt-0.5 font-body">
              Upload your brokerage CSV or try demo data
            </p>
          </div>
        </div>
      </div>

      {/* Guide */}
      {guideActive && (
        <div className="max-w-3xl mx-auto px-6 pt-6">
          <GuidePanel section="import" />
        </div>
      )}

      {/* Stepper */}
      <div className="max-w-3xl mx-auto px-6 py-6">
        <div className="flex items-center justify-between mb-8">
          {steps.map((s, i) => {
            const Icon = s.icon;
            const isActive = step === s.num;
            const isComplete = step > s.num;
            return (
              <div key={s.num} className="flex items-center gap-3 flex-1">
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
                      <Icon className="w-4 h-4" />
                    )}
                  </div>
                  <span
                    className={`text-xs font-semibold whitespace-nowrap font-body ${
                      isActive ? "text-text" : "text-text-ter"
                    }`}
                  >
                    {s.label}
                  </span>
                </div>
                {i < steps.length - 1 && (
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

        {error && step !== 4 && (
          <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-light text-red text-sm font-body mb-6">
            <AlertCircle className="w-4 h-4 shrink-0" />
            {error}
          </div>
        )}

        {/* Step Content */}
        <div className="bg-surface rounded-xl border border-border p-6">
          {step === 1 && (
            <div className="space-y-4">
              <CsvUploader onFileLoaded={handleFileLoaded} />
              <div className="relative flex items-center gap-4 py-2">
                <div className="flex-1 h-px bg-border" />
                <span className="text-xs text-text-ter font-body">or</span>
                <div className="flex-1 h-px bg-border" />
              </div>
              <button
                onClick={handleLoadDemo}
                className="w-full py-3.5 rounded-xl border border-teal/30 bg-teal-light text-teal text-sm font-semibold hover:bg-teal/10 transition-colors font-body flex items-center justify-center gap-2"
              >
                <FileText className="w-4 h-4" />
                Load Demo Trade History (35 trades)
              </button>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-6">
              <ColumnMapper
                headers={headers}
                mapping={mapping}
                onMappingChange={setMapping}
                preview={preview}
              />
              <div className="flex items-center gap-3 pt-2">
                <button
                  onClick={() => setStep(1)}
                  className="px-6 py-3 rounded-xl border border-border text-sm font-semibold text-text-sec hover:bg-surface-hover transition-colors font-body"
                >
                  Back
                </button>
                <button
                  onClick={handleProceedToReview}
                  disabled={!requiredMapped}
                  className={`flex-1 py-3 rounded-xl text-sm font-semibold transition-colors font-body ${
                    requiredMapped
                      ? "bg-text text-bg hover:bg-text/80"
                      : "bg-border text-text-ter cursor-not-allowed"
                  }`}
                >
                  Parse & Review
                </button>
              </div>
            </div>
          )}

          {step === 3 && trades.length > 0 && portfolio && (
            <div className="space-y-8">
              {/* Summary Stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-bg rounded-xl border border-border p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <Hash className="w-3.5 h-3.5 text-text-ter" />
                    <span className="text-[10px] text-text-ter uppercase tracking-wider font-semibold font-mono">
                      Total Trades
                    </span>
                  </div>
                  <p className="font-mono text-2xl font-bold text-text">{trades.length}</p>
                </div>
                <div className="bg-bg rounded-xl border border-border p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <TrendingUp className="w-3.5 h-3.5 text-green" />
                    <span className="text-[10px] text-text-ter uppercase tracking-wider font-semibold font-mono">
                      Buys / Sells
                    </span>
                  </div>
                  <p className="font-mono text-2xl font-bold text-text">
                    <span className="text-green">{trades.filter((t) => t.action === "buy").length}</span>
                    <span className="text-text-ter mx-1">/</span>
                    <span className="text-red">{trades.filter((t) => t.action === "sell").length}</span>
                  </p>
                </div>
                <div className="bg-bg rounded-xl border border-border p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <Percent className="w-3.5 h-3.5 text-text-ter" />
                    <span className="text-[10px] text-text-ter uppercase tracking-wider font-semibold font-mono">
                      Win Rate
                    </span>
                  </div>
                  <p className="font-mono text-2xl font-bold text-text">
                    {Math.round(portfolio.winRate * 100)}%
                  </p>
                  <p className="text-[10px] text-text-ter font-mono mt-0.5">
                    {portfolio.wins}W / {portfolio.losses}L
                  </p>
                </div>
                <div className="bg-bg rounded-xl border border-border p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <BarChart3 className="w-3.5 h-3.5 text-text-ter" />
                    <span className="text-[10px] text-text-ter uppercase tracking-wider font-semibold font-mono">
                      Sharpe
                    </span>
                  </div>
                  <p className="font-mono text-2xl font-bold text-text">
                    {portfolio.sharpe.toFixed(1)}
                  </p>
                </div>
              </div>

              {/* P&L + Portfolio Overview */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="bg-bg rounded-xl border border-border p-4">
                  <span className="text-[10px] text-text-ter uppercase tracking-wider font-semibold font-mono">Total P&L</span>
                  <p className={`font-mono text-xl font-bold mt-1 ${portfolio.totalPnl >= 0 ? "text-green" : "text-red"}`}>
                    {portfolio.totalPnl >= 0 ? "+" : ""}${Math.round(portfolio.totalPnl).toLocaleString()}
                  </p>
                </div>
                <div className="bg-bg rounded-xl border border-border p-4">
                  <span className="text-[10px] text-text-ter uppercase tracking-wider font-semibold font-mono">Avg Hold</span>
                  <p className="font-mono text-xl font-bold text-text mt-1">{portfolio.avgHoldDays}d</p>
                </div>
                <div className="bg-bg rounded-xl border border-border p-4">
                  <span className="text-[10px] text-text-ter uppercase tracking-wider font-semibold font-mono">Positions</span>
                  <p className="font-mono text-xl font-bold text-text mt-1">{portfolio.positions.length}</p>
                </div>
              </div>

              {/* Sectors */}
              {(() => {
                const sectors = Array.from(new Set(trades.map((t) => t.sector).filter(Boolean)));
                return sectors.length > 0 ? (
                  <div>
                    <p className="text-xs font-semibold text-text-ter uppercase tracking-wider mb-3 font-mono">
                      Sectors Detected
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {sectors.map((sector) => {
                        const count = trades.filter((t) => t.sector === sector).length;
                        return (
                          <span key={sector} className="px-3 py-1.5 rounded-lg bg-surface-hover text-xs font-medium text-text-sec font-body">
                            {sector} <span className="font-mono text-text-ter ml-1">{count}</span>
                          </span>
                        );
                      })}
                    </div>
                  </div>
                ) : null;
              })()}

              {/* Trade Log Table */}
              <div>
                <p className="text-xs font-semibold text-text-ter uppercase tracking-wider mb-3 font-mono">
                  Trade Log ({trades.length})
                </p>
                <div className="overflow-x-auto rounded-lg border border-border max-h-[400px] overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-surface-hover">
                      <tr className="border-b border-border">
                        <th className="px-3 py-2 text-left text-text-ter font-semibold font-mono">Date</th>
                        <th className="px-3 py-2 text-left text-text-ter font-semibold font-mono">Ticker</th>
                        <th className="px-3 py-2 text-left text-text-ter font-semibold font-mono">Action</th>
                        <th className="px-3 py-2 text-right text-text-ter font-semibold font-mono">Qty</th>
                        <th className="px-3 py-2 text-right text-text-ter font-semibold font-mono">Price</th>
                        <th className="px-3 py-2 text-right text-text-ter font-semibold font-mono">Total</th>
                        <th className="px-3 py-2 text-left text-text-ter font-semibold font-mono">Sector</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trades.map((trade, i) => (
                        <tr key={i} className="border-b border-border last:border-b-0 hover:bg-surface-hover/50">
                          <td className="px-3 py-2 font-mono text-text-sec">{trade.date}</td>
                          <td className="px-3 py-2 font-mono font-semibold text-text">{trade.ticker}</td>
                          <td className="px-3 py-2">
                            <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold font-mono ${
                              trade.action === "buy" ? "bg-green-light text-green" : "bg-red-light text-red"
                            }`}>
                              {trade.action === "buy" ? <TrendingUp className="w-2.5 h-2.5" /> : <TrendingDown className="w-2.5 h-2.5" />}
                              {trade.action.toUpperCase()}
                            </span>
                          </td>
                          <td className="px-3 py-2 font-mono text-right text-text-sec">{trade.quantity}</td>
                          <td className="px-3 py-2 font-mono text-right text-text-sec">${trade.price.toFixed(2)}</td>
                          <td className="px-3 py-2 font-mono text-right text-text font-medium">${trade.total.toFixed(2)}</td>
                          <td className="px-3 py-2 text-text-ter font-body">{trade.sector || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Behavioral Traits Preview */}
              <div>
                <p className="text-xs font-semibold text-text-ter uppercase tracking-wider mb-3 font-mono">
                  Computed Behavioral Traits
                </p>
                <div className="space-y-2">
                  {portfolio.traits.map((trait) => (
                    <div key={trait.name} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-surface-hover">
                      <span className="text-xs text-text-sec w-36 font-body">{trait.name}</span>
                      <div className="flex-1 h-2 rounded-full bg-text-muted overflow-hidden">
                        <div className="h-full rounded-full bg-teal transition-all duration-500" style={{ width: `${trait.score}%` }} />
                      </div>
                      <span className="font-mono text-xs font-semibold text-text w-8 text-right">{trait.score}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Top Positions */}
              {portfolio.positions.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-text-ter uppercase tracking-wider mb-3 font-mono">
                    Top Positions
                  </p>
                  <div className="overflow-x-auto rounded-lg border border-border">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="bg-surface-hover border-b border-border">
                          <th className="px-3 py-2 text-left text-text-ter font-semibold font-mono">Ticker</th>
                          <th className="px-3 py-2 text-left text-text-ter font-semibold font-mono">Sector</th>
                          <th className="px-3 py-2 text-right text-text-ter font-semibold font-mono">Trades</th>
                          <th className="px-3 py-2 text-right text-text-ter font-semibold font-mono">P&L</th>
                          <th className="px-3 py-2 text-right text-text-ter font-semibold font-mono">Win Rate</th>
                        </tr>
                      </thead>
                      <tbody>
                        {portfolio.positions.sort((a, b) => b.trades - a.trades).slice(0, 8).map((pos) => (
                          <tr key={pos.ticker} className="border-b border-border last:border-b-0">
                            <td className="px-3 py-2 font-mono font-semibold text-text">{pos.ticker}</td>
                            <td className="px-3 py-2 text-text-ter font-body">{pos.sector}</td>
                            <td className="px-3 py-2 font-mono text-right text-text-sec">{pos.trades}</td>
                            <td className={`px-3 py-2 font-mono text-right font-medium ${pos.pnl >= 0 ? "text-green" : "text-red"}`}>
                              {pos.pnl >= 0 ? "+" : ""}${Math.round(pos.pnl).toLocaleString()}
                            </td>
                            <td className="px-3 py-2 font-mono text-right text-text-sec">
                              {pos.trades >= 2 ? `${Math.round((pos.wins / Math.floor(pos.trades / 2)) * 100)}%` : "-"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Import Actions */}
              <div className="flex items-center gap-3 pt-2">
                <button
                  onClick={() => setStep(2)}
                  className="px-6 py-3 rounded-xl border border-border text-sm font-semibold text-text-sec hover:bg-surface-hover transition-colors font-body"
                >
                  Back
                </button>
                <button
                  onClick={handleImportAndAnalyze}
                  disabled={importing}
                  className="flex-1 py-3 rounded-xl bg-text text-bg text-sm font-semibold hover:bg-text/80 transition-colors font-body flex items-center justify-center gap-2"
                >
                  {importing ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Importing...
                    </>
                  ) : (
                    <>
                      <Brain className="w-4 h-4" />
                      Import & Generate Trading DNA
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
