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
    <div className="bg-surface rounded-xl border border-border p-4 transition-all duration-200 hover:shadow-sm hover:-translate-y-0.5 hover:border-text-tertiary/30 cursor-pointer">
      <div className="flex items-center justify-between mb-3">
        <span className="font-mono text-base font-bold text-text-primary">
          {ticker.ticker}
        </span>
        <span
          className={`font-mono text-sm font-semibold ${isPositive ? "text-gain" : "text-loss"}`}
        >
          {isPositive ? "+" : ""}
          {ticker.change.toFixed(1)}%
        </span>
      </div>
      <div className="flex items-center justify-between">
        <SignalBadge score={ticker.signal} size="md" />
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-tertiary">
            {ticker.theses} theses
          </span>
          {ticker.hot && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-accent-light text-accent text-[10px] font-bold uppercase">
              <Flame className="w-2.5 h-2.5" />
              HOT
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
