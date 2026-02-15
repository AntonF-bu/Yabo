"use client";

import { useState, useEffect } from "react";
import { useUser } from "@clerk/nextjs";
import { useProfile } from "@/hooks/useProfile";
import { usePortfolio } from "@/hooks/usePortfolio";
import { traders, currentUserProfile } from "@/lib/mock-data";
import { loadPortfolio, hasImportedData } from "@/lib/storage";
import { tierColors } from "@/lib/constants";
import { ComputedPortfolio, Trader } from "@/types";
import TierBadge from "@/components/ui/TierBadge";
import Sparkline from "@/components/ui/Sparkline";
import MockDataBadge from "@/components/ui/MockDataBadge";
import { Database } from "lucide-react";
import GuidePanel from "@/components/guide/GuidePanel";
import TierTable from "@/components/guide/TierTable";

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

function getRankColor(rank: number): string {
  if (rank === 1) return "#9A7B5B";
  if (rank === 2 || rank === 3) return "#A09A94";
  return "#D5D0C8";
}

export default function BoardTab({ guideActive }: { guideActive?: boolean }) {
  const { user } = useUser();
  const { profile } = useProfile();
  const { trades } = usePortfolio();
  const firstName =
    user?.username ||
    user?.firstName ||
    "Trader";
  const [activeDesk, setActiveDesk] = useState("Overall");
  const [activePeriod, setActivePeriod] = useState("All Time");
  const [imported, setImported] = useState<ComputedPortfolio | null>(null);

  useEffect(() => {
    if (hasImportedData()) {
      const portfolio = loadPortfolio();
      if (portfolio) setImported(portfolio);
    }
  }, []);

  const allTraders: (Trader & { isYou?: boolean })[] = [...traders];

  if (imported) {
    const userComposite = imported.winRate * 50 + (imported.sharpe > 0 ? imported.sharpe * 20 : 0);

    let insertIdx = allTraders.length;
    for (let i = 0; i < allTraders.length; i++) {
      const traderComposite = allTraders[i].winRate * 50 + allTraders[i].sharpe * 20;
      if (userComposite >= traderComposite) {
        insertIdx = i;
        break;
      }
    }

    const userTrader: Trader & { isYou?: boolean } = {
      id: 999,
      name: currentUserProfile.name,
      dna: "Your Imported Stats",
      winRate: imported.winRate,
      sharpe: imported.sharpe,
      rep: currentUserProfile.rep,
      rank: insertIdx + 1,
      initials: currentUserProfile.initials,
      streak: currentUserProfile.streak,
      level: currentUserProfile.level,
      xp: currentUserProfile.xp,
      tier: currentUserProfile.tier as Trader["tier"],
      isYou: true,
    };

    allTraders.splice(insertIdx, 0, userTrader);
    allTraders.forEach((t, i) => {
      t.rank = i + 1;
    });
  }

  return (
    <div className="space-y-5">
      {guideActive && (
        <GuidePanel section="board">
          <TierTable />
        </GuidePanel>
      )}
      <div>
        <div className="flex items-center gap-3">
          <h2 className="font-display text-[28px] text-text">
            Leaderboard
          </h2>
          <MockDataBadge />
        </div>
        <p className="text-sm text-text-ter mt-0.5 font-body">
          Top traders by composite score
        </p>
      </div>

      {/* Your Status */}
      <div className="rounded-xl p-4 bg-teal-muted border border-teal/10 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-text font-body">{firstName}</span>
          <span className="text-xs text-text-sec font-body">
            {profile?.archetype || "Unranked"}
          </span>
        </div>
        <div className="flex items-center gap-5">
          <div className="text-center">
            <p className="font-mono text-sm font-bold text-teal">{trades.length}</p>
            <p className="text-[10px] text-text-ter uppercase tracking-wider font-mono">Trades</p>
          </div>
          <div className="text-center">
            <p className="font-mono text-sm font-bold text-text">{profile?.tier || "Rookie"}</p>
            <p className="text-[10px] text-text-ter uppercase tracking-wider font-mono">Tier</p>
          </div>
          <div className="text-center">
            <p className="font-mono text-sm font-bold text-text">Unranked</p>
            <p className="text-[10px] text-text-ter uppercase tracking-wider font-mono">Rank</p>
          </div>
        </div>
      </div>

      {imported && (
        <div className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-teal-light border border-teal/10">
          <Database className="w-3.5 h-3.5 text-teal" />
          <span className="text-xs text-teal font-medium">
            Your imported stats are shown on the board
          </span>
        </div>
      )}

      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          {desks.map((d) => (
            <button
              key={d}
              onClick={() => setActiveDesk(d)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium font-mono transition-colors ${
                activeDesk === d
                  ? "bg-text text-bg"
                  : "text-text-ter hover:bg-surface-hover"
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
              className={`px-2.5 py-1 rounded text-[10px] font-semibold font-mono transition-colors ${
                activePeriod === p
                  ? "bg-text text-bg"
                  : "text-text-ter hover:bg-surface-hover"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-surface rounded-xl border border-border overflow-hidden">
        <div className="hidden md:grid grid-cols-[52px_1fr_72px_72px_72px_56px_64px] px-5 py-3 border-b border-border text-[10px] text-text-ter uppercase tracking-wider font-semibold font-mono">
          <span>Rank</span>
          <span>Trader</span>
          <span className="text-right">Win Rate</span>
          <span className="text-right">Sharpe</span>
          <span className="text-right">Rep</span>
          <span className="text-right">Streak</span>
          <span className="text-right">Trend</span>
        </div>

        {allTraders.map((trader, i) => {
          const isYou = "isYou" in trader && trader.isYou;
          const tierColor = tierColors[trader.tier] || "#9B9B9B";
          const rkColor = getRankColor(trader.rank);
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
                border-b border-border last:border-b-0
                hover:bg-surface-hover transition-colors ${animClass}
                ${isYou ? "bg-teal-light/30 ring-1 ring-teal/10" : ""}`}
            >
              <span
                className="font-display text-base font-bold"
                style={{ color: rkColor }}
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
                    <span className="text-sm font-semibold text-text truncate">
                      {trader.name}
                    </span>
                    <TierBadge tier={trader.tier} />
                    {isYou && (
                      <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-text text-bg">
                        YOU
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-text-ter">{trader.dna}</span>
                </div>
              </div>
              <span className="font-mono text-sm font-semibold text-green text-right">
                {Math.round(trader.winRate * 100)}%
              </span>
              <span className="font-mono text-sm text-right text-text">
                {trader.sharpe.toFixed(1)}
              </span>
              <span className="font-mono text-sm text-right text-text-sec">
                {trader.rep.toLocaleString()}
              </span>
              <span className="font-mono text-sm text-right text-green font-semibold">
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
