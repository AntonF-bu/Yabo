"use client";

import { traders } from "@/lib/mock-data";
import { tierColors } from "@/lib/constants";
import Sparkline from "@/components/ui/Sparkline";
import { Trophy } from "lucide-react";

export default function Leaderboard({ compact = false }: { compact?: boolean }) {
  const generateTrend = (seed: number) => {
    const data = [];
    let val = 50 + seed * 3;
    for (let i = 0; i < 10; i++) {
      val += (Math.sin(seed + i) * 5 + Math.cos(i * seed) * 3);
      data.push(Math.round(val));
    }
    return data;
  };

  if (compact) {
    return (
      <div className="bg-surface rounded-xl border border-border p-4 animate-fade-up-delay-2">
        <div className="flex items-center gap-2 mb-4">
          <Trophy className="w-4 h-4 text-gold" />
          <h3 className="text-sm font-semibold text-text-primary">
            Leaderboard
          </h3>
        </div>

        <div className="space-y-2.5">
          {traders.map((trader) => {
            const tierColor = tierColors[trader.tier] || "#9B9B9B";
            return (
              <div
                key={trader.id}
                className="flex items-center gap-2.5 py-1.5 px-2 rounded-lg hover:bg-surface-hover transition-colors cursor-pointer"
              >
                <span className="font-mono text-xs text-text-tertiary w-4 text-right">
                  {trader.rank}
                </span>
                <div
                  className="w-6 h-6 rounded-full flex items-center justify-center shrink-0"
                  style={{
                    backgroundColor: `${tierColor}18`,
                    color: tierColor,
                  }}
                >
                  <span className="text-[10px] font-bold">
                    {trader.initials}
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <span className="text-xs font-medium text-text-primary truncate block">
                    {trader.name}
                  </span>
                </div>
                <span className="font-mono text-xs text-text-secondary">
                  {Math.round(trader.winRate * 100)}%
                </span>
                <Sparkline
                  data={generateTrend(trader.id)}
                  width={40}
                  height={16}
                />
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // Full leaderboard view
  return (
    <div className="space-y-4">
      <h2 className="font-serif italic text-2xl text-text-primary">
        Leaderboard
      </h2>

      <div className="bg-surface rounded-xl border border-border overflow-hidden">
        <div className="grid grid-cols-[48px_1fr_80px_80px_80px_80px_80px] px-4 py-2.5 border-b border-border-light text-xs text-text-tertiary uppercase tracking-wider">
          <span>Rank</span>
          <span>Trader</span>
          <span className="text-right">Win Rate</span>
          <span className="text-right">Sharpe</span>
          <span className="text-right">Rep</span>
          <span className="text-right">Streak</span>
          <span className="text-right">Trend</span>
        </div>

        {traders.map((trader, i) => {
          const tierColor = tierColors[trader.tier] || "#9B9B9B";
          const animClass =
            i < 4
              ? i === 0
                ? "animate-fade-up"
                : i === 1
                  ? "animate-fade-up-delay-1"
                  : i === 2
                    ? "animate-fade-up-delay-2"
                    : "animate-fade-up-delay-3"
              : "";

          return (
            <div
              key={trader.id}
              className={`grid grid-cols-[48px_1fr_80px_80px_80px_80px_80px] px-4 py-3 items-center
                border-b border-border-light last:border-b-0
                hover:bg-surface-hover transition-colors cursor-pointer ${animClass}`}
            >
              <span className="font-mono text-sm font-bold text-text-tertiary">
                {trader.rank}
              </span>
              <div className="flex items-center gap-3">
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center"
                  style={{
                    backgroundColor: `${tierColor}18`,
                    color: tierColor,
                  }}
                >
                  <span className="text-xs font-bold">{trader.initials}</span>
                </div>
                <div>
                  <span className="text-sm font-medium text-text-primary block">
                    {trader.name}
                  </span>
                  <span className="text-xs text-text-tertiary">
                    {trader.dna}
                  </span>
                </div>
              </div>
              <span className="font-mono text-sm text-right text-text-primary">
                {Math.round(trader.winRate * 100)}%
              </span>
              <span className="font-mono text-sm text-right text-text-primary">
                {trader.sharpe.toFixed(1)}
              </span>
              <span className="font-mono text-sm text-right text-text-secondary">
                {trader.rep.toLocaleString()}
              </span>
              <span className="font-mono text-sm text-right text-gain">
                {trader.streak}W
              </span>
              <div className="flex justify-end">
                <Sparkline
                  data={generateTrend(trader.id)}
                  width={56}
                  height={20}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
