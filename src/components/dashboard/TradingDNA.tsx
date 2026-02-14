"use client";

import { currentUser } from "@/lib/mock-data";
import { behavioralTraits } from "@/lib/mock-data";
import { tierColors } from "@/lib/constants";
import StatCard from "@/components/ui/StatCard";
import Card from "@/components/ui/Card";
import { TrendingUp, TrendingDown, Minus, Award, Target, Zap, Shield, BarChart3, Clock } from "lucide-react";

const achievements = [
  { name: "Thesis Machine", description: "50 theses published", progress: 100, icon: Target },
  { name: "Sharp Shooter", description: "Sharpe ratio > 1.5 for 30d", progress: 100, icon: Zap },
  { name: "Win Streak", description: "10 consecutive wins", progress: 50, icon: Award },
  { name: "Risk Master", description: "No stop-loss breaches in 30d", progress: 100, icon: Shield },
  { name: "Sector Alpha", description: "Top 5% sector returns", progress: 80, icon: BarChart3 },
  { name: "Diamond Hands", description: "Hold to target 10 times", progress: 30, icon: Clock },
];

export default function TradingDNA() {
  const user = currentUser;
  const tierColor = tierColors[user.tier] || "#9B9B9B";

  return (
    <div className="space-y-6">
      <h2 className="font-serif italic text-2xl text-text-primary">
        Trading DNA
      </h2>

      {/* Profile Card */}
      <Card hover={false} className="p-6 animate-fade-up">
        <div className="flex items-start gap-5">
          <div
            className="w-16 h-16 rounded-2xl flex items-center justify-center shrink-0"
            style={{ backgroundColor: `${tierColor}18`, color: tierColor }}
          >
            <span className="text-xl font-bold">{user.initials}</span>
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h3 className="text-lg font-semibold text-text-primary">
                {user.name}
              </h3>
              <span
                className="px-2.5 py-0.5 rounded-md text-xs font-medium"
                style={{
                  backgroundColor: `${tierColor}18`,
                  color: tierColor,
                }}
              >
                {user.tier}
              </span>
            </div>
            <p className="text-sm text-accent font-medium mt-0.5">
              {user.dna}
            </p>
            <p className="text-sm text-text-secondary mt-3 leading-relaxed">
              Exceptional sector focus — top 4% in semiconductor conviction.
              Strong entries and thesis quality. Vulnerability: hold discipline
              — exiting winners early, holding losers long.
            </p>
          </div>
        </div>

        {/* Signature Pattern */}
        <div className="mt-5 p-4 rounded-xl bg-accent-light border border-accent/10">
          <p className="text-xs text-accent/70 font-medium uppercase tracking-wider mb-1">
            Signature Pattern
          </p>
          <p className="text-sm text-accent-dark font-medium">
            Buys semis within 48hrs of ETF flow divergence — 14 trades, 11 wins
            (78.6%)
          </p>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-4 gap-6 mt-6 pt-5 border-t border-border-light">
          <StatCard
            label="Win Rate"
            value={`${Math.round(user.winRate * 100)}%`}
            trend="up"
            trendValue="+3.2%"
          />
          <StatCard
            label="Sharpe"
            value={user.sharpe.toFixed(1)}
            trend="up"
            trendValue="+0.2"
          />
          <StatCard
            label="+Rep"
            value={user.rep.toLocaleString()}
            trend="up"
            trendValue="+240"
          />
          <StatCard
            label="Level"
            value={`${user.level}`}
            trend="up"
            trendValue={`${user.xp.toLocaleString()} XP`}
          />
        </div>
      </Card>

      {/* Behavioral Traits */}
      <Card hover={false} className="p-6 animate-fade-up-delay-1">
        <h3 className="text-sm font-semibold text-text-primary mb-4">
          Behavioral Traits
        </h3>
        <div className="space-y-4">
          {behavioralTraits.map((trait) => (
            <div key={trait.name} className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-primary">{trait.name}</span>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-text-tertiary">
                    Top {100 - trait.percentile}%
                  </span>
                  <div className="flex items-center gap-1">
                    {trait.trend === "up" && (
                      <TrendingUp className="w-3 h-3 text-gain" />
                    )}
                    {trait.trend === "down" && (
                      <TrendingDown className="w-3 h-3 text-loss" />
                    )}
                    {trait.trend === "flat" && (
                      <Minus className="w-3 h-3 text-text-tertiary" />
                    )}
                  </div>
                  <span className="font-mono text-sm font-medium text-text-primary w-8 text-right">
                    {trait.score}
                  </span>
                </div>
              </div>
              <div className="h-2 rounded-full bg-border-light overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{
                    width: `${trait.score}%`,
                    background:
                      trait.score >= 75
                        ? "linear-gradient(90deg, #E85D26, #22A06B)"
                        : trait.score >= 60
                          ? "linear-gradient(90deg, #E85D26, #FF991F)"
                          : "linear-gradient(90deg, #DE350B, #E85D26)",
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Achievements */}
      <Card hover={false} className="p-6 animate-fade-up-delay-2">
        <h3 className="text-sm font-semibold text-text-primary mb-4">
          Achievements
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {achievements.map((ach) => {
            const Icon = ach.icon;
            const isComplete = ach.progress === 100;
            return (
              <div
                key={ach.name}
                className={`p-3 rounded-lg border ${
                  isComplete
                    ? "border-accent/20 bg-accent-light/50"
                    : "border-border-light bg-background"
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <Icon
                    className={`w-4 h-4 ${isComplete ? "text-accent" : "text-text-tertiary"}`}
                  />
                  <span
                    className={`text-xs font-medium ${isComplete ? "text-accent" : "text-text-secondary"}`}
                  >
                    {ach.name}
                  </span>
                </div>
                <p className="text-xs text-text-tertiary mb-2">
                  {ach.description}
                </p>
                <div className="h-1 rounded-full bg-border-light overflow-hidden">
                  <div
                    className="h-full rounded-full bg-accent transition-all duration-500"
                    style={{ width: `${ach.progress}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
