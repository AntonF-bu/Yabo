'use client'

import { useUser } from '@clerk/nextjs'
import { useState, useEffect, useCallback } from 'react'
import { supabase } from '@/lib/supabase'

export interface PortfolioPositionRow {
  id: string
  clerk_id: string
  ticker: string
  shares: number
  avg_cost: number
  current_price: number
  sector: string
  created_at: string
  updated_at: string
}

export interface TradeRow {
  id: string
  clerk_id: string
  ticker: string
  side: 'buy' | 'sell'
  quantity: number
  price: number
  total_value: number
  fees: number
  sector: string
  source: string
  created_at: string
}

export function usePortfolio() {
  const { user } = useUser()
  const [positions, setPositions] = useState<PortfolioPositionRow[]>([])
  const [trades, setTrades] = useState<TradeRow[]>([])
  const [cash, setCash] = useState(100000)
  const [totalValue, setTotalValue] = useState(100000)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    if (!user) return

    try {
      const [posRes, tradeRes] = await Promise.all([
        supabase.from('positions').select('*').eq('clerk_id', user.id),
        supabase.from('trades').select('*').eq('clerk_id', user.id).order('created_at', { ascending: false }),
      ])

      const posData = (posRes.data || []) as PortfolioPositionRow[]
      const tradeData = (tradeRes.data || []) as TradeRow[]

      setPositions(posData)
      setTrades(tradeData)

      let c = 100000
      for (const t of tradeData) {
        if (t.side === 'buy') c -= Number(t.total_value) + Number(t.fees)
        else c += Number(t.total_value) - Number(t.fees)
      }
      setCash(c)

      const posVal = posData.reduce(
        (sum, p) => sum + (Number(p.shares) * Number(p.current_price)), 0
      )
      setTotalValue(c + posVal)
    } catch {
      // Supabase may not be set up yet
    }
    setLoading(false)
  }, [user])

  useEffect(() => { refresh() }, [refresh])

  return { positions, trades, cash, totalValue, loading, refresh }
}
