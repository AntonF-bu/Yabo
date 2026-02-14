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
  const tierColor = tierColors[trader.tier] || "#9B9B9B";

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
        transition-all duration-200 hover:shadow-md hover:-translate-y-0.5
        hover:border-text-tertiary/30 ${animationClass}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div
            className="w-9 h-9 rounded-full flex items-center justify-center shrink-0"
            style={{ backgroundColor: `${tierColor}18`, color: tierColor }}
          >
            <span className="text-xs font-bold">{trader.initials}</span>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-text-primary">
                {trader.name}
              </span>
              <TierBadge tier={trader.tier} />
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs text-text-tertiary">{trader.dna}</span>
              <span className="text-[10px] text-text-tertiary">
                &middot; {thesis.timeAgo}
              </span>
            </div>
          </div>
        </div>
        <SignalBadge score={thesis.signal} size="md" />
      </div>

      <div className="flex items-center gap-2.5 mt-4">
        <span className="font-mono text-lg font-bold text-text-primary">
          {thesis.ticker}
        </span>
        <Badge
          label={thesis.direction.toUpperCase()}
          variant="direction"
          direction={thesis.direction}
        />
      </div>

      <p className="mt-3 text-sm text-text-secondary leading-relaxed">
        {thesis.text}
      </p>

      <div className="flex items-center justify-between mt-4 gap-4">
        <div className="flex items-center gap-5">
          <div>
            <span className="text-[10px] text-text-tertiary uppercase tracking-wider">Entry</span>
            <p className="font-mono text-sm font-medium text-text-primary">
              ${thesis.price.toFixed(2)}
            </p>
          </div>
          <div>
            <span className="text-[10px] text-text-tertiary uppercase tracking-wider">Target</span>
            <p className="font-mono text-sm font-medium text-gain">
              ${thesis.target.toFixed(2)}
            </p>
          </div>
          <div>
            <span className="text-[10px] text-text-tertiary uppercase tracking-wider">Stop</span>
            <p className="font-mono text-sm font-medium text-loss">
              ${thesis.stop.toFixed(2)}
            </p>
          </div>
        </div>
        <Sparkline data={thesis.chartData} />
      </div>

      <div className="mt-4">
        <ConvictionBar value={thesis.conviction} />
      </div>

      <div className="flex items-center justify-between mt-4 pt-3 border-t border-border-light">
        <div className="flex items-center gap-4">
          <button className="flex items-center gap-1.5 text-xs text-text-tertiary hover:text-gain transition-colors">
            <ArrowUp className="w-3.5 h-3.5" />
            <span className="font-mono">{thesis.repCount}</span>
          </button>
          <button className="flex items-center gap-1.5 text-xs text-text-tertiary hover:text-text-primary transition-colors">
            <MessageSquare className="w-3.5 h-3.5" />
            <span className="font-mono">{thesis.replies}</span>
          </button>
          <div className="flex items-center gap-1.5 text-xs">
            <button className="px-2 py-1 rounded bg-gain-light text-gain font-mono font-semibold hover:bg-gain/15 transition-colors">
              Yes {thesis.yesVotes}
            </button>
            <button className="px-2 py-1 rounded bg-loss-light text-loss font-mono font-semibold hover:bg-loss/15 transition-colors">
              No {thesis.noVotes}
            </button>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 text-xs text-text-tertiary">
            <Clock className="w-3 h-3" />
            <span>{thesis.expiresIn}</span>
          </div>
          <div className="flex items-center gap-1 text-xs">
            <Target className="w-3 h-3 text-text-tertiary" />
            <span className="font-mono font-medium text-text-secondary">
              {Math.round(thesis.probability * 100)}%
            </span>
          </div>
        </div>
      </div>
    </article>
  );
}
