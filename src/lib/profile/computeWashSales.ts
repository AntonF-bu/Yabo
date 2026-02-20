/* ------------------------------------------------------------------ */
/*  Wash sale detection — pure function, no API calls                  */
/* ------------------------------------------------------------------ */

import type { TradeRow, WashSaleResult } from './types'

export function computeWashSales(trades: TradeRow[] | null): WashSaleResult | null {
  if (!trades || trades.length === 0) return null

  const equityTrades = trades.filter(
    t => t.ticker && (t.instrument_type === 'equity' || t.instrument_type === 'etf')
  )

  if (equityTrades.length === 0) return null

  const sells = equityTrades.filter(t => t.side === 'sell')
  const buys = equityTrades.filter(t => t.side === 'buy')

  if (sells.length === 0 || buys.length === 0) return null

  const tickerEvents: Record<string, { events: number; crossAccount: number }> = {}
  const WINDOW_MS = 30 * 24 * 60 * 60 * 1000

  for (const sell of sells) {
    const sellDate = new Date(sell.date).getTime()
    if (isNaN(sellDate)) continue

    for (const buy of buys) {
      if (buy.ticker !== sell.ticker) continue
      const buyDate = new Date(buy.date).getTime()
      if (isNaN(buyDate)) continue

      const diff = buyDate - sellDate
      if (diff >= -WINDOW_MS && diff <= WINDOW_MS && diff !== 0) {
        if (!tickerEvents[sell.ticker!]) {
          tickerEvents[sell.ticker!] = { events: 0, crossAccount: 0 }
        }
        tickerEvents[sell.ticker!].events++
        if (sell.account_id !== buy.account_id) {
          tickerEvents[sell.ticker!].crossAccount++
        }
      }
    }
  }

  const tickers = Object.keys(tickerEvents)
  if (tickers.length === 0) return null

  let totalEvents = 0
  let crossAccountCount = 0
  let topTicker = ''
  let topTickerEvents = 0

  for (const ticker of tickers) {
    const entry = tickerEvents[ticker]
    totalEvents += entry.events
    crossAccountCount += entry.crossAccount
    if (entry.events > topTickerEvents) {
      topTickerEvents = entry.events
      topTicker = ticker
    }
  }

  return {
    tickerCount: tickers.length,
    totalEvents,
    topTicker,
    topTickerEvents,
    crossAccountCount,
  }
}
