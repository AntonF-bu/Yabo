'use client'

import { PortfolioPositionRow } from '@/hooks/usePortfolio'

interface PositionsListProps {
  positions: PortfolioPositionRow[]
  totalValue: number
}

export default function PositionsList({ positions, totalValue }: PositionsListProps) {
  if (positions.length === 0) return null

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-text font-body">
          Positions
        </h3>
        <span className="text-xs text-text-ter font-mono">
          {positions.length} open
        </span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {positions.map((pos) => {
          const shares = Number(pos.shares)
          const avgCost = Number(pos.avg_cost)
          const currentPrice = Number(pos.current_price)
          const marketValue = shares * currentPrice
          const pnl = (currentPrice - avgCost) * shares
          const pnlPct = avgCost > 0 ? ((currentPrice - avgCost) / avgCost) * 100 : 0
          const portfolioPct = totalValue > 0 ? (marketValue / totalValue) * 100 : 0

          return (
            <div
              key={pos.ticker}
              className="bg-surface rounded-lg p-3 border border-border hover:border-border-hover transition-colors"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-sm font-bold text-text">{pos.ticker}</span>
                <span className="text-[10px] font-mono text-text-ter">
                  {portfolioPct.toFixed(1)}%
                </span>
              </div>
              <p className="font-mono text-xs text-text-sec">
                {shares.toFixed(shares % 1 !== 0 ? 2 : 0)} @ ${avgCost.toFixed(2)}
              </p>
              <p className={`font-mono text-xs font-semibold mt-1 ${pnl >= 0 ? 'text-green' : 'text-red'}`}>
                {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)} ({pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(1)}%)
              </p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
