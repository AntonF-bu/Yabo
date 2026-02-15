"use client";

import { TrendingTicker } from "@/types";
import SignalBadge from "@/components/ui/SignalBadge";
import { Flame } from "lucide-react";

interface TickerCardProps {
  ticker: TrendingTicker;
}

export default function TickerCard({ ticker }: TickerCardProps) {
  const isPositive = ticker.change >= 0;

  return (
    <div className="bg-surface rounded-xl border border-border p-4 transition-all duration-200 hover:-translate-y-0.5 hover:border-border-accent hover:shadow-[0_4px_24px_rgba(0,0,0,0.3)] cursor-pointer">
      <div className="flex items-center justify-between mb-3">
        <span className="font-mono text-base font-bold text-text">
          {ticker.ticker}
        </span>
        <span
          className={`font-mono text-sm font-semibold ${isPositive ? "text-green" : "text-red"}`}
        >
          {isPositive ? "+" : ""}
          {ticker.change.toFixed(1)}%
        </span>
      </div>
      <div className="flex items-center justify-between">
        <SignalBadge score={ticker.signal} size="md" />
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-ter font-mono">
            {ticker.theses} theses
          </span>
          {ticker.hot && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-teal-light text-teal text-[10px] font-mono font-bold uppercase tracking-wider">
              <Flame className="w-2.5 h-2.5" />
              HOT
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
