'use client'

import { useEffect, useRef, useState } from 'react'
import type { DossierProps } from '@/lib/profile/types'
import { DIMENSION_CONFIG } from '@/lib/profile/types'
import { formatDollars, computeObservationWindow } from '@/lib/profile/formatters'
import { computeBlindSpots } from '@/lib/profile/computeBlindSpots'
import { M } from '@/lib/profile/meridian'
import DnaRadar from '@/components/profile/DnaRadar'
import DimensionBar from '@/components/profile/DimensionBar'
import NarrativeBlock from '@/components/profile/NarrativeBlock'
import BlindSpotCard from '@/components/profile/BlindSpotCard'
import EntryInsights from '@/components/profile/EntryInsights'
import PsychologyPanel from '@/components/profile/PsychologyPanel'
import HoldingsTreemap from '@/components/profile/HoldingsTreemap'
import HoldingsInsights from '@/components/profile/HoldingsInsights'
import RiskPanel from '@/components/profile/RiskPanel'

/* ------------------------------------------------------------------ */
/*  Section wrapper with fade-in on scroll + editorial numbering       */
/* ------------------------------------------------------------------ */

function Section({ id, number, tag, title, subtitle, children }: {
  id: string
  number: string
  tag: string
  title: string
  subtitle?: string
  children: React.ReactNode
}) {
  const ref = useRef<HTMLElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVisible(true) },
      { threshold: 0.08 }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return (
    <section
      ref={ref}
      id={id}
      className="dossier-section"
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(20px)',
        transition: 'opacity 0.5s ease, transform 0.5s ease',
        padding: '64px 0',
        borderBottom: `1px solid ${M.border}`,
      }}
    >
      <div className="section-number" style={{
        fontFamily: M.serif,
        fontSize: 72,
        fontWeight: 300,
        color: M.surfaceDeep,
        lineHeight: 1,
        marginBottom: 8,
      }}>
        {number}
      </div>
      <div style={{
        fontFamily: M.mono,
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: '0.18em',
        textTransform: 'uppercase' as const,
        color: M.gold,
        marginBottom: 12,
      }}>
        {tag}
      </div>
      <div className="section-title" style={{
        fontFamily: M.serif,
        fontSize: 28,
        fontWeight: 400,
        color: M.ink,
        lineHeight: 1.25,
        letterSpacing: '-0.01em',
        marginBottom: 8,
      }}>
        {title}
      </div>
      {subtitle && (
        <div style={{
          fontSize: 14,
          fontFamily: M.sans,
          color: M.inkSecondary,
          lineHeight: 1.6,
          maxWidth: 520,
          marginBottom: 36,
        }}>
          {subtitle}
        </div>
      )}
      {children}
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  Meta chip                                                          */
/* ------------------------------------------------------------------ */

