"use client";

import { strategyRecommendations } from "@/lib/mock-data";
import Card from "@/components/ui/Card";
import StatCard from "@/components/ui/StatCard";
import { AlertTriangle, Check, X, Link2 } from "lucide-react";

const urgencyStyles = {
  high: { border: "border-l-loss", bg: "bg-loss-light", label: "HIGH", color: "text-loss" },
  medium: { border: "border-l-warn", bg: "bg-warn-light", label: "MEDIUM", color: "text-warn" },
  low: { border: "border-l-info", bg: "bg-info-light", label: "LOW", color: "text-info" },
};

export default function StrategyTab() {
  const totalImpact = strategyRecommendations.reduce(
    (sum, r) => sum + r.impact,
    0
  );

  return (
    <div className="space-y-6">
      <h2 className="font-serif italic text-2xl text-text-primary">
        Strategy
      </h2>

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4 animate-fade-up">
        <Card hover={false} className="p-4">
          <StatCard label="Positions" value="7" mono={true} />
        </Card>
        <Card hover={false} className="p-4">
          <StatCard label="Effective Bets" value="4.2" mono={true} />
        </Card>
        <Card hover={false} className="p-4">
          <StatCard label="Recs" value="3" mono={true} />
        </Card>
        <Card hover={false} className="p-4">
          <StatCard
            label="Potential"
            value={`+$${totalImpact.toLocaleString()}`}
            mono={true}
          />
        </Card>
      </div>

      {/* Recommendations */}
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
              className={`bg-surface rounded-xl border border-border border-l-4 ${style.border} p-5 ${animClass}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="font-mono text-base font-bold text-text-primary">
                      {rec.ticker}
                    </span>
                    <span className="text-sm font-medium text-text-primary">
                      {rec.action}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${style.color} ${style.bg}`}
                    >
                      {style.label}
                    </span>
                  </div>

                  <p className="text-sm text-text-secondary leading-relaxed">
                    {rec.narrative}
                  </p>

                  <div className="mt-3 flex items-start gap-2 p-3 rounded-lg bg-background">
                    <AlertTriangle className="w-3.5 h-3.5 text-accent mt-0.5 shrink-0" />
                    <p className="text-xs text-text-secondary leading-relaxed">
                      {rec.behavioral}
                    </p>
                  </div>
                </div>

                <div className="ml-4 text-right shrink-0">
                  <p className="text-xs text-text-tertiary">Impact</p>
                  <p className="font-mono text-lg font-bold text-gain">
                    +${rec.impact.toLocaleString()}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 mt-4 pt-3 border-t border-border-light">
                <button className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-accent text-white text-xs font-medium hover:bg-accent-dark transition-colors">
                  <Check className="w-3.5 h-3.5" />
                  Apply
                </button>
                <button className="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-border text-text-secondary text-xs font-medium hover:bg-surface-hover transition-colors">
                  <X className="w-3.5 h-3.5" />
                  Dismiss
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Correlation Alert */}
      <div className="bg-purple-light border border-purple/20 rounded-xl p-5 animate-fade-up-delay-3">
        <div className="flex items-start gap-3">
          <Link2 className="w-5 h-5 text-purple mt-0.5 shrink-0" />
          <div>
            <h4 className="text-sm font-semibold text-purple">
              Correlation Alert
            </h4>
            <p className="text-sm text-purple/80 mt-1 leading-relaxed">
              NVDA + AMD + AVGO are 94% correlated. 3 positions but effectively
              1.3 independent bets. Consider diversifying across uncorrelated
              sectors to reduce portfolio risk.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
