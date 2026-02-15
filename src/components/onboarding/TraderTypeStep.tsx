"use client";

import { TrendingUp, Search, Layers, BarChart3, Clock, Compass, Check } from "lucide-react";

const traderTypes = [
  { id: "momentum", label: "Momentum", desc: "Ride trends. Buy strength, sell weakness.", icon: TrendingUp },
  { id: "value", label: "Value", desc: "Find what others miss. Buy cheap, hold long.", icon: Search },
  { id: "options", label: "Options", desc: "Sell premium. Profit from time and volatility.", icon: Layers },
  { id: "quant", label: "Quant", desc: "Data-driven. Patterns, signals, probabilities.", icon: BarChart3 },
  { id: "swing", label: "Swing", desc: "Capture moves over days to weeks. Patient entries.", icon: Clock },
  { id: "exploring", label: "Exploring", desc: "Still figuring it out. Open to everything.", icon: Compass },
];

interface TraderTypeStepProps {
  value: string;
  onChange: (value: string) => void;
}

export default function TraderTypeStep({ value, onChange }: TraderTypeStepProps) {
  return (
    <div className="max-w-2xl mx-auto px-6">
      <h2 className="font-display italic text-[32px] text-text text-center">
        What kind of trader are you?
      </h2>
      <p className="text-sm text-text-sec font-body text-center mt-2 mb-8">
        Pick the style that feels most natural. There are no wrong answers.
      </p>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {traderTypes.map((type) => {
          const Icon = type.icon;
          const isSelected = value === type.id;
          return (
            <button
              key={type.id}
              onClick={() => onChange(type.id)}
              className={`relative p-5 rounded-xl border text-left transition-all duration-200
                ${isSelected
                  ? "border-teal bg-teal-muted"
                  : "border-border bg-surface hover:border-border-accent"
                }`}
            >
              {isSelected && (
                <div className="absolute top-3 right-3">
                  <Check className="w-4 h-4 text-teal" />
                </div>
              )}
              <Icon
                className={`w-6 h-6 mb-3 ${isSelected ? "text-teal" : "text-text-sec"}`}
                strokeWidth={1.5}
              />
              <p className={`text-sm font-semibold font-body ${isSelected ? "text-teal" : "text-text"}`}>
                {type.label}
              </p>
              <p className="text-xs text-text-ter font-body mt-1 leading-relaxed">
                {type.desc}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
