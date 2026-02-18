import { supabase } from '@/lib/supabase'
import type { Metadata } from 'next'
import Link from 'next/link'

/* ------------------------------------------------------------------ */
/*  Dimension display configuration                                    */
/* ------------------------------------------------------------------ */

const DIMENSIONS: Array<{ key: string; left: string; right: string }> = [
  { key: 'active_passive', left: 'Passive', right: 'Active' },
  { key: 'momentum_value', left: 'Value', right: 'Momentum' },
  { key: 'concentrated_diversified', left: 'Diversified', right: 'Concentrated' },
  { key: 'disciplined_emotional', left: 'Emotional', right: 'Disciplined' },
  { key: 'sophisticated_simple', left: 'Basic', right: 'Sophisticated' },
  { key: 'improving_declining', left: 'Declining', right: 'Improving' },
  { key: 'independent_herd', left: 'Herd', right: 'Independent' },
  { key: 'risk_seeking_averse', left: 'Risk Averse', right: 'Risk Seeking' },
]

/* ------------------------------------------------------------------ */
/*  Types for the raw_result JSONB blob                                */
/* ------------------------------------------------------------------ */

interface DimensionData {
  score: number
  label: string
  evidence: string[]
}

interface AnalysisResult {
  narrative?: {
    headline?: string
    archetype_summary?: string
    behavioral_deep_dive?: string
    risk_personality?: string
    key_recommendation?: string
    tax_efficiency?: string | null
    confidence_metadata?: {
      tier_label?: string
    }
  }
  classification_v2?: {
    dimensions?: Record<string, DimensionData>
    primary_archetype?: string
    behavioral_summary?: string
  }
  extraction?: {
    patterns?: {
      win_rate?: number
      profit_factor?: number
      holding_period?: { mean_days?: number }
      dominant_sectors?: Array<string | { sector?: string; name?: string }>
      ticker_concentration?: {
        top_3_tickers?: Array<{ ticker: string; pct?: number } | string>
      }
    }
    risk_profile?: {
      estimated_portfolio_value?: number
    }
    metadata?: {
      total_trades?: number
      date_range?: {
        start?: string
        end?: string
      }
    }
    confidence_metadata?: {
      confidence_tier?: string
    }
  }
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return ''
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
  } catch {
    return dateStr
  }
}

function fmtNum(n: number | undefined | null, decimals = 1): string {
  if (n === undefined || n === null) return '--'
  return Number(n).toFixed(decimals)
}

function fmtCurrency(n: number | undefined | null): string {
  if (n === undefined || n === null) return '--'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(n)
}

function renderProse(text: string | undefined | null) {
  if (!text) return null
  const paragraphs = text.split(/\n\n+/).filter(Boolean)
  return paragraphs.map((p, i) => (
    <p key={i} className="mb-4 last:mb-0">
      {p.trim()}
    </p>
  ))
}

/* ------------------------------------------------------------------ */
/*  State components                                                   */
/* ------------------------------------------------------------------ */

function NotFoundState() {
  return (
    <main className="min-h-screen bg-bg flex items-center justify-center px-6">
      <div className="text-center max-w-md">
        <h1 className="font-display text-3xl text-text mb-4">
          Profile not found
        </h1>
        <p className="font-body text-text-sec leading-relaxed">
          This analysis may still be in progress, or the link may be incorrect.
        </p>
        <Link
          href="/intake"
          className="inline-block mt-8 text-sm font-body text-teal hover:underline"
        >
          Start a new analysis
        </Link>
      </div>
    </main>
  )
}

function ProcessingState() {
  return (
    <main className="min-h-screen bg-bg flex items-center justify-center px-6">
      <div className="text-center max-w-md">
        <h1 className="font-display text-3xl text-text mb-4">
          Your analysis is being processed
        </h1>
        <p className="font-body text-text-sec leading-relaxed">
          Check back shortly. We&apos;ll have your Trading DNA ready soon.
        </p>
        <Link
          href="/intake"
          className="inline-block mt-8 text-sm font-body text-teal hover:underline"
        >
          Submit another analysis
        </Link>
      </div>
    </main>
  )
}

