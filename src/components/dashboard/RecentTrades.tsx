'use client'

import { TradeRow } from '@/hooks/usePortfolio'

interface RecentTradesProps {
  trades: TradeRow[]
}

export default function RecentTrades({ trades }: RecentTradesProps) {
  const recent = trades.slice(0, 5)

  if (recent.length === 0) return null

  return (
    <div>
      <h3 className="text-base font-semibold text-text font-body mb-4">
        Recent Activity
      </h3>
      <div className="space-y-1">
        {recent.map((trade) => {
          const date = new Date(trade.created_at)
          const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          const dateStr = date.toLocaleDateString([], { month: 'short', day: 'numeric' })
          const isBuy = trade.side === 'buy'

          return (
            <div
              key={trade.id}
              className="flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-surface/50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-mono text-text-ter whitespace-nowrap">
                  {dateStr} {timeStr}
                </span>
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                    isBuy
                      ? 'bg-teal/10 text-teal'
                      : 'bg-red/10 text-red'
                  }`}
                >
                  {trade.side}
                </span>
                <span className="font-mono text-sm font-bold text-text">
                  {trade.ticker}
                </span>
                <span className="text-xs text-text-sec font-mono">
                  x{trade.quantity}
                </span>
              </div>
              <div className="text-right">
                <span className="font-mono text-xs text-text">
                  ${Number(trade.total_value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
