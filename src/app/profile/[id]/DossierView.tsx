'use client'

import { useEffect, useRef, useState } from 'react'
import type { DossierProps } from '@/lib/profile/types'
import { DIMENSION_CONFIG } from '@/lib/profile/types'
import { formatDollars, computeObservationWindow } from '@/lib/profile/formatters'
import { computeBlindSpots } from '@/lib/profile/computeBlindSpots'
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
/*  Section wrapper with fade-in on scroll                             */
/* ------------------------------------------------------------------ */

function Section({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
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
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(20px)',
        transition: 'opacity 0.5s ease, transform 0.5s ease',
        marginBottom: 40,
      }}
    >
      <div style={{
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: 11,
        fontWeight: 600,
        color: '#A09A94',
        textTransform: 'uppercase',
        letterSpacing: 3,
        marginBottom: 16,
      }}>
        {label}
      </div>
      {children}
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  Meta chip                                                          */
/* ------------------------------------------------------------------ */

function MetaChip({ label, value }: { label: string; value: string }) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: 2,
    }}>
      <span style={{
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: 10,
        color: '#A09A94',
        textTransform: 'uppercase',
        letterSpacing: 1,
      }}>
        {label}
      </span>
      <span style={{
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: 13,
        fontWeight: 500,
        color: '#1A1715',
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
    <main style={{
      minHeight: '100vh',
      background: '#FAF8F4',
    }}>
      {/* ─── HERO ─── */}
      <header style={{
        maxWidth: 800,
        margin: '0 auto',
        padding: '48px 24px 32px',
      }}>
        <h1 style={{
          fontFamily: "'Newsreader', Georgia, serif",
          fontSize: 28,
          fontWeight: 400,
          color: '#1A1715',
          lineHeight: 1.35,
          margin: '0 0 8px',
        }}>
          {headline}
        </h1>
        {firstSentence && (
          <p style={{
            fontFamily: "'Inter', system-ui, sans-serif",
            fontSize: 15,
            color: '#6B6560',
            lineHeight: 1.6,
            margin: '0 0 24px',
          }}>
            {firstSentence}
          </p>
        )}

        {/* Meta row */}
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '16px 28px',
          padding: '16px 20px',
          background: '#F5F2EC',
          borderRadius: 10,
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
        </div>
      </header>

      {/* ─── CONTENT ─── */}
      <div style={{
        maxWidth: 800,
        margin: '0 auto',
        padding: '0 24px 80px',
      }}>
        {/* SECTION 01: TRADING DNA */}
        {hasDimensions && dimensions && (
          <Section id="trading-dna" label="01 / TRADING DNA">
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'minmax(200px, 340px) 1fr',
              gap: 24,
              alignItems: 'start',
            }}>
              {/* Radar */}
              <div style={{
                display: 'flex',
                justifyContent: 'center',
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
          <Section id="blind-spots" label="02 / BLIND SPOTS">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {blindSpots.map((spot, i) => (
                <BlindSpotCard key={i} spot={spot} />
              ))}
            </div>
          </Section>
        )}

        {/* SECTION 03: ENTRY SIGNATURE */}
        {hasEntryFeatures && (
          <Section id="entry-signature" label="03 / ENTRY SIGNATURE">
            <EntryInsights features={features} dimensions={dimensions} />
          </Section>
        )}

        {/* SECTION 04: PSYCHOLOGY */}
        {hasPsychology && (
          <Section id="psychology" label="04 / PSYCHOLOGY">
            <PsychologyPanel
              features={features}
              dimensions={dimensions}
              riskPersonality={riskPersonality}
            />
          </Section>
        )}

        {/* SECTION 05: HOLDINGS INTELLIGENCE */}
        {(hasHoldings || portfolioNarrative) && (
          <Section id="holdings" label="05 / HOLDINGS INTELLIGENCE">
            {hasHoldings && <HoldingsTreemap holdings={holdings} />}
            <div style={{ marginTop: hasHoldings ? 20 : 0 }}>
              <HoldingsInsights portfolioNarrative={portfolioNarrative} />
            </div>
          </Section>
        )}

        {/* SECTION 06: RISK */}
        {hasRisk && (
          <Section id="risk" label="06 / RISK">
            <RiskPanel holdingsFeatures={holdingsFeatures} portfolioNarrative={portfolioNarrative} />
          </Section>
        )}

        {/* RECOMMENDATION */}
        {typeof narrative?.key_recommendation === 'string' && narrative.key_recommendation && (
          <section style={{
            marginTop: 40,
            padding: '24px 20px',
            background: 'white',
            border: '1px solid #E8E4DE',
            borderRadius: 14,
          }}>
            <div style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 10,
              color: '#9A7B5B',
              textTransform: 'uppercase',
              letterSpacing: 2,
              marginBottom: 10,
            }}>
              KEY RECOMMENDATION
            </div>
            <p style={{
              fontFamily: "'Newsreader', Georgia, serif",
              fontSize: 17,
              fontWeight: 400,
              color: '#1A1715',
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
        borderTop: '1px solid #E8E4DE',
      }}>
        <span style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 11,
          color: '#A09A94',
        }}>
          Yabo Behavioral Intelligence
        </span>
      </footer>

      {/* ─── RESPONSIVE OVERRIDES ─── */}
      <style>{`
        @media (max-width: 640px) {
          #trading-dna > div > div {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </main>
  )
}
