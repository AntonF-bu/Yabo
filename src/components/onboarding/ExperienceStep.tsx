"use client";

import { Check } from "lucide-react";

const options = [
  { id: "beginner", label: "Just starting", desc: "Less than 1 year" },
  { id: "1-3years", label: "Getting serious", desc: "1-3 years" },
  { id: "3-7years", label: "Experienced", desc: "3-7 years" },
  { id: "7plus", label: "Veteran", desc: "7+ years" },
];

interface ExperienceStepProps {
  value: string;
  onChange: (value: string) => void;
}

export default function ExperienceStep({ value, onChange }: ExperienceStepProps) {
  return (
    <div className="max-w-xl mx-auto px-6">
      <h2 className="font-display italic text-[32px] text-text text-center">
        How long have you been trading?
      </h2>
      <p className="text-sm text-text-sec font-body text-center mt-2 mb-8">
        This helps calibrate your starting profile.
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
