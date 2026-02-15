"use client";

import { useState } from "react";
import { traders } from "@/lib/mock-data";
import { tierColors, rankColors } from "@/lib/constants";
import TierBadge from "@/components/ui/TierBadge";
import Sparkline from "@/components/ui/Sparkline";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

const desks = ["Overall", "Tech Desk", "Energy Desk", "Options Desk", "Earnings Desk"];
const periods = ["30 Days", "90 Days", "All Time"];

function generateTrend(seed: number) {
  const data = [];
  let val = 50 + seed * 3;
  for (let i = 0; i < 10; i++) {
    val += Math.sin(seed + i) * 5 + Math.cos(i * seed) * 3;
    data.push(Math.round(val));
  }
  return data;
}

export default function BoardTab() {
  const [activeDesk, setActiveDesk] = useState("Overall");
  const [activePeriod, setActivePeriod] = useState("All Time");

  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-serif italic text-[28px] text-text-primary">
          Leaderboard
        </h2>
        <p className="text-sm text-text-tertiary mt-0.5">
          Top traders by composite score
        </p>
      </div>

      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          {desks.map((d) => (
            <button
              key={d}
              onClick={() => setActiveDesk(d)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                activeDesk === d
                  ? "bg-accent-light text-accent"
                  : "text-text-tertiary hover:bg-surface-hover"
              }`}
            >
              {d}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          {periods.map((p) => (
            <button
              key={p}
              onClick={() => setActivePeriod(p)}
              className={`px-2.5 py-1 rounded text-[10px] font-semibold transition-colors ${
                activePeriod === p
                  ? "bg-text-primary text-white"
                  : "text-text-tertiary hover:bg-surface-hover"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-surface rounded-xl border border-border overflow-hidden">
        <div className="hidden md:grid grid-cols-[52px_1fr_72px_72px_72px_56px_64px] px-5 py-3 border-b border-border-light text-[10px] text-text-tertiary uppercase tracking-wider font-semibold">
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
          const rkColor = rankColors[trader.rank];
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
              className={`grid grid-cols-[52px_1fr_72px_72px_72px_56px_64px] px-5 py-3.5 items-center
                border-b border-border-light last:border-b-0
                hover:bg-surface-hover transition-colors cursor-pointer ${animClass}`}
            >
              <span
                className="font-mono text-base font-bold"
                style={{ color: rkColor || "#9B9B9B" }}
              >
                {trader.rank}
              </span>
              <div className="flex items-center gap-3">
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
                  style={{ backgroundColor: `${tierColor}18`, color: tierColor }}
                >
                  <span className="text-xs font-bold">{trader.initials}</span>
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-text-primary truncate">
                      {trader.name}
                    </span>
                    <TierBadge tier={trader.tier} />
                  </div>
                  <span className="text-xs text-text-tertiary">{trader.dna}</span>
                </div>
              </div>
              <span className="font-mono text-sm font-semibold text-gain text-right">
                {Math.round(trader.winRate * 100)}%
              </span>
              <span className="font-mono text-sm text-right text-text-primary">
                {trader.sharpe.toFixed(1)}
              </span>
              <span className="font-mono text-sm text-right text-text-secondary">
                {trader.rep.toLocaleString()}
              </span>
              <span className="font-mono text-sm text-right text-gain font-semibold">
                {trader.streak}W
              </span>
              <div className="flex justify-end">
                <Sparkline data={generateTrend(trader.id)} width={48} height={18} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
