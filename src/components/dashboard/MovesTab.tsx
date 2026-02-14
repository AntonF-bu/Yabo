"use client";

import { collectiveMoves } from "@/lib/mock-data";
import Badge from "@/components/ui/Badge";
import SignalBadge from "@/components/ui/SignalBadge";
import ConvictionBar from "@/components/ui/ConvictionBar";
import Card from "@/components/ui/Card";
import { Users, Target, TrendingUp } from "lucide-react";

export default function MovesTab() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-serif italic text-2xl text-text-primary">
          The Move
        </h2>
        <span className="text-sm text-text-tertiary">
          {collectiveMoves.length} active moves
        </span>
      </div>

      <div className="space-y-4">
        {collectiveMoves.map((move, i) => {
          const upside = (
            ((move.target - move.currentPrice) / move.currentPrice) *
            100
          ).toFixed(1);
          const animClass =
            i === 0 ? "animate-fade-up" : "animate-fade-up-delay-1";

          return (
            <Card
              key={move.id}
              hover={false}
              className={`p-6 ${animClass}`}
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-2xl font-bold text-text-primary">
                    {move.ticker}
                  </span>
                  <Badge
                    label={move.direction.toUpperCase()}
                    variant="direction"
                    direction={move.direction}
                  />
                  <SignalBadge score={move.signal} />
                </div>
                <div className="flex items-center gap-2 text-text-secondary">
                  <Users className="w-4 h-4" />
                  <span className="font-mono text-sm font-medium">
                    {move.participants.toLocaleString()} traders
                  </span>
                </div>
              </div>

              {/* Catalyst */}
              <p className="text-sm text-text-secondary leading-relaxed">
                {move.catalyst}
              </p>

              {/* Price targets */}
              <div className="flex items-center gap-6 mt-4">
                <div className="flex flex-col">
                  <span className="text-xs text-text-tertiary">Current</span>
                  <span className="font-mono text-sm font-medium text-text-primary">
                    ${move.currentPrice.toFixed(2)}
                  </span>
                </div>
                <div className="flex flex-col">
                  <span className="text-xs text-text-tertiary">Target</span>
                  <span className="font-mono text-sm font-medium text-gain">
                    ${move.target.toFixed(2)}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <TrendingUp className="w-3.5 h-3.5 text-gain" />
                  <span className="font-mono text-sm font-medium text-gain">
                    +{upside}%
                  </span>
                </div>
              </div>

              {/* Conviction */}
              <div className="mt-4">
                <ConvictionBar value={move.conviction} height="md" />
              </div>

              {/* Action */}
              <div className="mt-5 pt-4 border-t border-border-light flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="flex -space-x-2">
                    {[1, 2, 3, 4, 5].map((n) => (
                      <div
                        key={n}
                        className="w-6 h-6 rounded-full border-2 border-surface bg-background flex items-center justify-center"
                      >
                        <span className="text-[8px] font-bold text-text-tertiary">
                          {String.fromCharCode(64 + n * 3)}
                          {String.fromCharCode(64 + n * 2)}
                        </span>
                      </div>
                    ))}
                    <div className="w-6 h-6 rounded-full border-2 border-surface bg-border-light flex items-center justify-center">
                      <span className="text-[8px] font-bold text-text-tertiary">
                        +{move.participants - 5}
                      </span>
                    </div>
                  </div>
                </div>

                <button className="px-5 py-2.5 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-dark transition-colors">
                  Join Move
                </button>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
