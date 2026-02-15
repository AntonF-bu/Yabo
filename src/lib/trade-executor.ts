import { supabase } from './supabase'
import { calculateSlippage, calculateCommission } from './rules-engine'

export async function executeTrade(
  clerkId: string,
  order: { ticker: string; side: 'buy' | 'sell'; quantity: number; price: number; sector: string }
) {
  const executionPrice = calculateSlippage(order.price, order.side)
  const commission = calculateCommission(order.quantity)
  const totalValue = order.quantity * executionPrice

  // 1. Insert immutable trade record
  const { error: tradeError } = await supabase.from('trades').insert({
    clerk_id: clerkId,
    ticker: order.ticker,
    side: order.side,
    quantity: order.quantity,
    price: executionPrice,
    total_value: totalValue,
    fees: commission,
    sector: order.sector,
    source: 'manual',
  })
  if (tradeError) throw tradeError

  // 2. Update position
  const { data: existing } = await supabase
    .from('positions')
    .select('*')
    .eq('clerk_id', clerkId)
    .eq('ticker', order.ticker)
    .single()

  if (order.side === 'buy') {
    if (existing) {
      const newShares = Number(existing.shares) + order.quantity
      const newAvgCost = (
        (Number(existing.shares) * Number(existing.avg_cost)) +
        (order.quantity * executionPrice)
      ) / newShares

      await supabase.from('positions').update({
        shares: newShares,
        avg_cost: newAvgCost,
        current_price: executionPrice,
        updated_at: new Date().toISOString(),
      }).eq('id', existing.id)
    } else {
      await supabase.from('positions').insert({
        clerk_id: clerkId,
        ticker: order.ticker,
        shares: order.quantity,
        avg_cost: executionPrice,
        current_price: executionPrice,
        sector: order.sector,
      })
    }
  }

  if (order.side === 'sell' && existing) {
    const newShares = Number(existing.shares) - order.quantity
    if (newShares <= 0) {
      await supabase.from('positions').delete().eq('id', existing.id)
    } else {
      await supabase.from('positions').update({
        shares: newShares,
        current_price: executionPrice,
        updated_at: new Date().toISOString(),
      }).eq('id', existing.id)
    }
  }

  // 3. Recalculate portfolio value
  await recalculatePortfolio(clerkId)

  return { executionPrice, commission, totalValue }
}

async function recalculatePortfolio(clerkId: string) {
  const { data: trades } = await supabase
    .from('trades').select('*').eq('clerk_id', clerkId)

  const { data: positions } = await supabase
    .from('positions').select('*').eq('clerk_id', clerkId)

  let cash = 100000
  for (const t of (trades || [])) {
    if (t.side === 'buy') cash -= Number(t.total_value) + Number(t.fees)
    else cash += Number(t.total_value) - Number(t.fees)
  }

  const positionValue = (positions || []).reduce(
    (sum: number, p: Record<string, unknown>) => sum + (Number(p.shares) * Number(p.current_price)), 0
  )

  await supabase.from('profiles').update({
    current_value: cash + positionValue,
    updated_at: new Date().toISOString(),
  }).eq('clerk_id', clerkId)
}
