"use client";

import { ComputedPortfolio } from "@/types";
import { CheckCircle2, TrendingUp, BarChart3, Target, Percent } from "lucide-react";

interface ImportSummaryProps {
  portfolio: ComputedPortfolio;
  onConfirm: () => void;
  onBack: () => void;
}

export default function ImportSummary({ portfolio, onConfirm, onBack }: ImportSummaryProps) {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-gain-light text-gain text-sm">
        <CheckCircle2 className="w-5 h-5 shrink-0" />
        <div>
          <p className="font-semibold">Analysis Complete</p>
          <p className="text-xs opacity-80 mt-0.5">
            {portfolio.totalTrades} trades analyzed across {portfolio.positions.length} positions
          </p>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-surface rounded-xl border border-border p-4">
          <div className="flex items-center gap-1.5 mb-1">
            <TrendingUp className="w-3.5 h-3.5 text-text-tertiary" />
            <span className="text-[10px] text-text-tertiary uppercase tracking-wider font-semibold">
              Total P&L
            </span>
          </div>
          <p
            className={`font-mono text-xl font-bold ${
              portfolio.totalPnl >= 0 ? "text-gain" : "text-loss"
            }`}
          >
            {portfolio.totalPnl >= 0 ? "+" : ""}${Math.round(portfolio.totalPnl).toLocaleString()}
          </p>
          <p className="text-[10px] text-text-tertiary font-mono mt-0.5">
            {portfolio.totalPnlPercent >= 0 ? "+" : ""}
            {portfolio.totalPnlPercent.toFixed(1)}%
          </p>
        </div>

        <div className="bg-surface rounded-xl border border-border p-4">
          <div className="flex items-center gap-1.5 mb-1">
            <Percent className="w-3.5 h-3.5 text-text-tertiary" />
            <span className="text-[10px] text-text-tertiary uppercase tracking-wider font-semibold">
              Win Rate
            </span>
          </div>
          <p className="font-mono text-xl font-bold text-text-primary">
            {Math.round(portfolio.winRate * 100)}%
          </p>
          <p className="text-[10px] text-text-tertiary font-mono mt-0.5">
            {portfolio.wins}W / {portfolio.losses}L
          </p>
        </div>

        <div className="bg-surface rounded-xl border border-border p-4">
          <div className="flex items-center gap-1.5 mb-1">
            <BarChart3 className="w-3.5 h-3.5 text-text-tertiary" />
            <span className="text-[10px] text-text-tertiary uppercase tracking-wider font-semibold">
              Sharpe
            </span>
          </div>
          <p className="font-mono text-xl font-bold text-text-primary">
            {portfolio.sharpe.toFixed(1)}
          </p>
        </div>

        <div className="bg-surface rounded-xl border border-border p-4">
          <div className="flex items-center gap-1.5 mb-1">
            <Target className="w-3.5 h-3.5 text-text-tertiary" />
            <span className="text-[10px] text-text-tertiary uppercase tracking-wider font-semibold">
              Avg Hold
            </span>
          </div>
          <p className="font-mono text-xl font-bold text-text-primary">
            {portfolio.avgHoldDays}d
          </p>
        </div>
      </div>

      {/* Behavioral Traits Preview */}
      <div>
        <p className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-3">
          Computed Behavioral Traits
        </p>
        <div className="space-y-2">
          {portfolio.traits.map((trait) => (
            <div
              key={trait.name}
              className="flex items-center gap-3 px-3 py-2 rounded-lg bg-surface-hover"
            >
              <span className="text-xs text-text-secondary w-36">{trait.name}</span>
              <div className="flex-1 h-2 rounded-full bg-border overflow-hidden">
                <div
                  className="h-full rounded-full bg-accent transition-all duration-500"
                  style={{ width: `${trait.score}%` }}
                />
              </div>
              <span className="font-mono text-xs font-semibold text-text-primary w-8 text-right">
                {trait.score}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Top Positions */}
      {portfolio.positions.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-3">
            Top Positions
          </p>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-surface-hover border-b border-border-light">
                  <th className="px-3 py-2 text-left text-text-tertiary font-semibold">Ticker</th>
                  <th className="px-3 py-2 text-left text-text-tertiary font-semibold">Sector</th>
                  <th className="px-3 py-2 text-right text-text-tertiary font-semibold">Trades</th>
                  <th className="px-3 py-2 text-right text-text-tertiary font-semibold">P&L</th>
                  <th className="px-3 py-2 text-right text-text-tertiary font-semibold">Win Rate</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.positions
                  .sort((a, b) => b.trades - a.trades)
                  .slice(0, 8)
                  .map((pos) => (
                    <tr
                      key={pos.ticker}
                      className="border-b border-border-light last:border-b-0"
                    >
                      <td className="px-3 py-2 font-mono font-semibold text-text-primary">
                        {pos.ticker}
                      </td>
                      <td className="px-3 py-2 text-text-tertiary">{pos.sector}</td>
                      <td className="px-3 py-2 font-mono text-right text-text-secondary">
                        {pos.trades}
                      </td>
                      <td
                        className={`px-3 py-2 font-mono text-right font-medium ${
                          pos.pnl >= 0 ? "text-gain" : "text-loss"
                        }`}
                      >
                        {pos.pnl >= 0 ? "+" : ""}${Math.round(pos.pnl).toLocaleString()}
                      </td>
                      <td className="px-3 py-2 font-mono text-right text-text-secondary">
                        {pos.trades >= 2
                          ? `${Math.round((pos.wins / Math.floor(pos.trades / 2)) * 100)}%`
                          : "-"}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-3 pt-2">
        <button
          onClick={onBack}
          className="px-6 py-3 rounded-xl border border-border text-sm font-semibold text-text-secondary hover:bg-surface-hover transition-colors"
        >
          Back
        </button>
        <button
          onClick={onConfirm}
          className="flex-1 py-3 rounded-xl bg-accent text-white text-sm font-semibold hover:bg-accent-dark transition-colors"
        >
          Confirm & Import to Dashboard
        </button>
      </div>
    </div>
  );
}
