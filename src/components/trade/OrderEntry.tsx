'use client'

import { useState, useEffect, useMemo } from 'react'
import { Quote, StockProfile } from '@/lib/market-data'
import { validateTrade, calculateCommission, Portfolio, PortfolioPosition, RuleCheck } from '@/lib/rules-engine'
import { PortfolioPositionRow } from '@/hooks/usePortfolio'
import PortfolioImpact from './PortfolioImpact'
import RuleCheckList from './RuleCheckList'
import LiveDot from '@/components/ui/LiveDot'

interface OrderEntryProps {
  ticker: string
  quote: Quote
  profile: StockProfile | null
  positions: PortfolioPositionRow[]
  cash: number
  totalValue: number
  onReview: (order: { side: 'buy' | 'sell'; quantity: number; price: number; sector: string; checks: RuleCheck[] }) => void
  onBack: () => void
  initialSide?: 'buy' | 'sell'
}

export default function OrderEntry({
  ticker,
  quote,
  profile,
  positions,
  cash,
  totalValue,
  onReview,
  onBack,
  initialSide,
}: OrderEntryProps) {
  const [side, setSide] = useState<'buy' | 'sell'>(initialSide || 'buy')
  const [quantity, setQuantity] = useState('')
  const price = quote.c
  const change = quote.d
  const changePct = quote.dp

  const existingPosition = positions.find(p => p.ticker === ticker)
  const sector = profile?.finnhubIndustry || 'Other'

  // Auto-set to sell if user has position
  useEffect(() => {
    if (existingPosition && !existingPosition.shares) {
      setSide('buy')
    }
  }, [existingPosition])

  const qty = parseFloat(quantity) || 0
  const orderValue = qty * price
  const commission = qty > 0 ? calculateCommission(qty) : 0

  const portfolioForRules: Portfolio = useMemo(() => ({
    cashBalance: cash,
    totalValue: totalValue,
    startingCapital: 100000,
    positions: positions.map((p): PortfolioPosition => ({
      ticker: p.ticker,
      shares: Number(p.shares),
      avgCost: Number(p.avg_cost),
      currentPrice: Number(p.current_price),
      sector: p.sector,
      marketValue: Number(p.shares) * Number(p.current_price),
    })),
    peakValue: Math.max(totalValue, 100000),
  }), [cash, totalValue, positions])

  const checks = useMemo(() => {
    if (qty <= 0) return []
    return validateTrade({
      ticker,
      side,
      quantity: qty,
      price,
      sector,
    }, portfolioForRules)
  }, [ticker, side, qty, price, sector, portfolioForRules])

  const hasErrors = checks.some(c => !c.passed)
  const canReview = qty > 0 && !hasErrors

  const handleQuickFill = (pct: number) => {
    if (side === 'buy') {
      const maxShares = Math.floor((cash * pct) / price * 100) / 100
      setQuantity(maxShares > 0 ? String(maxShares) : '0')
    } else if (existingPosition) {
      const shares = Number(existingPosition.shares)
      const amount = Math.floor(shares * pct * 100) / 100
      setQuantity(amount > 0 ? String(amount) : '0')
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <button
        onClick={onBack}
        className="text-xs text-text-ter hover:text-text transition-colors font-body mb-4 self-start"
      >
        &larr; Back to search
      </button>

      <div className="mb-5">
        <div className="flex items-center gap-2">
          <h3 className="font-mono text-lg font-bold text-text">{ticker}</h3>
          {profile?.name && (
            <span className="text-xs text-text-sec font-body truncate">{profile.name}</span>
          )}
        </div>
        <div className="flex items-center gap-3 mt-1">
          <span className="font-mono text-[32px] font-bold text-text leading-none">
            ${price.toFixed(2)}
          </span>
          <div className="flex items-center gap-1.5">
            <span className={`font-mono text-sm font-semibold ${change >= 0 ? 'text-green' : 'text-red'}`}>
              {change >= 0 ? '+' : ''}{change.toFixed(2)} ({changePct >= 0 ? '+' : ''}{changePct.toFixed(2)}%)
            </span>
            <LiveDot />
          </div>
        </div>
      </div>

      {/* Buy / Sell Toggle */}
      <div className="flex gap-1 p-1 bg-bg rounded-lg mb-5">
        <button
          onClick={() => setSide('buy')}
          className={`flex-1 py-2 rounded-md text-sm font-semibold font-body transition-colors ${
            side === 'buy'
              ? 'bg-green/10 text-green'
              : 'text-text-ter hover:text-text-sec'
          }`}
        >
          BUY
        </button>
        <button
          onClick={() => setSide('sell')}
          className={`flex-1 py-2 rounded-md text-sm font-semibold font-body transition-colors ${
            side === 'sell'
              ? 'bg-red/10 text-red'
              : 'text-text-ter hover:text-text-sec'
          }`}
        >
          SELL
        </button>
      </div>

      {/* Quantity Input */}
      <div className="mb-3">
        <label className="text-[10px] font-mono uppercase tracking-[2px] text-text-ter block mb-2">
          Shares
        </label>
        <input
          type="number"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          placeholder="0"
          step="0.01"
          min="0"
          className="w-full px-4 py-3 bg-surface border border-border rounded-lg text-center font-mono text-2xl font-bold text-text placeholder:text-text-ter/30 focus:outline-none focus:border-teal transition-colors"
        />
      </div>

      {/* Quick-fill buttons */}
      <div className="flex gap-2 mb-5">
        {[
          { label: '25%', pct: 0.25 },
          { label: '50%', pct: 0.50 },
          { label: '75%', pct: 0.75 },
          { label: 'MAX', pct: 1.0 },
        ].map((btn) => (
          <button
            key={btn.label}
            onClick={() => handleQuickFill(btn.pct)}
            className="flex-1 py-1.5 rounded-md bg-bg border border-border text-[11px] font-mono font-medium text-text-sec hover:border-text hover:text-text transition-colors"
          >
            {btn.label}
          </button>
        ))}
      </div>

      {/* Estimated cost */}
      {qty > 0 && (
        <div className="flex items-center justify-between px-1 mb-4">
          <span className="text-xs text-text-sec font-body">
            {side === 'buy' ? 'Estimated Cost' : 'Estimated Proceeds'}
          </span>
          <span className="font-mono text-sm font-semibold text-text">
            ${orderValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        </div>
      )}

      {/* Scrollable section */}
      <div className="flex-1 overflow-y-auto space-y-4 min-h-0">
        {qty > 0 && (
          <>
            <PortfolioImpact
              side={side}
              orderValue={orderValue}
              commission={commission}
              cashBefore={cash}
              totalValueBefore={totalValue}
            />
            <RuleCheckList checks={checks} />
          </>
        )}
      </div>

      {/* Review button */}
      <div className="pt-4 mt-auto">
        <button
          onClick={() => onReview({ side, quantity: qty, price, sector, checks })}
          disabled={!canReview}
          className={`w-full py-3.5 rounded-xl text-sm font-semibold font-body transition-all ${
            canReview
              ? 'bg-text text-bg hover:-translate-y-0.5'
              : 'bg-surface text-text-ter cursor-not-allowed'
          }`}
        >
          Review Order
        </button>
      </div>
    </div>
  )
}
