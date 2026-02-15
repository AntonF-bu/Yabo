const FINNHUB_BASE = 'https://finnhub.io/api/v1'
const API_KEY = process.env.NEXT_PUBLIC_FINNHUB_API_KEY

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

export async function getQuote(symbol: string): Promise<Quote> {
  const res = await fetch(
    `${FINNHUB_BASE}/quote?symbol=${symbol.toUpperCase()}&token=${API_KEY}`
  )
  if (!res.ok) throw new Error('Failed to fetch quote')
  return res.json()
}

export async function getStockProfile(symbol: string): Promise<StockProfile> {
  const res = await fetch(
    `${FINNHUB_BASE}/stock/profile2?symbol=${symbol.toUpperCase()}&token=${API_KEY}`
  )
  if (!res.ok) throw new Error('Failed to fetch profile')
  return res.json()
}

export async function searchTickers(query: string): Promise<SearchResult[]> {
  const res = await fetch(
    `${FINNHUB_BASE}/search?q=${encodeURIComponent(query)}&token=${API_KEY}`
  )
  if (!res.ok) throw new Error('Search failed')
  const data = await res.json()
  return (data.result || [])
    .filter((r: SearchResult) => r.type === 'Common Stock' && !r.symbol.includes('.'))
    .slice(0, 8)
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
