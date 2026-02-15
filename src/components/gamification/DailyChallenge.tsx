"use client";

import { dailyChallenge } from "@/lib/mock-data";
import { Zap } from "lucide-react";

export default function DailyChallenge() {
  const ch = dailyChallenge;

  return (
    <div className="bg-elevated rounded-xl p-5">
      <div className="flex items-center gap-2 mb-3">
        <Zap className="w-4 h-4 text-teal" />
        <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-teal">
          Daily Challenge
        </span>
      </div>
      <p className="text-sm font-semibold text-text font-body">{ch.title}</p>
      <p className="text-xs text-text-ter mt-1 font-body">{ch.description}</p>
      <div className="flex items-center justify-between mt-4">
        <div className="flex-1 mr-4">
          <div className="h-1.5 rounded-full bg-text-muted overflow-hidden">
            <div
              className="h-full rounded-full bg-teal"
              style={{
                width: `${(ch.progress / ch.total) * 100}%`,
              }}
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-ter font-mono">
            {ch.progress}/{ch.total}
          </span>
          <span className="text-xs font-bold text-teal font-mono">
            +{ch.xpReward} XP
          </span>
        </div>
      </div>
    </div>
  );
}
