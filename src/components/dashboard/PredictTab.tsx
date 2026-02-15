"use client";

import { useState } from "react";
import { predictions } from "@/lib/mock-data";
import PredictionCard from "@/components/cards/PredictionCard";

const categories = ["All", "Hot", "Mega Cap", "Macro", "Semiconductors", "EV", "Volatility"];

export default function PredictTab() {
  const [activeFilter, setActiveFilter] = useState("All");

  const filtered =
    activeFilter === "All"
      ? predictions
      : activeFilter === "Hot"
        ? predictions.filter((p) => p.hot)
        : predictions.filter((p) => p.category === activeFilter);

  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-serif italic text-[28px] text-text-primary">
          Predict
        </h2>
        <p className="text-sm text-text-tertiary mt-0.5">
          Community market predictions
        </p>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setActiveFilter(cat)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeFilter === cat
                ? "bg-accent-light text-accent"
                : "text-text-tertiary hover:bg-surface-hover hover:text-text-primary"
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {filtered.map((p, i) => (
          <div
            key={p.id}
            className={
              i === 0
                ? "animate-fade-up"
                : i === 1
                  ? "animate-fade-up-delay-1"
                  : i === 2
                    ? "animate-fade-up-delay-2"
                    : "animate-fade-up-delay-3"
            }
          >
            <PredictionCard prediction={p} />
          </div>
        ))}
      </div>
    </div>
  );
}
