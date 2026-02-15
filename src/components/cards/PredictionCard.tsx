"use client";

import { Prediction } from "@/types";
import { Flame } from "lucide-react";

interface PredictionCardProps {
  prediction: Prediction;
}

export default function PredictionCard({ prediction }: PredictionCardProps) {
  const yesPct = Math.round(prediction.yesProb * 100);
  const noPct = 100 - yesPct;

  return (
    <div className="bg-surface rounded-xl border border-border p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-border-accent hover:shadow-[0_4px_24px_rgba(0,0,0,0.3)]">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {prediction.hot && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-teal-light text-teal text-[10px] font-mono font-bold uppercase tracking-wider">
              <Flame className="w-2.5 h-2.5" />
              HOT
            </span>
          )}
          <span className="px-2 py-0.5 rounded bg-teal-light text-teal text-[10px] font-mono font-medium uppercase tracking-wider">
            {prediction.category}
          </span>
        </div>
        <span className="text-xs text-text-ter font-mono">
          {prediction.volume.toLocaleString()} votes
        </span>
      </div>

      <p className="text-sm font-semibold text-text mb-4 font-body">
        {prediction.question}
      </p>

      <div className="flex gap-2 mb-3" style={{ opacity: 0.35, pointerEvents: "none" }}>
        <span className="flex-1 py-2.5 rounded-lg bg-green-light text-green text-sm font-semibold font-body text-center cursor-not-allowed">
          Yes &middot; {yesPct}%
        </span>
        <span className="flex-1 py-2.5 rounded-lg bg-red-light text-red text-sm font-semibold font-body text-center cursor-not-allowed">
          No &middot; {noPct}%
        </span>
      </div>

      <div className="h-1.5 rounded-full bg-red-light overflow-hidden">
        <div
          className="h-full rounded-full bg-green"
          style={{ width: `${yesPct}%` }}
        />
      </div>
    </div>
  );
}
