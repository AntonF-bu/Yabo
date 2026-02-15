"use client";

import { useState, useEffect } from "react";
import { currentUserProfile, behavioralTraits, achievements } from "@/lib/mock-data";
import { loadPortfolio, hasImportedData, clearImportedData } from "@/lib/storage";
import { ComputedPortfolio, BehavioralTrait } from "@/types";
import Card from "@/components/ui/Card";
import TraitBar from "@/components/ui/TraitBar";
import TierBadge from "@/components/ui/TierBadge";
import AchievementCard from "@/components/cards/AchievementCard";
import RadarProfile from "@/components/charts/RadarProfile";
import { Share2, Database, X } from "lucide-react";

export default function MirrorTab() {
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

  const traits: BehavioralTrait[] =
    usingImported && imported ? imported.traits : behavioralTraits;
  const winRate = usingImported && imported ? imported.winRate : user.winRate;
  const sharpe = usingImported && imported ? imported.sharpe : user.sharpe;

  const handleClearImport = () => {
    clearImportedData();
    setImported(null);
    setUsingImported(false);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display italic text-[28px] text-text">
          The Mirror
        </h2>
        <p className="text-sm text-text-ter mt-0.5 font-body">Your Trading DNA</p>
      </div>

      {/* Imported Data Indicator */}
      {usingImported && (
        <div className="flex items-center justify-between px-4 py-2.5 rounded-lg bg-teal-light border border-teal/10 animate-fade-up">
          <div className="flex items-center gap-2 text-xs text-teal font-medium">
            <Database className="w-3.5 h-3.5" />
            Traits computed from imported trade data
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

      {/* DNA Profile */}
      <Card hover={false} className="p-6 animate-fade-up">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left: Radar */}
          <div className="flex flex-col items-center">
            <RadarProfile traits={traits} />
            <h3 className="font-display italic text-xl text-text mt-2">
              {user.archetype}
            </h3>
            <TierBadge tier={user.tier} className="mt-2" />
          </div>

          {/* Right: Summary + Stats */}
          <div className="flex flex-col justify-center">
            <p className="text-sm text-text-sec leading-relaxed font-body">
              Exceptional sector focus -- top 4% in semiconductor conviction.
              Strong entries and thesis quality. Vulnerability: hold discipline
              -- exiting winners early, holding losers long.
            </p>

            <div className="mt-5 p-4 rounded-xl bg-teal-light border border-teal/10">
              <p className="text-[10px] font-bold uppercase tracking-widest text-teal mb-1.5 font-mono">
                Signature Pattern
              </p>
              <p className="text-sm text-teal font-medium leading-relaxed font-body">
                Buys semis within 48hrs of ETF flow divergence -- 14 trades, 11
                wins (78.6%)
              </p>
            </div>

            <div className="grid grid-cols-4 gap-4 mt-6 pt-5 border-t border-border">
              <div>
                <span className="text-[10px] text-text-ter uppercase tracking-wider font-mono">
                  Win Rate
                </span>
                <p className="font-mono text-xl font-bold text-green">
                  {Math.round(winRate * 100)}%
                </p>
              </div>
              <div>
                <span className="text-[10px] text-text-ter uppercase tracking-wider font-mono">
                  Sharpe
                </span>
                <p className="font-mono text-xl font-bold text-text">
                  {sharpe.toFixed(1)}
                </p>
              </div>
              <div>
                <span className="text-[10px] text-text-ter uppercase tracking-wider font-mono">
                  +Rep
                </span>
                <p className="font-mono text-xl font-bold text-teal">
                  {user.rep}
                </p>
              </div>
              <div>
                <span className="text-[10px] text-text-ter uppercase tracking-wider font-mono">
                  Level
                </span>
                <p className="font-mono text-xl font-bold text-text">
                  {user.level}
                </p>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Behavioral Traits */}
      <Card hover={false} className="p-6 animate-fade-up-delay-1">
        <h3 className="text-sm font-semibold text-text mb-5 font-body">
          Behavioral Traits
        </h3>
        <div className="space-y-3.5">
          {traits.map((trait) => (
            <TraitBar
              key={trait.name}
              name={trait.name}
              score={trait.score}
              percentile={trait.percentile}
              trend={trait.trend}
            />
          ))}
        </div>
      </Card>

      {/* Achievements */}
      <Card hover={false} className="p-6 animate-fade-up-delay-2">
        <h3 className="text-sm font-semibold text-text mb-4 font-body">
          Achievements
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {achievements.map((ach) => (
            <AchievementCard key={ach.id} achievement={ach} />
          ))}
        </div>
      </Card>

      {/* Share button */}
      <button className="w-full py-3.5 rounded-xl bg-surface text-text text-sm font-semibold flex items-center justify-center gap-2 hover:bg-surface-hover transition-colors animate-fade-up-delay-3 border border-border font-body">
        <Share2 className="w-4 h-4" />
        Share Trading DNA
      </button>
    </div>
  );
}
