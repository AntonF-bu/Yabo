"use client";

import { useState, useEffect } from "react";
import { useUser } from "@clerk/nextjs";
import { useProfile } from "@/hooks/useProfile";
import { PortfolioPositionRow, TradeRow } from "@/hooks/usePortfolio";
import { trendingTickers, predictions } from "@/lib/mock-data";
import { getQuote } from "@/lib/market-data";
import { loadPortfolio, hasImportedData, clearImportedData } from "@/lib/storage";
import { ComputedPortfolio } from "@/types";
import TickerCard from "@/components/cards/TickerCard";
import PredictionCard from "@/components/cards/PredictionCard";
import StreakBanner from "@/components/gamification/StreakBanner";
import DailyChallenge from "@/components/gamification/DailyChallenge";
import PositionsList from "@/components/dashboard/PositionsList";
import RecentTrades from "@/components/dashboard/RecentTrades";
import { Database, X, ArrowUpRight } from "lucide-react";

interface DiscoverTabProps {
  portfolioPositions?: PortfolioPositionRow[];
  portfolioTrades?: TradeRow[];
  portfolioCash?: number;
  portfolioTotalValue?: number;
  onOpenTrade?: (ticker?: string) => void;
}

const TRENDING_SYMBOLS = ["NVDA", "AMZN", "TSLA", "META", "AAPL", "AVGO"];

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

export default function DiscoverTab({
  portfolioPositions,
  portfolioTrades,
  portfolioCash,
  portfolioTotalValue,
  onOpenTrade,
}: DiscoverTabProps) {
  const { user } = useUser();
  const { profile: dbProfile } = useProfile();
  const firstName =
    user?.firstName ||
    user?.fullName?.split(" ")[0] ||
    user?.username ||
    user?.primaryEmailAddress?.emailAddress?.split("@")[0] ||
    "Trader";
  const greeting = getGreeting();
  const [imported, setImported] = useState<ComputedPortfolio | null>(null);
  const [usingImported, setUsingImported] = useState(false);
  const [liveQuotes, setLiveQuotes] = useState<Record<string, { change: number; changePercent: number }>>({});

  useEffect(() => {
    if (hasImportedData()) {
      const portfolio = loadPortfolio();
      if (portfolio) {
        setImported(portfolio);
        setUsingImported(true);
      }
    }
  }, []);

  // Fetch real prices for trending tickers
  useEffect(() => {
    let cancelled = false;
    async function fetchTrending() {
      const results: Record<string, { change: number; changePercent: number }> = {};
      for (const symbol of TRENDING_SYMBOLS) {
        if (cancelled) break;
        try {
          const quote = await getQuote(symbol);
          if (quote.c > 0) {
            results[symbol] = { change: quote.d, changePercent: quote.dp };
          }
        } catch {
          // Use fallback on failure
        }
        // Small delay to avoid rate limiting
        await new Promise(r => setTimeout(r, 200));
      }
      if (!cancelled) setLiveQuotes(results);
    }
    fetchTrending();
    return () => { cancelled = true };
  }, []);

  const hasRealPortfolio = portfolioTrades && portfolioTrades.length > 0;

  // Use real portfolio data > imported data > mock data
  const portfolioValue = hasRealPortfolio && portfolioTotalValue != null
    ? portfolioTotalValue
    : usingImported && imported
      ? imported.totalValue
      : dbProfile?.current_value ?? 100000;
  const startCap = 100000;
  const pnl = portfolioValue - startCap;
  const pnlPercent = startCap > 0 ? ((portfolioValue - startCap) / startCap) * 100 : 0;
  const cashBalance = hasRealPortfolio && portfolioCash != null ? portfolioCash : null;

  const handleClearImport = () => {
    clearImportedData();
    setImported(null);
    setUsingImported(false);
  };

  // Merge live quotes into trending tickers
  const enrichedTickers = trendingTickers.map((t) => {
    const live = liveQuotes[t.ticker];
    if (live) {
      return { ...t, change: live.changePercent };
    }
    return t;
  });

  return (
    <div className="space-y-6">
      {/* Imported Data Indicator */}
      {usingImported && !hasRealPortfolio && (
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
          {greeting}, {firstName}
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
          Simulated portfolio &middot; Started $100,000
          {cashBalance != null && (
            <span> &middot; Cash: <span className="font-mono">${Math.round(cashBalance).toLocaleString()}</span></span>
          )}
          {portfolioPositions && portfolioPositions.length > 0 && (
            <span> &middot; {portfolioPositions.length} position{portfolioPositions.length !== 1 ? 's' : ''}</span>
          )}
        </p>
      </div>

      {/* Real Positions */}
      {portfolioPositions && portfolioPositions.length > 0 && (
        <div className="animate-fade-up-delay-1">
          <PositionsList positions={portfolioPositions} totalValue={portfolioValue} />
        </div>
      )}

      {/* Recent Trades */}
      {portfolioTrades && portfolioTrades.length > 0 && (
        <div className="animate-fade-up-delay-1">
          <RecentTrades trades={portfolioTrades} />
        </div>
      )}

      {/* First Trade Prompt */}
      {(!portfolioTrades || portfolioTrades.length === 0) && (
        <div className="animate-fade-up-delay-1 p-5 rounded-xl bg-surface border border-border text-center">
          <p className="font-display italic text-lg text-text">Make your first trade</p>
          <p className="text-sm text-text-sec mt-1 font-body">
            You have $100,000 in simulated capital. Tap the + button to get started.
          </p>
          <button
            onClick={() => onOpenTrade?.()}
            className="flex items-center justify-center gap-1 mt-3 text-teal text-sm font-semibold font-body hover:text-teal/80 transition-colors"
          >
            <ArrowUpRight className="w-4 h-4" />
            Open Trade Panel
          </button>
        </div>
      )}

      {/* Streak */}
      <div className="animate-fade-up-delay-2">
        <StreakBanner />
      </div>

      {/* Daily Challenge */}
      <div className="animate-fade-up-delay-3">
        <DailyChallenge />
      </div>

      {/* Trending */}
      <div className="animate-fade-up-delay-3">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-text font-body">
            Trending on Yabo
          </h3>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {enrichedTickers.map((t) => (
            <div key={t.ticker} onClick={() => onOpenTrade?.(t.ticker)}>
              <TickerCard ticker={t} showSignalPreview />
            </div>
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
