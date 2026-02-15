"use client";

import { useState, useEffect } from "react";
import { OnboardingResults, computeArchetype, computePreliminaryTraits, getInsightText } from "@/lib/db";
import LiveDot from "@/components/ui/LiveDot";

interface ProfileRevealProps {
  results: OnboardingResults;
  onComplete: () => void;
  saving: boolean;
}

// Mini radar chart as SVG polygon
function MiniRadar({ traits }: { traits: Record<string, number> }) {
  const keys = [
    "entryTiming", "holdDiscipline", "positionSizing", "convictionAccuracy",
    "riskManagement", "sectorFocus", "drawdownResilience", "thesisQuality",
  ];
  const labels = [
    "Entry", "Hold", "Sizing", "Conviction",
    "Risk", "Focus", "Resilience", "Thesis",
  ];
  const cx = 75;
  const cy = 75;
  const maxR = 60;
  const n = keys.length;

  // Grid rings
  const rings = [0.25, 0.5, 0.75, 1.0];

  // Compute polygon points
  const points = keys.map((key, i) => {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    const r = (traits[key] / 100) * maxR;
    return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`;
  });

  return (
    <svg width="150" height="150" viewBox="0 0 150 150" className="overflow-visible">
      {/* Grid rings */}
      {rings.map((ring) => (
        <polygon
          key={ring}
          points={Array.from({ length: n }, (_, i) => {
            const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
            const r = ring * maxR;
            return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`;
          }).join(" ")}
          fill="none"
          stroke="rgba(232,228,220,0.06)"
          strokeWidth={1}
        />
      ))}
      {/* Axis lines */}
      {keys.map((_, i) => {
        const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
        return (
          <line
            key={i}
            x1={cx}
            y1={cy}
            x2={cx + maxR * Math.cos(angle)}
            y2={cy + maxR * Math.sin(angle)}
            stroke="rgba(232,228,220,0.06)"
            strokeWidth={1}
          />
        );
      })}
      {/* Data polygon */}
      <polygon
        points={points.join(" ")}
        fill="rgba(0,191,166,0.2)"
        stroke="#00BFA6"
        strokeWidth={2}
        strokeLinejoin="round"
      />
      {/* Labels */}
      {labels.map((label, i) => {
        const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
        const lr = maxR + 14;
        const x = cx + lr * Math.cos(angle);
        const y = cy + lr * Math.sin(angle);
        return (
          <text
            key={i}
            x={x}
            y={y}
            textAnchor="middle"
            dominantBaseline="central"
            fill="rgba(232,228,220,0.25)"
            fontSize="7"
            fontFamily="'Fira Code', monospace"
          >
            {label}
          </text>
        );
      })}
    </svg>
  );
}

// Animated counter
function AnimatedNumber({ target, duration = 1000 }: { target: number; duration?: number }) {
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    const start = Date.now();
    const tick = () => {
      const elapsed = Date.now() - start;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setCurrent(Math.round(target * eased));
      if (progress < 1) {
        requestAnimationFrame(tick);
      }
    };
    requestAnimationFrame(tick);
  }, [target, duration]);

  return <>{current}</>;
}

