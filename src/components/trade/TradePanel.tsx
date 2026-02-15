'use client'

import { useState, useEffect, useCallback } from 'react'
import { X } from 'lucide-react'
import { getQuote, getStockProfile, mapToSector, Quote, StockProfile } from '@/lib/market-data'
import { RuleCheck } from '@/lib/rules-engine'
import { PortfolioPositionRow } from '@/hooks/usePortfolio'
import TickerSearch from './TickerSearch'
import OrderEntry from './OrderEntry'
import OrderConfirmation from './OrderConfirmation'

interface TradePanelProps {
  open: boolean
  onClose: () => void
  positions: PortfolioPositionRow[]
  cash: number
  totalValue: number
  onTradeComplete: () => void
  initialTicker?: string
}

type Step = 'search' | 'order' | 'confirm'

interface OrderData {
  side: 'buy' | 'sell'
  quantity: number
  price: number
  sector: string
  checks: RuleCheck[]
}

export default function TradePanel({
  open,
  onClose,
  positions,
  cash,
  totalValue,
  onTradeComplete,
  initialTicker,
}: TradePanelProps) {
  const [step, setStep] = useState<Step>('search')
  const [selectedTicker, setSelectedTicker] = useState('')
  const [quote, setQuote] = useState<Quote | null>(null)
  const [stockProfile, setStockProfile] = useState<StockProfile | null>(null)
  const [orderData, setOrderData] = useState<OrderData | null>(null)
  const [loading, setLoading] = useState(false)

  // Reset state on open/close
  useEffect(() => {
    if (!open) {
      setTimeout(() => {
        setStep('search')
        setSelectedTicker('')
        setQuote(null)
        setStockProfile(null)
        setOrderData(null)
      }, 300)
    }
  }, [open])

  // Auto-select ticker when panel opens with initialTicker
  useEffect(() => {
    if (open && initialTicker) {
      handleSelectTicker(initialTicker)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initialTicker])

  const handleSelectTicker = useCallback(async (symbol: string) => {
    setLoading(true)
    setSelectedTicker(symbol)
    try {
      const [q, p] = await Promise.all([
        getQuote(symbol),
        getStockProfile(symbol).catch(() => null),
      ])
      setQuote(q)
      if (p) {
        setStockProfile({ ...p, finnhubIndustry: mapToSector(p.finnhubIndustry || '') })
      } else {
        setStockProfile(null)
      }
      setStep('order')
    } catch {
      // Could not fetch -- stay on search
    }
    setLoading(false)
  }, [])

  const handleReview = (data: OrderData) => {
    setOrderData(data)
    setStep('confirm')
  }

  const handleComplete = () => {
    onTradeComplete()
    onClose()
  }

  return (
    <>
      {/* Overlay */}
      {open && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-[4px] z-50 transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Panel */}
      <div
        className={`fixed top-0 right-0 bottom-0 z-50 w-full sm:w-[420px] bg-surface border-l border-border transform transition-transform duration-300 ease-out ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex flex-col h-full">
          {/* Panel Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-border">
            <h2 className="font-display italic text-lg text-text">
              {step === 'search' && 'New Trade'}
              {step === 'order' && selectedTicker}
              {step === 'confirm' && 'Confirm Order'}
            </h2>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-text-ter hover:text-text hover:bg-bg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Panel Content */}
          <div className="flex-1 overflow-y-auto p-5">
            {loading ? (
              <div className="flex flex-col items-center justify-center py-20">
                <div className="w-3 h-3 rounded-full bg-teal animate-pulse" />
                <p className="text-xs text-text-ter mt-3 font-body">Loading market data...</p>
              </div>
            ) : step === 'search' ? (
              <TickerSearch
                positions={positions}
                onSelect={handleSelectTicker}
              />
            ) : step === 'order' && quote ? (
              <OrderEntry
                ticker={selectedTicker}
                quote={quote}
                profile={stockProfile}
                positions={positions}
                cash={cash}
                totalValue={totalValue}
                onReview={handleReview}
                onBack={() => setStep('search')}
              />
            ) : step === 'confirm' && orderData ? (
              <OrderConfirmation
                ticker={selectedTicker}
                companyName={stockProfile?.name || ''}
                side={orderData.side}
                quantity={orderData.quantity}
                price={orderData.price}
                sector={orderData.sector}
                checks={orderData.checks}
                totalValue={totalValue}
                onComplete={handleComplete}
                onBack={() => setStep('order')}
              />
            ) : null}
          </div>
        </div>
      </div>
    </>
  )
}
