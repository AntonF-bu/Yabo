"use client";

import { currentUserProfile } from "@/lib/mock-data";
import { Flame } from "lucide-react";

export default function StreakBanner() {
  const user = currentUserProfile;
  const xpPct = Math.round((user.xp / user.xpToNext) * 100);

  return (
    <div className="bg-surface rounded-xl border border-border p-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-teal-light flex items-center justify-center">
          <Flame className="w-5 h-5 text-teal" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-text font-body">
              {user.streak}-day streak!
            </span>
          </div>
          <p className="text-xs text-text-ter font-body">
            Post a thesis to keep it going &middot; +50 XP
          </p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span className="font-mono text-sm font-bold text-teal">
          Lv.{user.level}
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
