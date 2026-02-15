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
    <div className="bg-surface rounded-xl border border-border p-5 transition-all duration-200 hover:shadow-sm hover:-translate-y-0.5 hover:border-text-tertiary/30">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {prediction.hot && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-accent-light text-accent text-[10px] font-bold uppercase">
              <Flame className="w-2.5 h-2.5" />
              HOT
            </span>
          )}
          <span className="px-2 py-0.5 rounded bg-background text-text-tertiary text-[10px] font-medium uppercase">
            {prediction.category}
          </span>
        </div>
        <span className="text-xs text-text-tertiary font-mono">
          {prediction.volume.toLocaleString()} votes
        </span>
      </div>

      <p className="text-sm font-semibold text-text-primary mb-4">
        {prediction.question}
      </p>

      <div className="flex gap-2 mb-3">
        <button className="flex-1 py-2.5 rounded-lg bg-gain-light text-gain text-sm font-semibold hover:bg-gain/10 transition-colors">
          Yes &middot; {yesPct}%
        </button>
        <button className="flex-1 py-2.5 rounded-lg bg-loss-light text-loss text-sm font-semibold hover:bg-loss/10 transition-colors">
          No &middot; {noPct}%
        </button>
      </div>

      <div className="h-1.5 rounded-full bg-loss-light overflow-hidden">
        <div
          className="h-full rounded-full bg-gain"
          style={{ width: `${yesPct}%` }}
        />
      </div>
    </div>
  );
}