export default function ProfileReveal({ results, onComplete, saving }: ProfileRevealProps) {
  const [phase, setPhase] = useState<"analyzing" | "reveal">("analyzing");

  const archetype = computeArchetype(results);
  const traits = computePreliminaryTraits(results);
  const insight = getInsightText(results.traderType, results.riskTolerance);

  // Sort traits to find top 2
  const traitEntries = [
    { name: "Entry Timing", score: traits.entryTiming },
    { name: "Hold Discipline", score: traits.holdDiscipline },
    { name: "Position Sizing", score: traits.positionSizing },
    { name: "Conviction", score: traits.convictionAccuracy },
    { name: "Risk Mgmt", score: traits.riskManagement },
    { name: "Sector Focus", score: traits.sectorFocus },
    { name: "Resilience", score: traits.drawdownResilience },
    { name: "Thesis Quality", score: traits.thesisQuality },
  ];
  const sorted = [...traitEntries].sort((a, b) => b.score - a.score);
  const top2 = sorted.slice(0, 2);

  const riskLabel: Record<string, string> = {
    "conservative": "Conservative",
    "moderate": "Moderate",
    "aggressive": "Aggressive",
    "very-aggressive": "Very Aggressive",
  };
  const expLabel: Record<string, string> = {
    "beginner": "Beginner",
    "1-3years": "1-3 Years",
    "3-7years": "3-7 Years",
    "7plus": "7+ Years",
  };

  useEffect(() => {
    const timer = setTimeout(() => setPhase("reveal"), 1500);
    return () => clearTimeout(timer);
  }, []);

  if (phase === "analyzing") {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center p-6">
        <div className="text-center animate-fade-in">
          <div className="w-16 h-16 mx-auto mb-6 rounded-full border-2 border-teal/30 flex items-center justify-center">
            <div className="w-3 h-3 rounded-full bg-teal animate-pulse-dot" />
          </div>
          <p className="font-mono text-sm text-teal tracking-wider">
            Analyzing your Trading DNA...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-6">
      <div className="max-w-lg w-full">
        {/* DNA Card */}
        <div
          className="bg-surface rounded-2xl border border-border p-8 animate-fade-up"
          style={{ boxShadow: "0 24px 80px rgba(0,0,0,0.3), 0 0 0 1px rgba(0,191,166,0.05)" }}
        >
          {/* Top: archetype + tier */}
          <div className="text-center mb-6">
            <div className="flex items-center justify-center gap-2 mb-3">
              <LiveDot />
              <span className="text-[9px] font-mono font-bold tracking-[3px] text-teal uppercase">
                YOUR TRADING DNA
              </span>
            </div>
            <h2 className="font-display italic text-[36px] text-text leading-tight">
              {archetype}
            </h2>
            <span className="inline-block mt-2 px-3 py-1 rounded-full text-[10px] font-mono font-bold tracking-wider text-teal border border-teal/30 uppercase">
              ROOKIE
            </span>
          </div>

          {/* Radar + Starting Capital side by side */}
          <div className="flex items-center justify-between mb-6">
            <MiniRadar traits={traits} />
            <div className="text-right">
              <p className="text-[10px] font-mono text-text-ter uppercase tracking-wider">
                Starting Capital
              </p>
              <p className="font-mono text-[32px] font-bold text-text mt-1">
                $<AnimatedNumber target={100000} />
              </p>
            </div>
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-4 gap-3 mb-6 pt-5 border-t border-border">
            {top2.map((trait) => (
              <div key={trait.name}>
                <p className="text-[9px] font-mono text-text-ter uppercase tracking-wider">
                  {trait.name}
                </p>
                <p className="font-mono text-lg font-bold text-teal mt-0.5">
                  <AnimatedNumber target={trait.score} />
                </p>
              </div>
            ))}
            <div>
              <p className="text-[9px] font-mono text-text-ter uppercase tracking-wider">
                Risk
              </p>
              <p className="font-mono text-xs font-semibold text-text mt-1.5">
                {riskLabel[results.riskTolerance] || results.riskTolerance}
              </p>
            </div>
            <div>
              <p className="text-[9px] font-mono text-text-ter uppercase tracking-wider">
                Experience
              </p>
              <p className="font-mono text-xs font-semibold text-text mt-1.5">
                {expLabel[results.experienceLevel] || results.experienceLevel}
              </p>
            </div>
          </div>

          {/* Insight */}
          <div className="p-4 rounded-xl bg-teal-muted border border-teal/10">
            <p className="text-sm text-teal font-body leading-relaxed italic">
              &ldquo;{insight}&rdquo;
            </p>
          </div>
        </div>

        {/* Below card */}
        <p className="text-center text-sm text-text-ter font-body mt-6 animate-fade-up-delay-1">
          This is your starting point. Every trade you make refines it.
        </p>

        <div className="text-center mt-6 animate-fade-up-delay-2">
          <button
            onClick={onComplete}
            disabled={saving}
            className={`px-10 py-4 rounded-full text-sm font-semibold font-body transition-all
              ${saving
                ? "bg-teal/50 text-bg/50 cursor-wait"
                : "bg-teal text-bg hover:shadow-[0_0_24px_rgba(0,191,166,0.3)]"
              }`}
          >
            {saving ? "Saving..." : "Claim Your Seat"}
          </button>
        </div>
      </div>
    </div>
  );
}
