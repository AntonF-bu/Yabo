"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useProfile } from "@/hooks/useProfile";
import { currentUserProfile, behavioralTraits, achievements } from "@/lib/mock-data";
import { loadPortfolio, hasImportedData, clearImportedData } from "@/lib/storage";
import { ComputedPortfolio, BehavioralTrait } from "@/types";
import Card from "@/components/ui/Card";
import TraitBar from "@/components/ui/TraitBar";
import TierBadge from "@/components/ui/TierBadge";
import AchievementCard from "@/components/cards/AchievementCard";
import RadarProfile from "@/components/charts/RadarProfile";
import MockDataBadge from "@/components/ui/MockDataBadge";
import { Share2, Database, X } from "lucide-react";

// Build trait array from Supabase profile data
function profileToTraits(p: { trait_entry_timing?: number; trait_hold_discipline?: number; trait_position_sizing?: number; trait_conviction_accuracy?: number; trait_risk_management?: number; trait_sector_focus?: number; trait_drawdown_resilience?: number; trait_thesis_quality?: number }): BehavioralTrait[] {
  return [
    { name: "Entry Timing", score: p.trait_entry_timing ?? 50, percentile: p.trait_entry_timing ?? 50, trend: "flat" as const },
    { name: "Hold Discipline", score: p.trait_hold_discipline ?? 50, percentile: p.trait_hold_discipline ?? 50, trend: "flat" as const },
    { name: "Position Sizing", score: p.trait_position_sizing ?? 50, percentile: p.trait_position_sizing ?? 50, trend: "flat" as const },
    { name: "Conviction Accuracy", score: p.trait_conviction_accuracy ?? 50, percentile: p.trait_conviction_accuracy ?? 50, trend: "flat" as const },
    { name: "Risk Management", score: p.trait_risk_management ?? 50, percentile: p.trait_risk_management ?? 50, trend: "flat" as const },
    { name: "Sector Focus", score: p.trait_sector_focus ?? 50, percentile: p.trait_sector_focus ?? 50, trend: "flat" as const },
    { name: "Drawdown Resilience", score: p.trait_drawdown_resilience ?? 50, percentile: p.trait_drawdown_resilience ?? 50, trend: "flat" as const },
    { name: "Thesis Quality", score: p.trait_thesis_quality ?? 50, percentile: p.trait_thesis_quality ?? 50, trend: "flat" as const },
  ];
}

export default function MirrorTab() {
  const { profile: dbProfile } = useProfile();
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

  // Priority: imported data > Supabase profile > mock data
  const hasDbTraits = dbProfile && dbProfile.onboarding_complete && dbProfile.trait_entry_timing != null;
  const usingRealData = (usingImported && imported) || hasDbTraits;
  const traits: BehavioralTrait[] =
    usingImported && imported
      ? imported.traits
      : hasDbTraits
        ? profileToTraits(dbProfile)
        : behavioralTraits;
  const winRate = usingImported && imported ? imported.winRate : user.winRate;
  const sharpe = usingImported && imported ? imported.sharpe : user.sharpe;

  const displayArchetype = dbProfile?.archetype || null;
  const displayTier = dbProfile?.tier || "Rookie";
  const displayLevel = dbProfile?.level ?? 1;

  const handleClearImport = () => {
    clearImportedData();
    setImported(null);
    setUsingImported(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display italic text-[28px] text-text">
            The Mirror
          </h2>
          <p className="text-sm text-text-ter mt-0.5 font-body">Your Trading DNA</p>
        </div>
        {!usingRealData && <MockDataBadge />}
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
            {displayArchetype ? (
              <h3 className="font-display italic text-xl text-text mt-2">
                {displayArchetype}
              </h3>
            ) : (
              <Link
                href="/onboarding"
                className="text-sm text-teal hover:text-teal/80 transition-colors font-body mt-2"
              >
                Complete onboarding to discover your archetype
              </Link>
            )}
            <TierBadge tier={displayTier} className="mt-2" />
          </div>

          {/* Right: Summary + Stats */}
          <div className="flex flex-col justify-center">
            <p className="text-sm text-text-sec leading-relaxed font-body">
              {hasDbTraits
                ? "Your preliminary Trading DNA based on your onboarding responses. Trade more to refine these scores."
                : "Exceptional sector focus -- top 4% in semiconductor conviction. Strong entries and thesis quality. Vulnerability: hold discipline -- exiting winners early, holding losers long."
              }
            </p>

            <div className="mt-5 p-4 rounded-xl bg-teal-light border border-teal/10">
              <p className="text-[10px] font-bold uppercase tracking-widest text-teal mb-1.5 font-mono">
                Signature Pattern
              </p>
              <p className="text-sm text-teal font-medium leading-relaxed font-body">
                {hasDbTraits
                  ? "Your signature pattern will emerge as you trade. Keep going."
                  : "Buys semis within 48hrs of ETF flow divergence -- 14 trades, 11 wins (78.6%)"
                }
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
                  Tier
                </span>
                <p className="font-mono text-xl font-bold text-teal">
                  {displayTier}
                </p>
              </div>
              <div>
                <span className="text-[10px] text-text-ter uppercase tracking-wider font-mono">
                  Level
                </span>
                <p className="font-mono text-xl font-bold text-text">
                  {displayLevel}
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

      {/* Share button (disabled) */}
      <div
        className="w-full py-3.5 rounded-xl bg-surface text-text text-sm font-semibold flex items-center justify-center gap-2 animate-fade-up-delay-3 border border-border font-body"
        style={{ opacity: 0.35, cursor: "not-allowed" }}
      >
        <Share2 className="w-4 h-4" />
        Share Trading DNA
      </div>
    </div>
  );
}
