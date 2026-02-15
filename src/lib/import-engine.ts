import { supabase } from './supabase'
import { ImportedTrade } from '@/types'
import { getSector } from './sector-map'

/**
 * Import parsed trades into Supabase (trades + positions tables).
 * Clears existing imported trades first, then inserts fresh.
 */
export async function importTradesToSupabase(
  clerkId: string,
  trades: ImportedTrade[],
): Promise<{ tradesInserted: number; positionsUpserted: number }> {
  // 1. Delete existing imported trades and positions for this user
  await supabase.from('trades').delete().eq('clerk_id', clerkId).eq('source', 'csv_import')
  await supabase.from('positions').delete().eq('clerk_id', clerkId)

  // 2. Insert trades
  const tradeRows = trades.map((t) => ({
    clerk_id: clerkId,
    ticker: t.ticker,
    side: t.action,
    quantity: t.quantity,
    price: t.price,
    total_value: t.total,
    fees: 0,
    sector: t.sector || getSector(t.ticker),
    source: 'csv_import',
    created_at: t.date ? new Date(t.date).toISOString() : new Date().toISOString(),
  }))

  const { error: tradeError } = await supabase.from('trades').insert(tradeRows)
  if (tradeError) throw new Error(`Failed to insert trades: ${tradeError.message}`)

  // 3. Compute positions from trades
  const positionMap: Record<string, { shares: number; totalCost: number; sector: string; lastPrice: number }> = {}

  for (const t of trades) {
    if (!positionMap[t.ticker]) {
      positionMap[t.ticker] = { shares: 0, totalCost: 0, sector: t.sector || getSector(t.ticker), lastPrice: t.price }
    }
    const pos = positionMap[t.ticker]
    if (t.action === 'buy') {
      pos.totalCost += t.quantity * t.price
      pos.shares += t.quantity
    } else {
      pos.shares -= t.quantity
    }
    pos.lastPrice = t.price
  }

  // 4. Insert positions with shares > 0
  const positionRows = Object.entries(positionMap)
    .filter(([, p]) => p.shares > 0)
    .map(([ticker, p]) => ({
      clerk_id: clerkId,
      ticker,
      shares: p.shares,
      avg_cost: p.shares > 0 ? p.totalCost / (p.shares + Object.entries(positionMap).find(([t]) => t === ticker)?.[1].shares! - p.shares) : 0,
      current_price: p.lastPrice,
      sector: p.sector,
    }))

  // Recalculate avg_cost properly
  const cleanPositionRows = Object.entries(positionMap)
    .filter(([, p]) => p.shares > 0)
    .map(([ticker, p]) => {
      // Get all buys for this ticker to compute real avg cost
      const buys = trades.filter((t) => t.ticker === ticker && t.action === 'buy')
      const totalBuyQty = buys.reduce((s, t) => s + t.quantity, 0)
      const totalBuyCost = buys.reduce((s, t) => s + t.total, 0)
      const avgCost = totalBuyQty > 0 ? totalBuyCost / totalBuyQty : 0

      return {
        clerk_id: clerkId,
        ticker,
        shares: p.shares,
        avg_cost: avgCost,
        current_price: p.lastPrice,
        sector: p.sector,
      }
    })

  if (cleanPositionRows.length > 0) {
    const { error: posError } = await supabase.from('positions').insert(cleanPositionRows)
    if (posError) throw new Error(`Failed to insert positions: ${posError.message}`)
  }

  // 5. Update profile portfolio value
  const cash = 100000 - trades
    .reduce((sum, t) => {
      if (t.action === 'buy') return sum + t.total
      return sum - t.total
    }, 0)

  const posValue = cleanPositionRows.reduce((sum, p) => sum + p.shares * p.current_price, 0)

  await supabase.from('profiles').update({
    current_value: cash + posValue,
    updated_at: new Date().toISOString(),
  }).eq('clerk_id', clerkId)

  return {
    tradesInserted: trades.length,
    positionsUpserted: cleanPositionRows.length,
  }
}
