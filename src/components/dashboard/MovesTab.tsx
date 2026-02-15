"use client";

import { collectiveMoves } from "@/lib/mock-data";
import Badge from "@/components/ui/Badge";
import SignalBadge from "@/components/ui/SignalBadge";
import ConvictionBar from "@/components/ui/ConvictionBar";
import Card from "@/components/ui/Card";
import MockDataBadge from "@/components/ui/MockDataBadge";
import { Users, TrendingUp } from "lucide-react";

export default function MovesTab() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="font-display text-[28px] text-text">
              The Move
            </h2>
            <MockDataBadge />
          </div>
          <p className="text-sm text-text-ter mt-0.5 font-body">
            Collective conviction
          </p>
        </div>
        <span className="text-sm text-text-ter font-mono">
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
            <Card key={move.id} hover={false} className={`p-6 ${animClass}`}>
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-2xl font-bold text-text">
                    {move.ticker}
                  </span>
                  <Badge
                    label={move.direction.toUpperCase()}
                    variant="direction"
                    direction={move.direction}
                  />
                  <SignalBadge score={move.signal} size="md" />
                </div>
                <div className="flex items-center gap-2 text-text-sec">
                  <Users className="w-4 h-4" />
                  <span className="font-mono text-sm font-medium">
                    {move.participants.toLocaleString()} traders
                  </span>
                </div>
              </div>

              <p className="text-sm text-text-sec leading-relaxed font-body">
                {move.catalyst}
              </p>

              <div className="flex items-center gap-6 mt-4">
                <div>
                  <span className="text-[10px] text-text-ter uppercase tracking-wider font-mono">Current</span>
                  <p className="font-mono text-sm font-medium text-text">
                    ${move.currentPrice.toFixed(2)}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] text-text-ter uppercase tracking-wider font-mono">Target</span>
                  <p className="font-mono text-sm font-medium text-green">
                    ${move.target.toFixed(2)}
                  </p>
                </div>
                <div className="flex items-center gap-1">
                  <TrendingUp className="w-3.5 h-3.5 text-green" />
                  <span className="font-mono text-sm font-medium text-green">
                    +{upside}%
                  </span>
                </div>
              </div>

              <div className="mt-4">
                <ConvictionBar value={move.conviction} height="md" />
              </div>

              <div className="mt-5 pt-4 border-t border-border flex items-center justify-between">
                <div className="flex -space-x-2">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <div
                      key={n}
                      className="w-7 h-7 rounded-full border-2 border-surface bg-bg flex items-center justify-center"
                    >
                      <span className="text-[9px] font-bold text-text-ter">
                        {String.fromCharCode(64 + n * 3)}{String.fromCharCode(64 + n * 2)}
                      </span>
                    </div>
                  ))}
                  <div className="w-7 h-7 rounded-full border-2 border-surface bg-surface-hover flex items-center justify-center">
                    <span className="text-[9px] font-bold text-text-ter">
                      +{move.participants - 5}
                    </span>
                  </div>
                </div>
                <span className="px-5 py-2.5 rounded-lg bg-text text-bg text-sm font-semibold font-body" style={{ opacity: 0.35, cursor: "not-allowed" }}>
                  Join Move
                </span>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
