'use client'

interface PortfolioImpactProps {
  side: 'buy' | 'sell'
  orderValue: number
  commission: number
  cashBefore: number
  totalValueBefore: number
}

export default function PortfolioImpact({
  side,
  orderValue,
  commission,
  cashBefore,
  totalValueBefore,
}: PortfolioImpactProps) {
  const cashAfter = side === 'buy'
    ? cashBefore - orderValue - commission
    : cashBefore + orderValue - commission

  const cashPct = totalValueBefore > 0
    ? (cashAfter / totalValueBefore) * 100
    : 0

  return (
    <div className="p-3 rounded-lg bg-bg border border-border">
      <p className="text-[10px] font-mono uppercase tracking-[2px] text-text-ter mb-2">
        Portfolio Impact
      </p>
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-xs text-text-sec font-body">Order Value</span>
          <span className="text-xs font-mono text-text">
            ${orderValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-text-sec font-body">Commission</span>
          <span className="text-xs font-mono text-text-sec">
            ${commission.toFixed(2)}
          </span>
        </div>
        <div className="border-t border-border my-1" />
        <div className="flex items-center justify-between">
          <span className="text-xs text-text-sec font-body">Cash After</span>
          <span className={`text-xs font-mono font-semibold ${cashAfter >= 0 ? 'text-text' : 'text-red'}`}>
            ${cashAfter.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-text-sec font-body">Cash %</span>
          <span className="text-xs font-mono text-text-sec">
            {cashPct.toFixed(1)}%
          </span>
        </div>
      </div>
    </div>
  )
}