/* ------------------------------------------------------------------ */
/*  Metadata                                                           */
/* ------------------------------------------------------------------ */

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: 'Trading DNA Profile | Yabo',
    description: 'Behavioral trading analysis powered by Yabo',
  }
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default async function ProfilePage({
  params,
}: {
  params: { id: string }
}) {
  const profileId = params.id

  const { data, error } = await supabase
    .from('trade_imports')
    .select('raw_result, status, trade_count')
    .eq('profile_id', profileId)
    .order('created_at', { ascending: false })
    .limit(1)
    .maybeSingle()

  if (!data || error) return <NotFoundState />
  if (data.status !== 'processed') return <ProcessingState />

  const result = data.raw_result as AnalysisResult | null
  if (!result) return <NotFoundState />

  const narrative = result.narrative
  const v2 = result.classification_v2
  const extraction = result.extraction
  const dimensions = v2?.dimensions || {}

  // Key stats
  const winRate = extraction?.patterns?.win_rate
  const profitFactor = extraction?.patterns?.profit_factor
  const avgHold = extraction?.patterns?.holding_period?.mean_days
  const totalTrades = extraction?.metadata?.total_trades
  const confidenceTier =
    narrative?.confidence_metadata?.tier_label ||
    extraction?.confidence_metadata?.confidence_tier
  const startDate = extraction?.metadata?.date_range?.start
  const endDate = extraction?.metadata?.date_range?.end
  const portfolioValue = extraction?.risk_profile?.estimated_portfolio_value
  const dominantSectors = extraction?.patterns?.dominant_sectors || []
  const topTickers =
    extraction?.patterns?.ticker_concentration?.top_3_tickers || []

  return (
    <main className="min-h-screen bg-bg">
      {/* ── 1. HEADER ─────────────────────────────────────────── */}
      <header className="px-4 sm:px-6 py-4 border-b border-border">
        <div className="max-w-[720px] mx-auto flex items-center">
          <Link
            href="/"
            className="font-display text-lg font-semibold text-text"
          >
            Yabo
          </Link>
        </div>
      </header>

      <div className="px-4 sm:px-6">
        <div className="max-w-[720px] mx-auto pb-24">
          {/* ── 2. HEADLINE BLOCK ───────────────────────────────── */}
          <section
            className="pt-16 pb-12 text-center"
            style={{ animation: 'fade-up 0.5s ease-out both' }}
          >
            {narrative?.headline && (
              <h1
                className="font-display text-3xl sm:text-4xl md:text-[44px] text-text leading-[1.15] tracking-[-0.5px]"
                style={{ fontWeight: 400 }}
              >
                {narrative.headline}
              </h1>
            )}

            {v2?.behavioral_summary && (
              <p className="mt-5 font-display text-lg sm:text-xl text-text-sec italic leading-relaxed max-w-[560px] mx-auto">
                {v2.behavioral_summary}
              </p>
            )}

            <div className="mt-6 flex items-center justify-center gap-3 flex-wrap">
              {v2?.primary_archetype && (
                <span className="px-3 py-1 rounded-full border border-border text-xs font-body font-medium text-text uppercase tracking-wider">
                  {v2.primary_archetype}
                </span>
              )}
              {confidenceTier && (
                <span className="px-3 py-1 rounded-full border border-border text-xs font-body text-text-sec uppercase tracking-wider">
                  {confidenceTier}
                </span>
              )}
            </div>
          </section>

          {/* ── 3. KEY STATS ROW ────────────────────────────────── */}
          <section
            className="pb-16"
            style={{ animation: 'fade-up 0.5s ease-out 0.1s both' }}
          >
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-6 sm:gap-4">
              {[
                {
                  label: 'Win Rate',
                  value:
                    winRate != null
                      ? `${fmtNum(winRate <= 1 ? winRate * 100 : winRate, 1)}%`
                      : '--',
                },
                {
                  label: 'Profit Factor',
                  value:
                    profitFactor != null ? fmtNum(profitFactor, 2) : '--',
                },
                {
                  label: 'Avg Hold',
                  value: avgHold != null ? `${Math.round(avgHold)}d` : '--',
                },
                {
                  label: 'Total Trades',
                  value: totalTrades != null ? String(totalTrades) : '--',
                },
                {
                  label: 'Confidence',
                  value: confidenceTier || '--',
                },
              ].map((stat) => (
                <div key={stat.label} className="text-center">
                  <p
                    className="font-mono text-2xl font-semibold"
                    style={{ color: '#B8860B' }}
                  >
                    {stat.value}
                  </p>
                  <p className="text-[11px] font-body font-medium uppercase tracking-[1.5px] text-text-ter mt-1">
                    {stat.label}
                  </p>
                </div>
              ))}
            </div>
          </section>

          {/* ── 4. BEHAVIORAL DIMENSIONS ────────────────────────── */}
          {(() => {
            const hasDimensions =
              v2?.dimensions &&
              DIMENSIONS.some(({ key }) => v2.dimensions?.[key])

            if (!hasDimensions) {
              return (
                <section
                  className="pb-16"
                  style={{ animation: 'fade-up 0.5s ease-out 0.2s both' }}
                >
                  <p className="text-[11px] font-body font-semibold tracking-[3px] text-text-ter uppercase mb-6">
                    Your Trading DNA
                  </p>
                  <p className="font-body text-sm text-text-sec">
                    Dimensional analysis is not available for this profile.
                  </p>
                </section>
              )
            }

            return (
              <section
                className="pb-16"
                style={{ animation: 'fade-up 0.5s ease-out 0.2s both' }}
              >
                <p className="text-[11px] font-body font-semibold tracking-[3px] text-text-ter uppercase mb-10">
                  Your Trading DNA
                </p>

                <div className="space-y-10">
                  {DIMENSIONS.map(({ key, left, right }) => {
                    const dim = dimensions[key]
                    if (!dim) return null
                    const score = dim.score ?? 50
                    const label = dim.label || ''
                    const evidence = dim.evidence || []

                    return (
                      <div key={key}>
                        {/* Bar with pole labels */}
                        <div className="flex items-center gap-2 sm:gap-3">
                          <span className="text-[11px] sm:text-xs font-body text-text-sec w-16 sm:w-24 text-right shrink-0">
                            {left}
                          </span>
                          <div className="flex-1 relative h-6 flex items-center">
                            {/* Track */}
                            <div className="w-full h-[5px] bg-[#EDE9E3] rounded-full" />
                            {/* Marker */}
                            <div
                              className="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full border-[2.5px] border-white"
                              style={{
                                left: `calc(${Math.max(2, Math.min(98, score))}% - 8px)`,
                                backgroundColor: '#B8860B',
                                boxShadow: '0 1px 4px rgba(0,0,0,0.15)',
                              }}
                            />
                          </div>
                          <span className="text-[11px] sm:text-xs font-body text-text-sec w-16 sm:w-24 shrink-0">
                            {right}
                          </span>
                        </div>

                        {/* Dimension label */}
                        <p className="text-center text-[13px] font-body font-medium text-text mt-2">
                          {label}
                        </p>

                        {/* Evidence strings */}
                        {evidence.length > 0 && (
                          <div className="mt-1.5 space-y-0.5">
                            {evidence.slice(0, 3).map((ev, i) => (
                              <p
                                key={i}
                                className="text-center text-[11px] font-body text-text-ter leading-relaxed"
                              >
                                {ev}
                              </p>
                            ))}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </section>
            )
          })()}

          {/* ── 5. BEHAVIORAL DEEP DIVE ─────────────────────────── */}
          {narrative?.behavioral_deep_dive && (
            <section className="pb-16">
              <p className="text-[11px] font-body font-semibold tracking-[3px] text-text-ter uppercase mb-6">
                Behavioral Analysis
              </p>
              <div className="font-body text-[15px] text-text leading-[1.8]">
                {renderProse(narrative.behavioral_deep_dive)}
              </div>
            </section>
          )}

          {/* ── 6. RISK PERSONALITY ─────────────────────────────── */}
          {narrative?.risk_personality && (
            <section className="pb-16">
              <p className="text-[11px] font-body font-semibold tracking-[3px] text-text-ter uppercase mb-6">
                Risk Personality
              </p>
              <div className="font-body text-[15px] text-text leading-[1.8]">
                {renderProse(narrative.risk_personality)}
              </div>
            </section>
          )}

          {/* ── 9. TAX EFFICIENCY (conditional) ─────────────────── */}
          {narrative?.tax_efficiency && (
            <section className="pb-16">
              <p className="text-[11px] font-body font-semibold tracking-[3px] text-text-ter uppercase mb-6">
                Tax Efficiency
              </p>
              <div className="font-body text-[15px] text-text leading-[1.8]">
                {renderProse(narrative.tax_efficiency)}
              </div>
            </section>
          )}

          {/* ── 7. KEY RECOMMENDATION ───────────────────────────── */}
          {narrative?.key_recommendation && (
            <section className="pb-16">
              <div
                className="rounded-lg border border-border p-6 sm:p-8"
                style={{
                  borderLeftWidth: '3px',
                  borderLeftColor: '#B8860B',
                  backgroundColor: '#F5F2EC',
                }}
              >
                <p className="text-[11px] font-body font-semibold tracking-[3px] text-text-ter uppercase mb-4">
                  Key Recommendation
                </p>
                <div className="font-body text-[15px] text-text leading-[1.8]">
                  {renderProse(narrative.key_recommendation)}
                </div>
              </div>
            </section>
          )}

          {/* ── 8. PORTFOLIO CONTEXT ────────────────────────────── */}
          {(dominantSectors.length > 0 ||
            topTickers.length > 0 ||
            startDate ||
            endDate ||
            (portfolioValue != null && portfolioValue > 0)) && (
            <section className="pb-16">
              <p className="text-[11px] font-body font-semibold tracking-[3px] text-text-ter uppercase mb-6">
                Portfolio Context
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                {dominantSectors.length > 0 && (
                  <div>
                    <p className="text-[11px] font-body font-medium text-text-ter uppercase tracking-wider mb-1">
                      Top Sectors
                    </p>
                    <p className="font-body text-sm text-text">
                      {dominantSectors
                        .slice(0, 5)
                        .map((s) =>
                          typeof s === 'string'
                            ? s
                            : s.sector || s.name || String(s)
                        )
                        .join(', ')}
                    </p>
                  </div>
                )}
                {topTickers.length > 0 && (
                  <div>
                    <p className="text-[11px] font-body font-medium text-text-ter uppercase tracking-wider mb-1">
                      Top Tickers
                    </p>
                    <p className="font-mono text-sm text-text">
                      {topTickers
                        .slice(0, 5)
                        .map((t) =>
                          typeof t === 'string' ? t : t.ticker
                        )
                        .join(', ')}
                    </p>
                  </div>
                )}
                {(startDate || endDate) && (
                  <div>
                    <p className="text-[11px] font-body font-medium text-text-ter uppercase tracking-wider mb-1">
                      Date Range
                    </p>
                    <p className="font-body text-sm text-text">
                      {formatDate(startDate)}
                      {startDate && endDate ? ' \u2013 ' : ''}
                      {formatDate(endDate)}
                    </p>
                  </div>
                )}
                {portfolioValue != null && portfolioValue > 0 && (
                  <div>
                    <p className="text-[11px] font-body font-medium text-text-ter uppercase tracking-wider mb-1">
                      Est. Portfolio Value
                    </p>
                    <p className="font-mono text-sm text-text">
                      {fmtCurrency(portfolioValue)}
                    </p>
                  </div>
                )}
              </div>
            </section>
          )}

          {/* ── 10. FOOTER ──────────────────────────────────────── */}
          <footer className="border-t border-border pt-8">
            <p className="text-xs font-body text-text-ter text-center">
              Analysis based on {totalTrades ?? '--'} trades
              {startDate || endDate
                ? ` from ${formatDate(startDate)} to ${formatDate(endDate)}`
                : ''}
            </p>
            <p className="text-xs font-body text-text-ter text-center mt-1">
              Powered by Yabo Behavioral Mirror v0.5
            </p>
          </footer>
        </div>
      </div>
    </main>
  )
}
