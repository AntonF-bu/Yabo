"use client";

import { currentUserProfile, trendingTickers, predictions } from "@/lib/mock-data";
import TickerCard from "@/components/cards/TickerCard";
import PredictionCard from "@/components/cards/PredictionCard";
import StreakBanner from "@/components/gamification/StreakBanner";
import DailyChallenge from "@/components/gamification/DailyChallenge";

export default function DiscoverTab() {
  const user = currentUserProfile;

  return (
    <div className="space-y-6">
      {/* Greeting + Portfolio */}
      <div className="animate-fade-up">
        <h2 className="font-serif italic text-[28px] text-text-primary">
          Good morning
        </h2>
        <div className="flex items-baseline gap-3 mt-1">
          <span className="font-mono text-[44px] font-bold text-text-primary leading-none">
            ${user.portfolioValue.toLocaleString()}
          </span>
          <span className="font-mono text-base font-semibold text-gain">
            +${user.pnl.toLocaleString()} ({user.pnlPercent}%)
          </span>
        </div>
        <p className="text-sm text-text-tertiary mt-1">
          Simulated portfolio &middot; Started ${user.startingValue.toLocaleString()}
        </p>
      </div>

      {/* Streak */}
      <div className="animate-fade-up-delay-1">
        <StreakBanner />
      </div>

      {/* Daily Challenge */}
      <div className="animate-fade-up-delay-2">
        <DailyChallenge />
      </div>

      {/* Trending */}
      <div className="animate-fade-up-delay-3">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-text-primary">
            Trending on Yabo
          </h3>
          <button className="text-sm font-medium text-accent hover:text-accent-dark transition-colors">
            See all →
          </button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {trendingTickers.map((t) => (
            <TickerCard key={t.ticker} ticker={t} />
          ))}
        </div>
      </div>

      {/* Predictions */}
      <div className="animate-fade-up-delay-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-text-primary">
            Predictions
          </h3>
        </div>
        <div className="space-y-3">
          {predictions.slice(0, 3).map((p) => (
            <PredictionCard key={p.id} prediction={p} />
          ))}
        </div>
      </div>
    </div>
  );
}
