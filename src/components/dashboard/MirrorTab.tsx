"use client";

import { currentUserProfile, behavioralTraits, achievements } from "@/lib/mock-data";
import Card from "@/components/ui/Card";
import TraitBar from "@/components/ui/TraitBar";
import TierBadge from "@/components/ui/TierBadge";
import AchievementCard from "@/components/cards/AchievementCard";
import RadarProfile from "@/components/charts/RadarProfile";
import { Share2 } from "lucide-react";

export default function MirrorTab() {
  const user = currentUserProfile;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-serif italic text-[28px] text-text-primary">
          The Mirror
        </h2>
        <p className="text-sm text-text-tertiary mt-0.5">Your Trading DNA</p>
      </div>

      {/* DNA Profile */}
      <Card hover={false} className="p-6 animate-fade-up">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left: Radar */}
          <div className="flex flex-col items-center">
            <RadarProfile />
            <h3 className="font-serif italic text-xl text-text-primary mt-2">
              {user.archetype}
            </h3>
            <TierBadge tier={user.tier} className="mt-2" />
          </div>

          {/* Right: Summary + Stats */}
          <div className="flex flex-col justify-center">
            <p className="text-sm text-text-secondary leading-relaxed">
              Exceptional sector focus — top 4% in semiconductor conviction.
              Strong entries and thesis quality. Vulnerability: hold discipline
              — exiting winners early, holding losers long.
            </p>

            <div className="mt-5 p-4 rounded-xl bg-accent-light border border-accent/10">
              <p className="text-[10px] font-bold uppercase tracking-widest text-accent mb-1.5">
                Signature Pattern
              </p>
              <p className="text-sm text-accent-dark font-medium leading-relaxed">
                Buys semis within 48hrs of ETF flow divergence — 14 trades, 11
                wins (78.6%)
              </p>
            </div>

            <div className="grid grid-cols-4 gap-4 mt-6 pt-5 border-t border-border-light">
              <div>
                <span className="text-[10px] text-text-tertiary uppercase tracking-wider">
                  Win Rate
                </span>
                <p className="font-mono text-xl font-bold text-gain">
                  {Math.round(user.winRate * 100)}%
                </p>
              </div>
              <div>
                <span className="text-[10px] text-text-tertiary uppercase tracking-wider">
                  Sharpe
                </span>
                <p className="font-mono text-xl font-bold text-text-primary">
                  {user.sharpe.toFixed(1)}
                </p>
              </div>
              <div>
                <span className="text-[10px] text-text-tertiary uppercase tracking-wider">
                  +Rep
                </span>
                <p className="font-mono text-xl font-bold text-accent">
                  {user.rep}
                </p>
              </div>
              <div>
                <span className="text-[10px] text-text-tertiary uppercase tracking-wider">
                  Level
                </span>
                <p className="font-mono text-xl font-bold text-text-primary">
                  {user.level}
                </p>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Behavioral Traits */}
      <Card hover={false} className="p-6 animate-fade-up-delay-1">
        <h3 className="text-sm font-semibold text-text-primary mb-5">
          Behavioral Traits
        </h3>
        <div className="space-y-3.5">
          {behavioralTraits.map((trait) => (
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
        <h3 className="text-sm font-semibold text-text-primary mb-4">
          Achievements
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {achievements.map((ach) => (
            <AchievementCard key={ach.id} achievement={ach} />
          ))}
        </div>
      </Card>

      {/* Share button */}
      <button className="w-full py-3.5 rounded-xl bg-dark text-white text-sm font-semibold flex items-center justify-center gap-2 hover:bg-dark-surface transition-colors animate-fade-up-delay-3">
        <Share2 className="w-4 h-4" />
        Share Trading DNA
      </button>
    </div>
  );
}
