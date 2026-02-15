"use client";

import { Thesis } from "@/types";
import { tierColors } from "@/lib/constants";
import Badge from "@/components/ui/Badge";
import SignalBadge from "@/components/ui/SignalBadge";
import ConvictionBar from "@/components/ui/ConvictionBar";
import Sparkline from "@/components/ui/Sparkline";
import TierBadge from "@/components/ui/TierBadge";
import { MessageSquare, ArrowUp, Clock, Target } from "lucide-react";

interface ThesisCardProps {
  thesis: Thesis;
  index: number;
}

export default function ThesisCard({ thesis, index }: ThesisCardProps) {
  const { trader } = thesis;
  const tierColor = tierColors[trader.tier] || "rgba(232,228,220,0.45)";

  const animationClass =
    index === 0
      ? "animate-fade-up"
      : index === 1
        ? "animate-fade-up-delay-1"
        : index === 2
          ? "animate-fade-up-delay-2"
          : "animate-fade-up-delay-3";

  return (
    <article
      className={`bg-surface rounded-xl border border-border p-5
        transition-all duration-200 hover:-translate-y-0.5
        hover:border-border-accent hover:shadow-[0_4px_24px_rgba(0,0,0,0.3)] ${animationClass}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div
            className="w-9 h-9 rounded-full flex items-center justify-center shrink-0"
            style={{ backgroundColor: `${tierColor}18`, color: tierColor }}
          >
            <span className="text-xs font-mono font-bold">{trader.initials}</span>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-text font-body">
                {trader.name}
              </span>
              <TierBadge tier={trader.tier} />
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs text-text-ter font-body">{trader.dna}</span>
              <span className="text-[10px] text-text-ter">
                &middot; {thesis.timeAgo}
              </span>
            </div>
          </div>
        </div>
        <SignalBadge score={thesis.signal} size="md" />
      </div>

      <div className="flex items-center gap-2.5 mt-4">
        <span className="font-mono text-lg font-bold text-text">
          {thesis.ticker}
        </span>
        <Badge
          label={thesis.direction.toUpperCase()}
          variant="direction"
          direction={thesis.direction}
        />
      </div>

      <p className="mt-3 text-sm text-text-sec leading-relaxed font-body">
        {thesis.text}
      </p>

      <div className="flex items-center justify-between mt-4 gap-4">
        <div className="flex items-center gap-5">
          <div>
            <span className="text-[10px] text-text-ter uppercase tracking-[2px] font-mono">Entry</span>
            <p className="font-mono text-sm font-medium text-text">
              ${thesis.price.toFixed(2)}
            </p>
          </div>
          <div>
            <span className="text-[10px] text-text-ter uppercase tracking-[2px] font-mono">Target</span>
            <p className="font-mono text-sm font-medium text-green">
              ${thesis.target.toFixed(2)}
            </p>
          </div>
          <div>
            <span className="text-[10px] text-text-ter uppercase tracking-[2px] font-mono">Stop</span>
            <p className="font-mono text-sm font-medium text-red">
              ${thesis.stop.toFixed(2)}
            </p>
          </div>
        </div>
        <Sparkline data={thesis.chartData} />
      </div>

      <div className="mt-4">
        <ConvictionBar value={thesis.conviction} />
      </div>

      <div className="flex items-center justify-between mt-4 pt-3 border-t border-border">
        <div className="flex items-center gap-4" style={{ opacity: 0.35, pointerEvents: "none" }}>
          <span className="flex items-center gap-1.5 text-xs text-text-ter cursor-not-allowed">
            <ArrowUp className="w-3.5 h-3.5" />
            <span className="font-mono">{thesis.repCount}</span>
          </span>
          <span className="flex items-center gap-1.5 text-xs text-text-ter cursor-not-allowed">
            <MessageSquare className="w-3.5 h-3.5" />
            <span className="font-mono">{thesis.replies}</span>
          </span>
          <div className="flex items-center gap-1.5 text-xs">
            <span className="px-2 py-1 rounded bg-green-light text-green font-mono font-semibold cursor-not-allowed">
              Yes {thesis.yesVotes}
            </span>
            <span className="px-2 py-1 rounded bg-red-light text-red font-mono font-semibold cursor-not-allowed">
              No {thesis.noVotes}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 text-xs text-text-ter">
            <Clock className="w-3 h-3" />
            <span className="font-mono">{thesis.expiresIn}</span>
          </div>
          <div className="flex items-center gap-1 text-xs">
            <Target className="w-3 h-3 text-text-ter" />
            <span className="font-mono font-medium text-text-sec">
              {Math.round(thesis.probability * 100)}%
            </span>
          </div>
        </div>
      </div>
    </article>
  );
}
