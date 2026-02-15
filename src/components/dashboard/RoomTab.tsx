"use client";

import { theses } from "@/lib/mock-data";
import ThesisCard from "@/components/cards/ThesisCard";
import MockDataBadge from "@/components/ui/MockDataBadge";

export default function RoomTab() {
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="font-display italic text-[28px] text-text">
              The Room
            </h2>
            <MockDataBadge />
          </div>
          <p className="text-sm text-text-ter mt-0.5 font-body">
            Live thesis feed from top traders
          </p>
        </div>
        <div className="flex items-center gap-2" style={{ opacity: 0.35, pointerEvents: "none" }}>
          <span className="px-3 py-1.5 rounded-lg bg-teal-light text-teal text-xs font-semibold font-mono cursor-not-allowed">
            Latest
          </span>
          <span className="px-3 py-1.5 rounded-lg text-text-ter text-xs font-medium font-mono cursor-not-allowed">
            Top Signal
          </span>
          <span className="px-3 py-1.5 rounded-lg text-text-ter text-xs font-medium font-mono cursor-not-allowed">
            Hot Takes
          </span>
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
