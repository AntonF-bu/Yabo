"use client";

import { discoverStats } from "@/lib/guide-content";

export default function DiscoverGuideExtra() {
  return (
    <div className="space-y-1">
      {discoverStats.map((stat) => (
        <p key={stat} className="text-xs text-text-ter font-mono">{stat}</p>
      ))}
    </div>
  );
}
