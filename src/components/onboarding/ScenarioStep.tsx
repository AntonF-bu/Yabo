"use client";

import { Check } from "lucide-react";

const options = [
  { id: "buy-dip", label: "Buy the dip", desc: "This is noise. I am adding to my position." },
  { id: "hold", label: "Hold and wait", desc: "No action until I see how the market reacts at open." },
  { id: "trim", label: "Trim the position", desc: "Cut half now, reassess with the rest." },
  { id: "stop-out", label: "Stop out", desc: "Hit my risk limit. Sell everything and move on." },
];

interface ScenarioStepProps {
  value: string;
  onChange: (value: string) => void;
}

export default function ScenarioStep({ value, onChange }: ScenarioStepProps) {
  return (
    <div className="max-w-xl mx-auto px-6">
      <h2 className="font-display text-[32px] text-text text-center">
        Quick scenario:
      </h2>
      <p className="text-sm text-text-sec font-body text-center mt-2 mb-8 leading-relaxed max-w-md mx-auto">
        You are holding NVDA at $140. It drops 8% in pre-market on news of export
        restrictions to China. The broader market is flat. Your position is now
        -$1,120. What do you do?
      </p>

      <div className="space-y-3">
        {options.map((opt) => {
          const isSelected = value === opt.id;
          return (
            <button
              key={opt.id}
              onClick={() => onChange(opt.id)}
              className={`relative w-full p-4 rounded-xl border text-left transition-all duration-200
                ${isSelected
                  ? "border-teal bg-teal-muted"
                  : "border-border bg-surface hover:border-border-accent"
                }`}
            >
              {isSelected && (
                <div className="absolute top-4 right-4">
                  <Check className="w-4 h-4 text-teal" />
                </div>
              )}
              <p className={`text-sm font-semibold font-body ${isSelected ? "text-teal" : "text-text"}`}>
                {opt.label}
              </p>
              <p className="text-xs text-text-ter font-body mt-1">
                {opt.desc}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
