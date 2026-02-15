'use client'

import { useState, useEffect, useRef } from 'react'
import { Search } from 'lucide-react'
import { searchTickers, SearchResult } from '@/lib/market-data'
import { PortfolioPositionRow } from '@/hooks/usePortfolio'

interface TickerSearchProps {
  positions: PortfolioPositionRow[]
  onSelect: (symbol: string) => void
}

export default function TickerSearch({ positions, onSelect }: TickerSearchProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)

    if (query.length < 1) {
      setResults([])
      return
    }

    debounceRef.current = setTimeout(async () => {
      setSearching(true)
      try {
        const data = await searchTickers(query)
        setResults(data)
      } catch {
        setResults([])
      }
      setSearching(false)
    }, 300)

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [query])

  return (
    <div className="flex flex-col h-full">
      {/* Search Input */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-ter" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search ticker or company..."
          autoFocus
          className="w-full pl-10 pr-4 py-3 bg-surface border border-border rounded-lg text-text font-mono text-sm placeholder:text-text-ter/40 focus:outline-none focus:border-teal transition-colors"
        />
      </div>

      {/* Search Results */}
      {query.length > 0 && (
        <div className="mt-2 max-h-[300px] overflow-y-auto">
          {searching ? (
            <div className="py-8 text-center">
              <div className="w-3 h-3 rounded-full bg-teal animate-pulse mx-auto" />
              <p className="text-xs text-text-ter mt-2 font-body">Searching...</p>
            </div>
          ) : results.length === 0 && query.length > 0 ? (
            <p className="py-6 text-center text-xs text-text-ter font-body">
              No results for &quot;{query}&quot;
            </p>
          ) : (
            <div className="space-y-0.5">
              {results.map((r) => (
                <button
                  key={r.symbol}
                  onClick={() => onSelect(r.symbol)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-surface-hover transition-colors text-left"
                >
                  <span className="font-mono text-sm font-bold text-text">
                    {r.displaySymbol}
                  </span>
                  <span className="text-[13px] text-text-sec font-body truncate">
                    {r.description}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Your Positions */}
      {positions.length > 0 && query.length === 0 && (
        <div className="mt-6">
          <p className="text-[10px] font-mono uppercase tracking-[2px] text-text-ter mb-3">
            Your Positions
          </p>
          <div className="space-y-0.5">
            {positions.map((pos) => (
              <button
                key={pos.ticker}
                onClick={() => onSelect(pos.ticker)}
                className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg hover:bg-surface-hover transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className="font-mono text-sm font-bold text-text">
                    {pos.ticker}
                  </span>
                  <span className="text-xs text-text-sec font-body">
                    {Number(pos.shares).toFixed(Number(pos.shares) % 1 !== 0 ? 2 : 0)} shares
                  </span>
                </div>
                <span className="font-mono text-xs text-text-sec">
                  ${(Number(pos.shares) * Number(pos.current_price)).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {positions.length === 0 && query.length === 0 && (
        <div className="flex-1 flex flex-col items-center justify-center py-12">
          <Search className="w-8 h-8 text-text-ter/40 mb-3" />
          <p className="text-sm text-text-sec font-body">Search for a stock to trade</p>
          <p className="text-xs text-text-ter mt-1 font-body">Try NVDA, AAPL, TSLA...</p>
        </div>
      )}
    </div>
  )
}
