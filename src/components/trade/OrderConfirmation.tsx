'use client'

import { useState } from 'react'
import { useUser } from '@clerk/nextjs'
import { executeTrade } from '@/lib/trade-executor'
import { calculateCommission, calculateSlippage, RuleCheck } from '@/lib/rules-engine'
import RuleCheckList from './RuleCheckList'
import { CheckCircle, Loader2 } from 'lucide-react'

interface OrderConfirmationProps {
  ticker: string
  companyName: string
  side: 'buy' | 'sell'
  quantity: number
  price: number
  sector: string
  checks: RuleCheck[]
  totalValue: number
  onComplete: () => void
  onBack: () => void
}

export default function OrderConfirmation({
  ticker,
  companyName,
  side,
  quantity,
  price,
  sector,
  checks,
  totalValue,
  onComplete,
  onBack,
}: OrderConfirmationProps) {
  const { user } = useUser()
  const [status, setStatus] = useState<'review' | 'executing' | 'success' | 'error'>('review')
  const [errorMsg, setErrorMsg] = useState('')
  const [result, setResult] = useState<{ executionPrice: number; commission: number; totalValue: number } | null>(null)

  const estimatedPrice = calculateSlippage(price, side)
  const commission = calculateCommission(quantity)
  const estimatedTotal = quantity * estimatedPrice + (side === 'buy' ? commission : -commission)

  const warnings = checks.filter(c => c.passed && c.severity === 'warning' && c.rule !== 'All Rules')

  const handleConfirm = async () => {
    if (!user) return
    setStatus('executing')

    try {
      const res = await executeTrade(user.id, {
        ticker,
        side,
        quantity,
        price,
        sector,
      })
      setResult(res)
      setStatus('success')

      // Auto-close after 2 seconds
      setTimeout(() => {
        onComplete()
      }, 2000)
    } catch (err) {
      setStatus('error')
      setErrorMsg(err instanceof Error ? err.message : 'Trade execution failed')
    }
  }

  // Success state
  if (status === 'success' && result) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-12">
        <div className="animate-scale-up">
          <CheckCircle className="w-16 h-16 text-teal" />
        </div>
        <h3 className="font-display italic text-xl text-text mt-4">
          Trade Executed
        </h3>
        <p className="text-sm text-text-sec mt-2 font-body">
          {side === 'buy' ? 'Bought' : 'Sold'} {quantity} shares of {ticker}
        </p>
        <p className="font-mono text-lg font-bold text-text mt-1">
          @ ${result.executionPrice.toFixed(2)}
        </p>
        <div className="mt-6 p-3 rounded-lg bg-teal/5 border border-teal/20">
          <p className="text-xs text-text-sec font-body">Updated Portfolio Value</p>
          <p className="font-mono text-xl font-bold text-teal mt-0.5">
            ${totalValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </p>
        </div>
      </div>
    )
  }

  // Executing state
  if (status === 'executing') {
    return (
      <div className="flex flex-col items-center justify-center h-full py-12">
        <Loader2 className="w-10 h-10 text-teal animate-spin" />
        <p className="text-sm text-text-sec mt-4 font-body">Executing trade...</p>
      </div>
    )
  }

  // Error state
  if (status === 'error') {
    return (
      <div className="flex flex-col items-center justify-center h-full py-12">
        <div className="w-16 h-16 rounded-full bg-red/10 flex items-center justify-center">
          <span className="font-mono text-2xl text-red">!</span>
        </div>
        <h3 className="font-display italic text-xl text-text mt-4">
          Trade Failed
        </h3>
        <p className="text-sm text-red mt-2 font-body text-center max-w-[280px]">
          {errorMsg}
        </p>
        <button
          onClick={onBack}
          className="mt-6 px-6 py-2.5 rounded-lg border border-border text-sm text-text-sec font-body hover:border-teal/30 transition-colors"
        >
          Go Back
        </button>
      </div>
    )
  }

  // Review state
  return (
    <div className="flex flex-col h-full">
      <button
        onClick={onBack}
        className="text-xs text-text-ter hover:text-text transition-colors font-body mb-6 self-start"
      >
        &larr; Back to order
      </button>

      <h3 className="font-display italic text-xl text-text mb-6">
        {side === 'buy' ? 'Buy' : 'Sell'} {quantity} shares of {ticker}
      </h3>

      {companyName && (
        <p className="text-xs text-text-sec font-body -mt-4 mb-6">{companyName}</p>
      )}

      {/* Order Summary */}
      <div className="space-y-3 mb-6">
        <div className="flex items-center justify-between">
          <span className="text-sm text-text-sec font-body">Market Price</span>
          <span className="font-mono text-sm text-text">${price.toFixed(2)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-text-sec font-body">Est. Execution Price</span>
          <span className="font-mono text-sm text-text">${estimatedPrice.toFixed(2)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-text-sec font-body">Quantity</span>
          <span className="font-mono text-sm text-text">{quantity}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-text-sec font-body">Commission</span>
          <span className="font-mono text-sm text-text-sec">${commission.toFixed(2)}</span>
        </div>
        <div className="border-t border-border pt-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-text font-body">
              Estimated Total
            </span>
            <span className="font-mono text-lg font-bold text-text">
              ${estimatedTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
        </div>
        <p className="text-[10px] text-text-ter font-body">
          Includes 0.02% slippage estimate. Actual execution price may vary slightly.
        </p>
      </div>

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="mb-6">
          <RuleCheckList checks={warnings} />
        </div>
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Confirm button */}
      <button
        onClick={handleConfirm}
        className={`w-full py-3.5 rounded-xl text-sm font-semibold font-body transition-all ${
          side === 'buy'
            ? 'bg-teal text-bg hover:shadow-[0_0_24px_rgba(0,191,166,0.3)]'
            : 'bg-red text-white hover:shadow-[0_0_24px_rgba(255,107,107,0.3)]'
        }`}
      >
        Confirm {side === 'buy' ? 'Buy' : 'Sell'}
      </button>
    </div>
  )
}
