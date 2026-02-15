"use client";

import { useState, useEffect } from "react";
import { useUser } from "@clerk/nextjs";
import { currentUserProfile, trendingTickers, predictions } from "@/lib/mock-data";
import { loadPortfolio, hasImportedData, clearImportedData } from "@/lib/storage";
import { ComputedPortfolio } from "@/types";
import TickerCard from "@/components/cards/TickerCard";
import PredictionCard from "@/components/cards/PredictionCard";
import StreakBanner from "@/components/gamification/StreakBanner";
import DailyChallenge from "@/components/gamification/DailyChallenge";
import { Database, X } from "lucide-react";

export default function DiscoverTab() {
  const { user } = useUser();
  const firstName = user?.firstName || "Trader";
  const profile = currentUserProfile;
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

  const portfolioValue = usingImported && imported ? imported.totalValue : profile.portfolioValue;
  const pnl = usingImported && imported ? imported.totalPnl : profile.pnl;
  const pnlPercent = usingImported && imported ? imported.totalPnlPercent : profile.pnlPercent;
  const startingValue = usingImported && imported ? imported.totalCost : profile.startingValue;

  const handleClearImport = () => {
    clearImportedData();
    setImported(null);
    setUsingImported(false);
  };

  return (
    <div className="space-y-6">
      {/* Imported Data Indicator */}
      {usingImported && (
        <div className="flex items-center justify-between px-4 py-2.5 rounded-lg bg-teal-light border border-teal/10 animate-fade-up">
          <div className="flex items-center gap-2 text-xs text-teal font-medium">
            <Database className="w-3.5 h-3.5" />
            Using imported trade data
          </div>
          <button
            onClick={handleClearImport}
            className="flex items-center gap-1 text-xs text-text-ter hover:text-red transition-colors"
          >
            <X className="w-3 h-3" />
            Clear
          </button>
        </div>
      )}

      {/* Greeting + Portfolio */}
      <div className="animate-fade-up">
        <h2 className="font-display italic text-[28px] text-text">
          Good morning, {firstName}
        </h2>
        <div className="flex items-baseline gap-3 mt-1">
          <span className="font-mono text-[44px] font-bold text-text leading-none">
            ${Math.round(portfolioValue).toLocaleString()}
          </span>
          <span className={`font-mono text-base font-semibold ${pnl >= 0 ? "text-green" : "text-red"}`}>
            {pnl >= 0 ? "+" : ""}${Math.round(pnl).toLocaleString()} ({pnlPercent.toFixed(1)}%)
          </span>
        </div>
        <p className="text-sm text-text-ter mt-1 font-body">
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
          <h3 className="text-base font-semibold text-text font-body">
            Trending on Yabo
          </h3>
          <button className="text-sm font-medium text-teal hover:text-teal/80 transition-colors font-body">
            See all
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
          <h3 className="text-base font-semibold text-text font-body">
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
