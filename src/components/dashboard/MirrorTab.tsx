"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useUser } from "@clerk/nextjs";
import { useProfile } from "@/hooks/useProfile";
import { usePortfolio } from "@/hooks/usePortfolio";
import { currentUserProfile, behavioralTraits, achievements } from "@/lib/mock-data";
import { loadPortfolio, hasImportedData, clearImportedData } from "@/lib/storage";
import { analyzeAndSave } from "@/lib/analyze";
import { ComputedPortfolio, BehavioralTrait } from "@/types";
import Card from "@/components/ui/Card";
import TraitBar from "@/components/ui/TraitBar";
import TierBadge from "@/components/ui/TierBadge";
import AchievementCard from "@/components/cards/AchievementCard";
import RadarProfile from "@/components/charts/RadarProfile";
import MockDataBadge from "@/components/ui/MockDataBadge";
import { Share2, Database, X, RefreshCw, Upload, Loader2, Brain } from "lucide-react";

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
  const { user } = useUser();
  const { profile: dbProfile } = useProfile();
  const { trades: dbTrades, positions: dbPositions, cash: dbCash, totalValue: dbTotalValue } = usePortfolio();
  const mockUser = currentUserProfile;
  const [imported, setImported] = useState<ComputedPortfolio | null>(null);
  const [usingImported, setUsingImported] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    if (hasImportedData()) {
      const portfolio = loadPortfolio();
      if (portfolio) {
        setImported(portfolio);
        setUsingImported(true);
      }
    }
  }, []);

  // Determine data source priority: AI analysis > imported data > onboarding > mock
  const hasAiAnalysis = dbProfile?.ai_analyzed_at != null;
  const hasDbTraits = dbProfile && dbProfile.onboarding_complete && dbProfile.trait_entry_timing != null;
  const usingRealData = hasAiAnalysis || (usingImported && imported) || hasDbTraits;

  const traits: BehavioralTrait[] =
    hasAiAnalysis && dbProfile
      ? profileToTraits(dbProfile)
      : usingImported && imported
        ? imported.traits
        : hasDbTraits
          ? profileToTraits(dbProfile!)
          : behavioralTraits;

  const winRate = hasAiAnalysis && dbProfile?.ai_key_stats
    ? parseInt((dbProfile.ai_key_stats as Record<string, string>).winRate || "0") / 100
    : usingImported && imported ? imported.winRate : mockUser.winRate;
  const sharpe = usingImported && imported ? imported.sharpe : mockUser.sharpe;

  const displayArchetype = dbProfile?.archetype || null;
  const displayTier = dbProfile?.tier || "Rookie";
  const displayLevel = dbProfile?.level ?? 1;

  const aiKeyStats = hasAiAnalysis ? (dbProfile?.ai_key_stats as Record<string, string> | null) : null;
  const aiProfileText = hasAiAnalysis ? dbProfile?.ai_profile_text : null;
  const aiArchetypeDesc = hasAiAnalysis ? dbProfile?.ai_archetype_description : null;

  const handleClearImport = () => {
    clearImportedData();
    setImported(null);
    setUsingImported(false);
  };

  const handleRefreshAnalysis = useCallback(async () => {
    if (!user || !dbProfile || refreshing) return;
    setRefreshing(true);
    try {
      const tradesForAnalysis = dbTrades.map((t) => ({
        date: t.created_at,
        ticker: t.ticker,
        action: t.side,
        quantity: Number(t.quantity),
        price: Number(t.price),
        total: Number(t.total_value),
        sector: t.sector || undefined,
      }));
      const positionsForAnalysis = dbPositions.map((p) => ({
        ticker: p.ticker,
        shares: Number(p.shares),
        avgCost: Number(p.avg_cost),
        currentPrice: Number(p.current_price),
        sector: p.sector,
      }));
      await analyzeAndSave(user.id, tradesForAnalysis, positionsForAnalysis, dbTotalValue, dbCash);
      // Reload the page to refresh profile
      window.location.reload();
    } catch {
      // Silently fail
    }
    setRefreshing(false);
  }, [user, dbProfile, dbTrades, dbPositions, dbTotalValue, dbCash, refreshing]);

  // Empty state: no data at all
  const hasNoData = !hasAiAnalysis && !hasDbTraits && !usingImported;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-[28px] text-text">
            The Mirror
          </h2>
          <p className="text-sm text-text-ter mt-0.5 font-body">Your Trading DNA</p>
        </div>
        <div className="flex items-center gap-2">
          {hasAiAnalysis && dbTrades.length > 0 && (
            <button
              onClick={handleRefreshAnalysis}
              disabled={refreshing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs font-medium text-text-sec hover:bg-surface-hover transition-colors font-body"
            >
              {refreshing ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
              Refresh Analysis
            </button>
          )}
          {!usingRealData && <MockDataBadge />}
        </div>
      </div>

      {/* Imported Data Indicator */}
      {usingImported && !hasAiAnalysis && (
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

      {/* AI Analysis Banner */}
      {hasAiAnalysis && (
        <div className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-teal-light border border-teal/10 animate-fade-up">
          <Brain className="w-3.5 h-3.5 text-teal" />
          <span className="text-xs text-teal font-medium font-body">
            AI analysis powered by Claude &middot; Last updated {new Date(dbProfile!.ai_analyzed_at!).toLocaleDateString()}
          </span>
        </div>
      )}

      {/* Empty State */}
      {hasNoData && (
        <Card hover={false} className="p-8 text-center animate-fade-up">
          <div className="w-16 h-16 rounded-full bg-teal-light flex items-center justify-center mx-auto mb-4">
            <Upload className="w-8 h-8 text-teal" />
          </div>
          <h3 className="font-display text-lg text-text">Import your trades to unlock your Trading DNA</h3>
          <p className="text-sm text-text-ter mt-2 font-body max-w-md mx-auto">
            Upload a CSV of your trade history or try our demo data. Claude AI will analyze your patterns and generate a personalized trading profile.
          </p>
          <Link
            href="/dashboard/import"
            className="inline-flex items-center gap-2 mt-4 px-6 py-3 rounded-xl bg-text text-bg text-sm font-semibold hover:bg-text/80 transition-colors font-body"
          >
            <Upload className="w-4 h-4" />
            Import Trades
          </Link>
        </Card>
      )}

      {/* DNA Profile */}
      <Card hover={false} className="p-6 animate-fade-up">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left: Radar */}
          <div className="flex flex-col items-center">
            <RadarProfile traits={traits} />
            {displayArchetype ? (
              <h3 className="font-display text-xl text-text mt-2">
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
            {aiArchetypeDesc && (
              <p className="text-xs text-text-ter mt-1 text-center max-w-xs font-body">{aiArchetypeDesc}</p>
            )}
            <TierBadge tier={displayTier} className="mt-2" />
          </div>

          {/* Right: Summary + Stats */}
          <div className="flex flex-col justify-center">
            <p className="text-sm text-text-sec leading-relaxed font-body">
              {aiProfileText
                ? aiProfileText
                : hasDbTraits
                  ? "Your preliminary Trading DNA based on your onboarding responses. Trade more to refine these scores."
                  : "Exceptional sector focus -- top 4% in semiconductor conviction. Strong entries and thesis quality. Vulnerability: hold discipline -- exiting winners early, holding losers long."
              }
            </p>

            <div className="mt-5 p-4 rounded-xl bg-teal-light border border-teal/10">
              <p className="text-[10px] font-bold uppercase tracking-widest text-teal mb-1.5 font-mono">
                Signature Pattern
              </p>
              <p className="text-sm text-teal font-medium leading-relaxed font-body">
                {aiKeyStats?.signaturePattern
                  ? aiKeyStats.signaturePattern
                  : hasDbTraits
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
                  {aiKeyStats?.winRate || `${Math.round(winRate * 100)}%`}
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
