"use client";

import Link from "next/link";
import { useProfile } from "@/hooks/useProfile";
import { usePortfolio } from "@/hooks/usePortfolio";
import { strategyRecommendations, currentUserProfile } from "@/lib/mock-data";
import Card from "@/components/ui/Card";
import MockDataBadge from "@/components/ui/MockDataBadge";
import { AlertTriangle, Check, X, Link2, Upload, Brain } from "lucide-react";
import GuidePanel from "@/components/guide/GuidePanel";

interface AiRecommendation {
  priority: "high" | "medium" | "low";
  title: string;
  body: string;
  actionLabel: string;
  impact: string;
}

const urgencyStyles: Record<string, { border: string; bg: string; label: string; color: string }> = {
  high: { border: "border-l-red", bg: "bg-red-light", label: "HIGH", color: "text-red" },
  medium: { border: "border-l-yellow", bg: "bg-yellow-light", label: "MEDIUM", color: "text-yellow" },
  low: { border: "border-l-blue", bg: "bg-blue-light", label: "LOW", color: "text-blue" },
};

export default function StrategyTab({ guideActive }: { guideActive?: boolean }) {
  const { profile: dbProfile } = useProfile();
  const { positions, trades } = usePortfolio();
  const user = currentUserProfile;

  const hasAiRecs = dbProfile?.ai_recommendations && Array.isArray(dbProfile.ai_recommendations) && dbProfile.ai_recommendations.length > 0;
  const aiRecs: AiRecommendation[] = hasAiRecs
    ? (dbProfile!.ai_recommendations as unknown as AiRecommendation[])
    : [];

  // Use AI recs or fallback to mock
  const showingLive = hasAiRecs;

  const totalImpact = showingLive
    ? 0 // AI recs use string impact like "+$2,000 estimated"
    : strategyRecommendations.reduce((sum, r) => sum + r.impact, 0);

  const posCount = positions.length > 0 ? positions.length : user.positions;
  const recsCount = showingLive ? aiRecs.length : strategyRecommendations.length;

  return (
    <div className="space-y-6">
      {guideActive && <GuidePanel section="strategy" />}
      <div>
        <div className="flex items-center gap-3">
          <h2 className="font-display text-[28px] text-text">
            Strategy
          </h2>
          {!showingLive && <MockDataBadge />}
          {showingLive && (
            <span className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold uppercase font-mono text-teal bg-teal-light">
              <Brain className="w-3 h-3" />
              AI
            </span>
          )}
        </div>
        <p className="text-sm text-text-ter mt-0.5 font-body">
          {showingLive ? "AI recommendations based on your trade history" : "AI recommendations for your positions"}
        </p>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-3 animate-fade-up">
        {[
          { label: "Positions", value: String(posCount) },
          { label: "Trades", value: String(trades.length > 0 ? trades.length : user.effectiveBets.toFixed(1)) },
          { label: "Recs", value: String(recsCount) },
          { label: showingLive ? "Source" : "Potential", value: showingLive ? "Claude AI" : `+$${totalImpact.toLocaleString()}`, green: !showingLive },
        ].map((s) => (
          <Card key={s.label} hover={false} className="p-4">
            <span className="text-[10px] text-text-ter uppercase tracking-wider font-mono">
              {s.label}
            </span>
            <p className={`font-mono text-xl font-bold mt-1 ${s.green ? "text-green" : "text-text"}`}>
              {s.value}
            </p>
          </Card>
        ))}
      </div>

      {/* Empty State */}
      {!showingLive && trades.length === 0 && (
        <Card hover={false} className="p-8 text-center animate-fade-up">
          <div className="w-14 h-14 rounded-full bg-teal-light flex items-center justify-center mx-auto mb-3">
            <Upload className="w-7 h-7 text-teal" />
          </div>
          <h3 className="font-display text-lg text-text">Import trades for personalized recommendations</h3>
          <p className="text-sm text-text-ter mt-2 font-body max-w-md mx-auto">
            Upload your trade history to get AI-powered strategy recommendations tailored to your trading patterns.
          </p>
          <Link
            href="/dashboard/import"
            className="inline-flex items-center gap-2 mt-4 px-6 py-3 rounded-xl bg-text text-bg text-sm font-semibold hover:bg-text/80 transition-colors font-body"
          >
            <Upload className="w-4 h-4" />
            Import Trades
          </Link>
        </Card>
      )}

      {/* AI Recommendations */}
      {showingLive && (
        <div className="space-y-3">
          {aiRecs.map((rec, i) => {
            const style = urgencyStyles[rec.priority] || urgencyStyles.medium;
            const animClass =
              i === 0
                ? "animate-fade-up-delay-1"
                : i === 1
                  ? "animate-fade-up-delay-2"
                  : "animate-fade-up-delay-3";

            return (
              <div
                key={`${rec.title}-${i}`}
                className={`bg-surface rounded-xl border border-border border-l-4 ${style.border} p-5 ${animClass}
                  transition-all duration-200 hover:shadow-sm hover:-translate-y-0.5`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="font-mono text-base font-bold text-text">
                        {rec.title}
                      </span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase font-mono ${style.color} ${style.bg}`}>
                        {style.label}
                      </span>
                    </div>
                    <p className="text-sm text-text-sec leading-relaxed font-body">
                      {rec.body}
                    </p>
                  </div>
                  <div className="ml-4 text-right shrink-0">
                    <p className="text-[10px] text-text-ter uppercase font-mono">Impact</p>
                    <p className="font-mono text-sm font-bold text-green">
                      {rec.impact}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 mt-4 pt-3 border-t border-border" style={{ opacity: 0.35, pointerEvents: "none" }}>
                  <span className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-text text-bg text-xs font-semibold cursor-not-allowed font-body">
                    <Check className="w-3.5 h-3.5" />
                    {rec.actionLabel || "Apply"}
                  </span>
                  <span className="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-border text-text-sec text-xs font-medium cursor-not-allowed font-body">
                    <X className="w-3.5 h-3.5" />
                    Dismiss
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Mock Recommendations (fallback) */}
      {!showingLive && (
        <div className="space-y-3">
          {strategyRecommendations.map((rec, i) => {
            const style = urgencyStyles[rec.urgency];
            const animClass =
              i === 0
                ? "animate-fade-up-delay-1"
                : i === 1
                  ? "animate-fade-up-delay-2"
                  : "animate-fade-up-delay-3";

            return (
              <div
                key={rec.ticker}
                className={`bg-surface rounded-xl border border-border border-l-4 ${style.border} p-5 ${animClass}
                  transition-all duration-200 hover:shadow-sm hover:-translate-y-0.5`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="font-mono text-base font-bold text-text">
                        {rec.ticker}
                      </span>
                      <span className="text-sm font-medium text-text font-body">
                        {rec.action}
                      </span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase font-mono ${style.color} ${style.bg}`}>
                        {style.label}
                      </span>
                    </div>
                    <p className="text-sm text-text-sec leading-relaxed font-body">
                      {rec.narrative}
                    </p>
                    <div className="mt-3 flex items-start gap-2 p-3 rounded-lg bg-bg">
                      <AlertTriangle className="w-3.5 h-3.5 text-teal mt-0.5 shrink-0" />
                      <p className="text-xs text-text-sec leading-relaxed font-body">
                        {rec.behavioral}
                      </p>
                    </div>
                  </div>
                  <div className="ml-4 text-right shrink-0">
                    <p className="text-[10px] text-text-ter uppercase font-mono">Impact</p>
                    <p className="font-mono text-lg font-bold text-green">
                      +${rec.impact.toLocaleString()}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 mt-4 pt-3 border-t border-border" style={{ opacity: 0.35, pointerEvents: "none" }}>
                  <span className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-text text-bg text-xs font-semibold cursor-not-allowed font-body">
                    <Check className="w-3.5 h-3.5" />
                    Apply
                  </span>
                  <span className="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-border text-text-sec text-xs font-medium cursor-not-allowed font-body">
                    <X className="w-3.5 h-3.5" />
                    Dismiss
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Correlation Alert */}
      <div className="bg-purple-light border border-purple/20 rounded-xl p-5 animate-fade-up-delay-3">
        <div className="flex items-start gap-3">
          <Link2 className="w-5 h-5 text-purple mt-0.5 shrink-0" />
          <div>
            <h4 className="text-sm font-semibold text-purple font-body">
              Correlation Alert
            </h4>
            <p className="text-sm text-purple/80 mt-1 leading-relaxed font-body">
              {showingLive
                ? "Your portfolio concentration has been analyzed. Check the recommendations above for diversification opportunities."
                : "NVDA + AMD + AVGO are 94% correlated. 3 positions but effectively 1.3 independent bets. Consider diversifying across uncorrelated sectors to reduce portfolio risk."
              }
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
