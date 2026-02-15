const FINNHUB_BASE = 'https://finnhub.io/api/v1'
const API_KEY = process.env.NEXT_PUBLIC_FINNHUB_API_KEY

// Rate limiting: 200ms between Finnhub calls
let lastCallTime = 0
const MIN_INTERVAL = 200

async function rateLimitedFetch(url: string): Promise<Response> {
  const now = Date.now()
  const wait = Math.max(0, MIN_INTERVAL - (now - lastCallTime))
  if (wait > 0) await new Promise(r => setTimeout(r, wait))
  lastCallTime = Date.now()
  return fetch(url)
}

export interface Quote {
  c: number   // current price
  d: number   // change
  dp: number  // percent change
  h: number   // high
  l: number   // low
  o: number   // open
  pc: number  // previous close
  t: number   // timestamp
}

export interface StockProfile {
  ticker: string
  name: string
  finnhubIndustry: string
  marketCapitalization: number
  logo: string
  exchange: string
  country: string
}

export interface SearchResult {
  description: string
  displaySymbol: string
  symbol: string
  type: string
}

export interface CandlePoint {
  date: string
  close: number
  high: number
  low: number
  open: number
  volume: number
}

export async function getQuote(symbol: string): Promise<Quote> {
  const res = await rateLimitedFetch(
    `${FINNHUB_BASE}/quote?symbol=${symbol.toUpperCase()}&token=${API_KEY}`
  )
  if (!res.ok) throw new Error('Failed to fetch quote')
  return res.json()
}

export async function getStockProfile(symbol: string): Promise<StockProfile> {
  const res = await rateLimitedFetch(
    `${FINNHUB_BASE}/stock/profile2?symbol=${symbol.toUpperCase()}&token=${API_KEY}`
  )
  if (!res.ok) throw new Error('Failed to fetch profile')
  return res.json()
}

export async function searchTickers(query: string): Promise<SearchResult[]> {
  const res = await rateLimitedFetch(
    `${FINNHUB_BASE}/search?q=${encodeURIComponent(query)}&token=${API_KEY}`
  )
  if (!res.ok) throw new Error('Search failed')
  const data = await res.json()
  return (data.result || [])
    .filter((r: SearchResult) => r.type === 'Common Stock' && !r.symbol.includes('.'))
    .slice(0, 8)
}

export function getTimeRange(period: string): { from: number; to: number } {
  const to = Math.floor(Date.now() / 1000)
  const periods: Record<string, number> = {
    '1W': 7 * 86400,
    '1M': 30 * 86400,
    '3M': 90 * 86400,
    '6M': 180 * 86400,
    '1Y': 365 * 86400,
  }
  const from = to - (periods[period] || periods['3M'])
  return { from, to }
}

export async function getCandles(
  symbol: string,
  resolution: string = 'D',
  from: number,
  to: number,
): Promise<CandlePoint[]> {
  const res = await rateLimitedFetch(
    `${FINNHUB_BASE}/stock/candle?symbol=${symbol.toUpperCase()}&resolution=${resolution}&from=${from}&to=${to}&token=${API_KEY}`
  )
  if (!res.ok) throw new Error('Failed to fetch candles')
  const data = await res.json()

  if (data.s === 'no_data' || !data.t) return []

  return data.t.map((timestamp: number, i: number) => ({
    date: new Date(timestamp * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    close: data.c[i],
    high: data.h[i],
    low: data.l[i],
    open: data.o[i],
    volume: data.v[i],
  }))
}

export function mapToSector(finnhubIndustry: string): string {
  const mapping: Record<string, string> = {
    'Technology': 'Technology',
    'Software': 'Technology',
    'Semiconductors': 'Semiconductors',
    'Media': 'Technology',
    'Telecommunications': 'Technology',
    'Financial Services': 'Financials',
    'Banking': 'Financials',
    'Insurance': 'Financials',
    'Healthcare': 'Healthcare',
    'Biotechnology': 'Healthcare',
    'Pharmaceuticals': 'Healthcare',
    'Energy': 'Energy',
    'Oil & Gas': 'Energy',
    'Consumer Cyclical': 'Consumer',
    'Consumer Defensive': 'Consumer',
    'Retail': 'Consumer',
    'Industrials': 'Industrials',
    'Aerospace & Defense': 'Industrials',
    'Real Estate': 'Real Estate',
    'REITs': 'Real Estate',
    'Utilities': 'Utilities',
    'Basic Materials': 'Materials',
  }
  return mapping[finnhubIndustry] || 'Other'
}
