"use client";

import { dailyChallenge } from "@/lib/mock-data";
import { Zap } from "lucide-react";

export default function DailyChallenge() {
  const ch = dailyChallenge;

  return (
    <div className="bg-dark rounded-xl p-5 text-white">
      <div className="flex items-center gap-2 mb-3">
        <Zap className="w-4 h-4 text-accent" />
        <span className="text-[10px] font-bold uppercase tracking-widest text-accent">
          Daily Challenge
        </span>
      </div>
      <p className="text-sm font-semibold text-white">{ch.title}</p>
      <p className="text-xs text-white/50 mt-1">{ch.description}</p>
      <div className="flex items-center justify-between mt-4">
        <div className="flex-1 mr-4">
          <div className="h-1.5 rounded-full bg-dark-border overflow-hidden">
            <div
              className="h-full rounded-full bg-accent"
              style={{
                width: `${(ch.progress / ch.total) * 100}%`,
              }}
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-white/40 font-mono">
            {ch.progress}/{ch.total}
          </span>
          <span className="text-xs font-bold text-accent font-mono">
            +{ch.xpReward} XP
          </span>
        </div>
      </div>
    </div>
  );
}
