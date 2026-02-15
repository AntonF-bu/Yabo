"use client";

import { Check } from "lucide-react";

const options = [
  { id: "conservative", label: "Conservative", desc: "Sleep well at night. Max 10% drawdown.", color: "#4A8C6A" },
  { id: "moderate", label: "Moderate", desc: "Comfortable with volatility. Max 20% drawdown.", color: "#4A8C6A" },
  { id: "aggressive", label: "Aggressive", desc: "Drawdowns are opportunities. Max 30% drawdown.", color: "#9A7B5B" },
  { id: "very-aggressive", label: "Very Aggressive", desc: "I live for volatility. Bring it on.", color: "#C45A4A" },
];

interface RiskStepProps {
  value: string;
  onChange: (value: string) => void;
}

export default function RiskStep({ value, onChange }: RiskStepProps) {
  return (
    <div className="max-w-xl mx-auto px-6">
      <h2 className="font-display text-[32px] text-text text-center">
        How much heat can you take?
      </h2>
      <p className="text-sm text-text-sec font-body text-center mt-2 mb-8">
        This calibrates your simulation guardrails.
      </p>

      <div className="space-y-3">
        {options.map((opt) => {
          const isSelected = value === opt.id;
          return (
            <button
              key={opt.id}
              onClick={() => onChange(opt.id)}
              className={`relative w-full p-4 rounded-xl border text-left transition-all duration-200
                border-l-4
                ${isSelected
                  ? "border-teal bg-teal-muted"
                  : "border-border bg-surface hover:border-border-accent"
                }`}
              style={{ borderLeftColor: opt.color }}
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
