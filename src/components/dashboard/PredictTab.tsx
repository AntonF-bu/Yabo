"use client";

import { useState } from "react";
import { predictions } from "@/lib/mock-data";
import PredictionCard from "@/components/cards/PredictionCard";
import MockDataBadge from "@/components/ui/MockDataBadge";

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
        <div className="flex items-center gap-3">
          <h2 className="font-display italic text-[28px] text-text">
            Predict
          </h2>
          <MockDataBadge />
        </div>
        <p className="text-sm text-text-ter mt-0.5 font-body">
          Community market predictions
        </p>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setActiveFilter(cat)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium font-mono transition-colors ${
              activeFilter === cat
                ? "bg-teal-light text-teal"
                : "text-text-ter hover:bg-surface-hover hover:text-text"
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
