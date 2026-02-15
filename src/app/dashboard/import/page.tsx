"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { ArrowLeft, Upload, Columns, CheckCircle2 } from "lucide-react";
import { parseCsvText, autoDetectColumns, mapToTrades } from "@/lib/csv-parser";
import { computePortfolio } from "@/lib/trade-analytics";
import { saveTrades, savePortfolio } from "@/lib/storage";
import { ImportedTrade, ColumnMapping, ComputedPortfolio } from "@/types";
import CsvUploader from "@/components/import/CsvUploader";
import ColumnMapper from "@/components/import/ColumnMapper";
import ImportPreview from "@/components/import/ImportPreview";
import ImportSummary from "@/components/import/ImportSummary";

type Step = 1 | 2 | 3;

const steps = [
  { num: 1, label: "Upload", icon: Upload },
  { num: 2, label: "Map Columns", icon: Columns },
  { num: 3, label: "Review & Confirm", icon: CheckCircle2 },
];

export default function ImportPage() {
  const [step, setStep] = useState<Step>(1);
  const [headers, setHeaders] = useState<string[]>([]);
  const [rows, setRows] = useState<string[][]>([]);
  const [preview, setPreview] = useState<string[][]>([]);
  const [mapping, setMapping] = useState<Partial<ColumnMapping>>({});
  const [trades, setTrades] = useState<ImportedTrade[]>([]);
  const [portfolio, setPortfolio] = useState<ComputedPortfolio | null>(null);
  const [done, setDone] = useState(false);

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

  const handleConfirm = useCallback(() => {
    if (!portfolio) return;
    saveTrades(trades);
    savePortfolio(portfolio);
    setDone(true);
  }, [trades, portfolio]);

  const requiredMapped = (["date", "ticker", "action", "quantity", "price"] as const).every(
    (k) => mapping[k],
  );

  if (done) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center p-6">
        <div className="max-w-md w-full text-center space-y-6 animate-fade-up">
          <div className="w-16 h-16 rounded-full bg-green-light flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-8 h-8 text-green" />
          </div>
          <div>
            <h2 className="font-display italic text-[28px] text-text">
              Import Complete
            </h2>
            <p className="text-sm text-text-ter mt-2 font-body">
              {trades.length} trades imported and analyzed. Your dashboard now
              reflects your real trading data.
            </p>
          </div>
          <div className="flex flex-col gap-3">
            <Link
              href="/dashboard"
              className="w-full py-3.5 rounded-xl bg-teal text-bg text-sm font-semibold flex items-center justify-center hover:bg-teal/80 transition-colors font-body"
            >
              Go to Dashboard
            </Link>
            <button
              onClick={() => {
                setDone(false);
                setStep(1);
                setHeaders([]);
                setRows([]);
                setPreview([]);
                setMapping({});
                setTrades([]);
                setPortfolio(null);
              }}
              className="w-full py-3 rounded-xl border border-border text-sm font-semibold text-text-sec hover:bg-surface-hover transition-colors font-body"
            >
              Import Another File
            </button>
          </div>
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
            <h1 className="font-display italic text-xl text-text">Import Trades</h1>
            <p className="text-xs text-text-ter mt-0.5 font-body">
              Upload your brokerage CSV export
            </p>
          </div>
        </div>
      </div>

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
                          ? "bg-teal text-bg"
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

        {/* Step Content */}
        <div className="bg-surface rounded-xl border border-border p-6">
          {step === 1 && <CsvUploader onFileLoaded={handleFileLoaded} />}

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
                      ? "bg-teal text-bg hover:bg-teal/80"
                      : "bg-border text-text-ter cursor-not-allowed"
                  }`}
                >
                  Parse & Review
                </button>
              </div>
            </div>
          )}

          {step === 3 && trades.length > 0 && (
            <div className="space-y-8">
              <ImportPreview trades={trades} />
              {portfolio && (
                <ImportSummary
                  portfolio={portfolio}
                  onConfirm={handleConfirm}
                  onBack={() => setStep(2)}
                />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
