"use client";

import { theses } from "@/lib/mock-data";
import ThesisCard from "@/components/cards/ThesisCard";

export default function RoomTab() {
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-serif italic text-[28px] text-text-primary">
            The Room
          </h2>
          <p className="text-sm text-text-tertiary mt-0.5">
            Live thesis feed from top traders
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button className="px-3 py-1.5 rounded-lg bg-accent-light text-accent text-xs font-semibold">
            Latest
          </button>
          <button className="px-3 py-1.5 rounded-lg text-text-tertiary text-xs font-medium hover:bg-surface-hover transition-colors">
            Top Signal
          </button>
          <button className="px-3 py-1.5 rounded-lg text-text-tertiary text-xs font-medium hover:bg-surface-hover transition-colors">
            Hot Takes
          </button>
        </div>
      </div>

      <div className="space-y-3">
        {theses.map((thesis, i) => (
          <ThesisCard key={thesis.id} thesis={thesis} index={i} />
        ))}
      </div>
    </div>
  );
}