function MetaChip({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{
        fontFamily: M.mono,
        fontSize: 10,
        color: M.inkGhost,
        textTransform: 'uppercase' as const,
        letterSpacing: 1,
      }}>
        {label}
      </span>
      <span style={{
        fontFamily: M.mono,
        fontSize: 13,
        fontWeight: 500,
        color: M.ink,
      }}>
        {value}
      </span>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Main Dossier View                                                  */
/* ------------------------------------------------------------------ */

export default function DossierView({
  dimensions,
  features,
  narrative,
  summaryStats,
  holdingsFeatures,
  portfolioNarrative,
  trades,
  holdings,
  profile,
}: DossierProps) {
  // Sorted dimensions
  const sortedDims = Object.entries(DIMENSION_CONFIG)
    .sort((a, b) => a[1].order - b[1].order)
    .filter(([key]) => dimensions?.[key])

  // Blind spots
  const blindSpots = computeBlindSpots(features, holdingsFeatures, portfolioNarrative, trades, dimensions)

  // Narrative fields
  const headline = (narrative?.headline as string) || 'Your Trading DNA'
  const archetypeSummary = (narrative?.archetype_summary as string) || ''
  const firstSentence = archetypeSummary
    ? (archetypeSummary.match(/^[^.!?]+[.!?]/)?.[0] || archetypeSummary)
    : ''
  const deepDive = (narrative?.behavioral_deep_dive as string) || null
  const holdingsContextIncluded = narrative?.holdings_context_included === true
  const riskPersonality = (narrative?.risk_personality as string) || null

  // Meta
  const metaComputed = (features?._meta_computed_features as number) ?? null
  const metaTotal = (features?._meta_total_features as number) ?? null
  const totalTrades = (summaryStats?.total_trades as number) ?? null
  const observationWindow = computeObservationWindow(trades)
  const accountCount = (holdingsFeatures?.h_account_count as number) ?? null
  const totalValue = (holdingsFeatures?.h_total_value as number) ?? null
  const livePriceCount = (holdingsFeatures?._meta_live_price_count as number) ?? null
  const storedPriceCount = (holdingsFeatures?._meta_stored_price_count as number) ?? null

  // Holdings feature count (keys starting with h_, excluding _meta)
  const holdingsFeatureCount = holdingsFeatures
    ? Object.keys(holdingsFeatures).filter(k => k.startsWith('h_')).length
    : null

  // Check which sections have data
  const hasDimensions = sortedDims.length > 0
  const hasBlindSpots = blindSpots.length > 0
  const hasEntryFeatures = !!(features && (
    features.entry_breakout_score != null ||
    features.entry_dip_buyer_score != null ||
    features.entry_above_ma_score != null
  ))
  const hasPsychology = !!(features && (
    features.bias_disposition != null ||
    features.bias_overconfidence != null ||
    features.bias_action != null
  ))
  const hasHoldings = !!(holdings && holdings.length > 0)
  const hasRisk = !!(holdingsFeatures && (
    holdingsFeatures.h_stress_test_20pct != null ||
    holdingsFeatures.h_max_single_position_loss != null
  ))

  return (
    <main style={{ minHeight: '100vh', background: M.bg }}>
      {/* ─── HERO ─── */}
      <header style={{
        maxWidth: 1000,
        margin: '0 auto',
        padding: '72px 32px 56px',
        borderBottom: `1px solid ${M.border}`,
      }}>
        {/* Gold eyebrow */}
        <div style={{
          fontFamily: M.mono,
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: '0.15em',
          textTransform: 'uppercase' as const,
          color: M.gold,
          marginBottom: 20,
        }}>
          BEHAVIORAL INTELLIGENCE REPORT
        </div>

        <h1 className="dossier-headline" style={{
          fontFamily: M.serif,
          fontSize: 'clamp(32px, 4vw, 48px)' as unknown as number,
          fontWeight: 400,
          color: M.ink,
          lineHeight: 1.15,
          letterSpacing: '-0.02em',
          maxWidth: 720,
          margin: '0 0 12px',
        }}>
          {headline}
        </h1>
        {firstSentence && (
          <p style={{
            fontFamily: M.sans,
            fontSize: 16,
            color: M.inkSecondary,
            lineHeight: 1.65,
            maxWidth: 560,
            margin: '0 0 32px',
          }}>
            {firstSentence}
          </p>
        )}

        {/* Meta row */}
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '16px 40px',
          paddingTop: 24,
          borderTop: `1px solid ${M.border}`,
        }}>
          {profile?.profile_completeness && (
            <MetaChip label="Completeness" value={profile.profile_completeness} />
          )}
          {metaComputed != null && metaTotal != null && (
            <MetaChip label="Behavioral" value={`${metaComputed} of ${metaTotal}`} />
          )}
          {holdingsFeatureCount != null && (
            <MetaChip label="Holdings" value={`${holdingsFeatureCount} features`} />
          )}
          {totalTrades != null && (
            <MetaChip label="Trades" value={String(totalTrades)} />
          )}
          {observationWindow !== '--' && (
            <MetaChip label="Window" value={observationWindow} />
          )}
          {accountCount != null && (
            <MetaChip label="Accounts" value={String(accountCount)} />
          )}
          {totalValue != null && (
            <MetaChip label="Portfolio" value={formatDollars(totalValue)} />
          )}
          {livePriceCount != null && livePriceCount > 0 && (
            <MetaChip label="Pricing" value={`${livePriceCount} live${storedPriceCount ? ` / ${storedPriceCount} stored` : ''}`} />
          )}
        </div>
      </header>

      {/* ─── CONTENT ─── */}
      <div style={{
        maxWidth: 1000,
        margin: '0 auto',
        padding: '0 32px 80px',
      }}>
        {/* SECTION 01: TRADING DNA */}
        {hasDimensions && dimensions && (
          <Section
            id="trading-dna"
            number="01"
            tag="Trading DNA"
            title="Your behavioral fingerprint across 8 dimensions"
            subtitle="Each score is derived from multiple computed features, cross-referenced with real market data. Click any dimension to see the evidence."
          >
            <div className="radar-dims-grid" style={{
              display: 'grid',
              gridTemplateColumns: 'minmax(200px, 380px) 1fr',
              gap: 48,
              alignItems: 'start',
            }}>
              {/* Radar in bordered container */}
              <div style={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                background: M.surface,
                borderRadius: M.cardLg,
                border: `1px solid ${M.border}`,
                padding: 32,
                aspectRatio: '1',
              }}>
                <DnaRadar dimensions={dimensions} />
              </div>

              {/* Dimension bars */}
              <div>
                {sortedDims.map(([key, config]) => (
                  <DimensionBar
                    key={key}
                    dimKey={key}
                    data={dimensions[key]}
                    left={config.left}
                    right={config.right}
                  />
                ))}
              </div>
            </div>
          </Section>
        )}

        {/* NARRATIVE BLOCK */}
        <NarrativeBlock deepDive={deepDive} holdingsContextIncluded={holdingsContextIncluded} />

        {/* SECTION 02: BLIND SPOTS */}
        {hasBlindSpots && (
          <Section
            id="blind-spots"
            number="02"
            tag="Blind Spots"
            title="The patterns you can't see from the inside"
            subtitle="These are behaviors detected in your data that are invisible in the moment but visible in aggregate."
          >
            <div className="blindspots-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              {blindSpots.map((spot, i) => (
                <BlindSpotCard key={i} spot={spot} index={i} />
              ))}
            </div>
          </Section>
        )}

        {/* SECTION 03: ENTRY SIGNATURE */}
        {hasEntryFeatures && (
          <Section
            id="entry-signature"
            number="03"
            tag="Entry Signature"
            title="When and how you enter positions"
          >
            <EntryInsights features={features} dimensions={dimensions} />
          </Section>
        )}

        {/* SECTION 04: PSYCHOLOGY */}
        {hasPsychology && (
          <Section
            id="psychology"
            number="04"
            tag="Psychology"
            title="How winning and losing changes your behavior"
          >
            <PsychologyPanel
              features={features}
              dimensions={dimensions}
              riskPersonality={riskPersonality}
            />
          </Section>
        )}

        {/* SECTION 05: HOLDINGS INTELLIGENCE */}
        {(hasHoldings || portfolioNarrative) && (
          <Section
            id="holdings"
            number="05"
            tag="Holdings Intelligence"
            title="What your current portfolio reveals"
          >
            {hasHoldings && <HoldingsTreemap holdings={holdings} />}
            <div style={{ marginTop: hasHoldings ? 20 : 0 }}>
              <HoldingsInsights portfolioNarrative={portfolioNarrative} />
            </div>
          </Section>
        )}

        {/* SECTION 06: RISK */}
        {hasRisk && (
          <Section
            id="risk"
            number="06"
            tag="Risk"
            title="Your exposure under stress"
          >
            <RiskPanel holdingsFeatures={holdingsFeatures} portfolioNarrative={portfolioNarrative} />
          </Section>
        )}

        {/* RECOMMENDATION */}
        {typeof narrative?.key_recommendation === 'string' && narrative.key_recommendation && (
          <section style={{
            marginTop: 48,
            padding: '28px 24px',
            borderLeft: `4px solid ${M.gold}`,
            background: M.white,
            border: `1px solid ${M.border}`,
            borderLeftWidth: 4,
            borderLeftColor: M.gold,
            borderRadius: `0 ${M.card}px ${M.card}px 0`,
          }}>
            <div style={{
              fontFamily: M.mono,
              fontSize: 10,
              color: M.gold,
              textTransform: 'uppercase' as const,
              letterSpacing: '0.15em',
              marginBottom: 12,
            }}>
              KEY RECOMMENDATION
            </div>
            <p style={{
              fontFamily: M.serif,
              fontSize: 20,
              fontWeight: 400,
              color: M.ink,
              lineHeight: 1.7,
              margin: 0,
            }}>
              {narrative.key_recommendation}
            </p>
          </section>
        )}
      </div>

      {/* ─── FOOTER ─── */}
      <footer style={{
        padding: '24px',
        textAlign: 'center',
        borderTop: `1px solid ${M.border}`,
      }}>
        <span style={{
          fontFamily: M.mono,
          fontSize: 11,
          color: M.inkGhost,
        }}>
          Yabo Behavioral Intelligence
        </span>
      </footer>

      {/* ─── RESPONSIVE OVERRIDES ─── */}
      <style>{`
        @media (max-width: 768px) {
          .radar-dims-grid { grid-template-columns: 1fr !important; }
          .blindspots-grid { grid-template-columns: 1fr !important; }
          .entry-grid { grid-template-columns: 1fr !important; }
          .section-number { font-size: 48px !important; }
          .dossier-headline { font-size: 28px !important; }
        }
      `}</style>
    </main>
  )
}
