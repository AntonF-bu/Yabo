"use client";

import { useState, useEffect } from "react";
import { currentUserProfile, trendingTickers, predictions } from "@/lib/mock-data";
import { loadPortfolio, hasImportedData, clearImportedData } from "@/lib/storage";
import { ComputedPortfolio } from "@/types";
import TickerCard from "@/components/cards/TickerCard";
import PredictionCard from "@/components/cards/PredictionCard";
import StreakBanner from "@/components/gamification/StreakBanner";
import DailyChallenge from "@/components/gamification/DailyChallenge";
import { Database, X } from "lucide-react";

export default function DiscoverTab() {
  const user = currentUserProfile;
  const [imported, setImported] = useState<ComputedPortfolio | null>(null);
  const [usingImported, setUsingImported] = useState(false);

  useEffect(() => {
    if (hasImportedData()) {
      const portfolio = loadPortfolio();
      if (portfolio) {
        setImported(portfolio);
        setUsingImported(true);
      }
    }
  }, []);

  const portfolioValue = usingImported && imported ? imported.totalValue : user.portfolioValue;
  const pnl = usingImported && imported ? imported.totalPnl : user.pnl;
  const pnlPercent = usingImported && imported ? imported.totalPnlPercent : user.pnlPercent;
  const startingValue = usingImported && imported ? imported.totalCost : user.startingValue;

  const handleClearImport = () => {
    clearImportedData();
    setImported(null);
    setUsingImported(false);
  };

  return (
    <div className="space-y-6">
      {/* Imported Data Indicator */}
      {usingImported && (
        <div className="flex items-center justify-between px-4 py-2.5 rounded-lg bg-accent-light border border-accent/10 animate-fade-up">
          <div className="flex items-center gap-2 text-xs text-accent font-medium">
            <Database className="w-3.5 h-3.5" />
            Using imported trade data
          </div>
          <button
            onClick={handleClearImport}
            className="flex items-center gap-1 text-xs text-text-tertiary hover:text-loss transition-colors"
          >
            <X className="w-3 h-3" />
            Clear
          </button>
        </div>
      )}

      {/* Greeting + Portfolio */}
      <div className="animate-fade-up">
        <h2 className="font-serif italic text-[28px] text-text-primary">
          Good morning
        </h2>
        <div className="flex items-baseline gap-3 mt-1">
          <span className="font-mono text-[44px] font-bold text-text-primary leading-none">
            ${Math.round(portfolioValue).toLocaleString()}
          </span>
          <span className={`font-mono text-base font-semibold ${pnl >= 0 ? "text-gain" : "text-loss"}`}>
            {pnl >= 0 ? "+" : ""}${Math.round(pnl).toLocaleString()} ({pnlPercent.toFixed(1)}%)
          </span>
        </div>
        <p className="text-sm text-text-tertiary mt-1">
          {usingImported ? "Imported portfolio" : "Simulated portfolio"} &middot; Started ${Math.round(startingValue).toLocaleString()}
        </p>
      </div>

      {/* Streak */}
      <div className="animate-fade-up-delay-1">
        <StreakBanner />
      </div>

      {/* Daily Challenge */}
      <div className="animate-fade-up-delay-2">
        <DailyChallenge />
      </div>

      {/* Trending */}
      <div className="animate-fade-up-delay-3">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-text-primary">
            Trending on Yabo
          </h3>
          <button className="text-sm font-medium text-accent hover:text-accent-dark transition-colors">
            See all →
          </button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {trendingTickers.map((t) => (
            <TickerCard key={t.ticker} ticker={t} />
          ))}
        </div>
      </div>

      {/* Predictions */}
      <div className="animate-fade-up-delay-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-text-primary">
            Predictions
          </h3>
        </div>
        <div className="space-y-3">
          {predictions.slice(0, 3).map((p) => (
            <PredictionCard key={p.id} prediction={p} />
          ))}
        </div>
      </div>
    </div>
  );
}
