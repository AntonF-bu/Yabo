"use client";

import { TrendingTicker } from "@/types";
import SignalBadge from "@/components/ui/SignalBadge";
import { Flame } from "lucide-react";

interface TickerCardProps {
  ticker: TrendingTicker;
  showSignalPreview?: boolean;
}

export default function TickerCard({ ticker, showSignalPreview }: TickerCardProps) {
  const isPositive = ticker.change >= 0;

  return (
    <div className="bg-surface rounded-[14px] border border-border p-4 transition-all duration-200 hover:-translate-y-0.5 hover:border-border-accent cursor-pointer">
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
        <div>
          <SignalBadge score={ticker.signal} size="md" />
          {showSignalPreview && (
            <p className="text-[9px] font-body text-text-ter mt-0.5">Signal: preview</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-ter font-mono">
            {ticker.theses} theses
          </span>
          {ticker.hot && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-teal-light text-teal text-[10px] font-body font-semibold uppercase tracking-wider">
              <Flame className="w-2.5 h-2.5" />
              HOT
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
