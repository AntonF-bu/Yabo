"use client";

import { Thesis } from "@/types";
import { tierColors } from "@/lib/constants";
import Badge from "@/components/ui/Badge";
import SignalBadge from "@/components/ui/SignalBadge";
import ConvictionBar from "@/components/ui/ConvictionBar";
import Sparkline from "@/components/ui/Sparkline";
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
        transition-all duration-200 hover:shadow-sm hover:-translate-y-0.5
        hover:border-text-tertiary/30 ${animationClass}`}
    >
      {/* Header */}
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
              <Badge label={trader.tier} variant="tier" tier={trader.tier} />
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs text-text-tertiary">{trader.dna}</span>
              <span className="text-xs text-text-tertiary">
                {thesis.timeAgo}
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <SignalBadge score={thesis.signal} />
          <SignalBadge score={thesis.tqs} label="TQS" />
        </div>
      </div>

      {/* Ticker + Direction */}
      <div className="flex items-center gap-2 mt-4">
        <span className="font-mono text-lg font-bold text-text-primary">
          {thesis.ticker}
        </span>
        <Badge
          label={thesis.direction.toUpperCase()}
          variant="direction"
          direction={thesis.direction}
        />
      </div>

      {/* Thesis Text */}
      <p className="mt-3 text-sm text-text-secondary leading-relaxed">
        {thesis.text}
      </p>

      {/* Price Data + Sparkline */}
      <div className="flex items-center justify-between mt-4 gap-4">
        <div className="flex items-center gap-4">
          <div className="flex flex-col">
            <span className="text-xs text-text-tertiary">Entry</span>
            <span className="font-mono text-sm font-medium text-text-primary">
              ${thesis.price.toFixed(2)}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-xs text-text-tertiary">Target</span>
            <span className="font-mono text-sm font-medium text-gain">
              ${thesis.target.toFixed(2)}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-xs text-text-tertiary">Stop</span>
            <span className="font-mono text-sm font-medium text-loss">
              ${thesis.stop.toFixed(2)}
            </span>
          </div>
        </div>
        <Sparkline data={thesis.chartData} />
      </div>

      {/* Conviction Bar */}
      <div className="mt-4">
        <ConvictionBar value={thesis.conviction} />
      </div>

      {/* Footer */}
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

          <div className="flex items-center gap-2 text-xs">
            <span className="font-mono text-gain">
              Yes {thesis.yesVotes}
            </span>
            <span className="text-text-tertiary">/</span>
            <span className="font-mono text-loss">
              No {thesis.noVotes}
            </span>
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
