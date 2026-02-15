"use client";

import { useProfile } from "@/hooks/useProfile";
import { Flame } from "lucide-react";

export default function StreakBanner() {
  const { profile } = useProfile();

  const level = profile?.level ?? 1;
  const xp = profile?.xp ?? 0;
  const streak = profile?.streak ?? 0;
  const xpPerLevel = 100;
  const xpPct = Math.min(100, Math.round((xp % xpPerLevel) / xpPerLevel * 100));

  return (
    <div className="bg-surface rounded-xl border border-border p-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-teal-light flex items-center justify-center">
          <Flame className="w-5 h-5 text-teal" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-text font-body">
              {streak > 0 ? `${streak}-day streak!` : "Start your streak!"}
            </span>
          </div>
          <p className="text-xs text-text-ter font-body">
            {streak > 0
              ? "Keep trading to extend your streak"
              : "Trade today to begin"}
            {" "}&middot; +50 XP
          </p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span className="font-mono text-sm font-bold text-teal">
          Lv.{level}
        </span>
        <div className="w-20 h-1.5 rounded-full bg-text-muted overflow-hidden">
          <div
            className="h-full rounded-full bg-teal"
            style={{ width: `${xpPct}%` }}
          />
        </div>
      </div>
    </div>
  );
}
