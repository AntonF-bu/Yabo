import { supabase } from '@/lib/supabase'
import type { Metadata } from 'next'
import Link from 'next/link'
import DossierView from './DossierView'
import ProcessingScreen from './ProcessingScreen'

/* ------------------------------------------------------------------ */
/*  Shared types — exported for legacy ProfileView (kept for compat)   */
/* ------------------------------------------------------------------ */

export interface ProfileDimension {
  key: string
  score: number
  label: string
  left: string
  right: string
  why: string
  details: Array<{ stat: string; desc: string }>
  evidence: string[]
}

export interface StatGroup {
  title: string
  subtitle: string
  items: Array<{ v: string; l: string; h: boolean; why: string }>
}

export interface SectorData {
  name: string
  pct: number
  trades: number
  color: string
}

export interface TickerData {
  name: string
  trades: number
  weight: number
}

export interface HoldData {
  range: string
  pct: number
}

export interface BiasData {
  key: string
  label: string
  score: number
  color: string
  why: string
}

export interface ProfileData {
  headline: string
  archetype: string
  tier: string
  behavioralSummary: string
  stats: {
    winRate: number | null
    profitFactor: number | null
    avgHold: number | null
    trades: number | null
    portfolioValue: number | null
  }
  dimensions: ProfileDimension[]
  entry: { groups: StatGroup[] } | null
  exit: { groups: StatGroup[] } | null
  timing: { groups: StatGroup[] } | null
  psychology: { biases: BiasData[]; groups: StatGroup[] } | null
  sectors: SectorData[]
  tickers: TickerData[]
  holds: HoldData[]
  recommendation: string | null
  riskPersonality: string | null
  behavioralDeepDive: string | null
  taxEfficiency: string | null
  meta: { range: string; months: number; totalTrades: number }
}

export interface PortfolioCompleteness {
  reconstructed_value: number
  completeness_confidence: 'partial' | 'complete'
  signals_of_additional_holdings: string[]
  prompt_for_more_data: boolean
}

/* eslint-disable @typescript-eslint/no-explicit-any */
export interface PortfolioData {
  portfolio_analysis: any | null
  portfolio_features: Record<string, any> | null
  accounts_detected: any[] | null
  account_summaries: Record<string, any> | null
  reconstructed_holdings: Record<string, any> | null
  instrument_breakdown: Record<string, any> | null
  portfolio_completeness: PortfolioCompleteness | null
}
/* eslint-enable @typescript-eslint/no-explicit-any */

/* ------------------------------------------------------------------ */
/*  Not found state                                                    */
/* ------------------------------------------------------------------ */

function NotFoundState() {
  return (
    <main style={{ minHeight: '100vh', background: '#FAF8F4', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px' }}>
      <div style={{ textAlign: 'center', maxWidth: 420 }}>
        <h1 style={{ fontFamily: "'Newsreader', Georgia, serif", fontSize: 28, fontWeight: 400, color: '#1A1715', marginBottom: 12 }}>
          Profile not found
        </h1>
        <p style={{ fontFamily: "'Inter', system-ui, sans-serif", fontSize: 15, color: '#8A8580', lineHeight: 1.6 }}>
          This analysis may still be in progress, or the link may be incorrect.
        </p>
        <Link href="/intake" style={{ display: 'inline-block', marginTop: 24, fontFamily: "'Inter', system-ui, sans-serif", fontSize: 14, color: '#9A7B5B', textDecoration: 'none' }}>
          Start a new analysis
        </Link>
      </div>
    </main>
  )
}

/* ------------------------------------------------------------------ */
/*  Metadata + Page                                                    */
/* ------------------------------------------------------------------ */

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: 'The Dossier | Yabo',
    description: 'Behavioral intelligence report — powered by Yabo',
  }
}

export default async function ProfilePage({
  params,
}: {
  params: { id: string }
}) {
  const profileId = params.id

  // ── Fetch all analysis results for this profile ──
  const { data: analysisResults } = await supabase
    .from('analysis_results')
    .select('*')
    .eq('profile_id', profileId)
    .eq('status', 'completed')

  // ── Fetch trades for scatter plot and wash sale computation ──
  const { data: trades } = await supabase
    .from('trades_new')
    .select('date, side, ticker, instrument_type, quantity, price, amount, account_id')
    .eq('profile_id', profileId)
    .order('date', { ascending: true })

  // ── Fetch holdings for treemap ──
  const { data: holdings } = await supabase
    .from('holdings')
    .select('ticker, instrument_type, quantity, market_value, cost_basis, unrealized_gain, account_id, instrument_details, description')
    .eq('profile_id', profileId)

  // ── Fetch profile metadata ──
  const { data: profile } = await supabase
    .from('profiles_new')
    .select('*')
    .eq('profile_id', profileId)
    .maybeSingle()

  if (!profile) {
    // Check if still processing
    const { data: pendingUploads } = await supabase
      .from('uploads')
      .select('id, status')
      .eq('profile_id', profileId)
      .in('status', ['uploaded', 'classifying', 'classified', 'processing'])

    if (pendingUploads && pendingUploads.length > 0) {
      return <ProcessingScreen profileId={profileId} />
    }
    return <NotFoundState />
  }

  // ── Separate analysis types ──
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const behavioral = analysisResults?.find((r: any) => r.analysis_type === 'behavioral')
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const holdingsBehavioral = analysisResults?.find((r: any) => r.analysis_type === 'holdings_behavioral')
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const portfolio = analysisResults?.find((r: any) => r.analysis_type === 'portfolio')

  // No analysis yet — check if processing
  if (!behavioral && !holdingsBehavioral && !portfolio) {
    const { data: pendingUploads } = await supabase
      .from('uploads')
      .select('id, status')
      .eq('profile_id', profileId)
      .in('status', ['uploaded', 'classifying', 'classified', 'processing'])

    if (pendingUploads && pendingUploads.length > 0) {
      return <ProcessingScreen profileId={profileId} />
    }
    return <NotFoundState />
  }

  // ── Pass to DossierView ──
  return (
    <DossierView
      dimensions={behavioral?.dimensions ?? null}
      features={behavioral?.features ?? null}
      narrative={behavioral?.narrative ?? null}
      summaryStats={behavioral?.summary_stats ?? null}
      holdingsFeatures={holdingsBehavioral?.features ?? null}
      portfolioNarrative={portfolio?.narrative ?? null}
      trades={trades ?? null}
      holdings={holdings ?? null}
      profile={{
        profile_id: profile.profile_id,
        name: profile.name ?? null,
        email: profile.email ?? null,
        brokerage: profile.brokerage ?? null,
        tax_jurisdiction: profile.tax_jurisdiction ?? null,
        profile_completeness: profile.profile_completeness ?? null,
        accounts: profile.accounts ?? null,
      }}
    />
  )
}
