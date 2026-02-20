/* ------------------------------------------------------------------ */
/*  TypeScript interfaces for all Dossier profile data shapes          */
/* ------------------------------------------------------------------ */

export interface DimensionData {
  score: number
  label: string
  evidence: string[]
}

export interface DimensionConfig {
  key: string
  left: string
  right: string
  order: number
}

export const DIMENSION_CONFIG: Record<string, DimensionConfig> = {
  active_passive: { key: 'active_passive', left: 'Passive', right: 'Active', order: 0 },
  momentum_value: { key: 'momentum_value', left: 'Value', right: 'Momentum', order: 1 },
  concentrated_diversified: { key: 'concentrated_diversified', left: 'Diversified', right: 'Concentrated', order: 2 },
  disciplined_emotional: { key: 'disciplined_emotional', left: 'Emotional', right: 'Disciplined', order: 3 },
  sophisticated_simple: { key: 'sophisticated_simple', left: 'Simple', right: 'Sophisticated', order: 4 },
  improving_declining: { key: 'improving_declining', left: 'Declining', right: 'Improving', order: 5 },
  independent_herd: { key: 'independent_herd', left: 'Herd', right: 'Independent', order: 6 },
  risk_seeking_averse: { key: 'risk_seeking_averse', left: 'Conservative', right: 'Aggressive', order: 7 },
}

export interface BlindSpot {
  severity: 'danger' | 'warning' | 'info' | 'opportunity'
  title: string
  body: string
  evidence: { label: string; value: string }[]
}

export interface WashSaleResult {
  tickerCount: number
  totalEvents: number
  topTicker: string
  topTickerEvents: number
  crossAccountCount: number
}

export interface TradeRow {
  date: string
  side: string
  ticker: string | null
  instrument_type: string | null
  quantity: number | null
  price: number | null
  amount: number | null
  account_id: string | null
}

export interface HoldingRow {
  ticker: string | null
  instrument_type: string | null
  quantity: number | null
  market_value: number | null
  cost_basis: number | null
  unrealized_gain: number | null
  account_id: string | null
  instrument_details: Record<string, unknown> | null
  description: string | null
}

export interface ProfileMeta {
  profile_id: string
  name: string | null
  email: string | null
  brokerage: string | null
  tax_jurisdiction: string | null
  profile_completeness: string | null
  accounts: unknown | null
}

export interface RiskItem {
  risk: string
  detail: string
  severity: string
}

export interface AccountPurpose {
  account_id: string
  account_type: string
  purpose: string
  strategy: string
  estimated_value: string
}

export interface DossierProps {
  dimensions: Record<string, DimensionData> | null
  features: Record<string, unknown> | null
  narrative: Record<string, unknown> | null
  summaryStats: Record<string, unknown> | null
  holdingsFeatures: Record<string, unknown> | null
  portfolioNarrative: Record<string, unknown> | null
  trades: TradeRow[] | null
  holdings: HoldingRow[] | null
  profile: ProfileMeta | null
}
