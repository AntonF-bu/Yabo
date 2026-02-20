'use client'

import type { DimensionData } from '@/lib/profile/types'

interface PsychologyPanelProps {
  features: Record<string, unknown> | null
  dimensions: Record<string, DimensionData> | null
  riskPersonality: string | null
}

function feat(features: Record<string, unknown> | null, key: string): number | null {
  if (!features) return null
  const v = features[key]
  if (v == null || typeof v !== 'number') return null
  return v
}

interface BiasCard {
  label: string
  value: number
  interpretation: string
  color: string
}

export default function PsychologyPanel({ features, dimensions, riskPersonality }: PsychologyPanelProps) {
  const cards: BiasCard[] = []

  const disposition = feat(features, 'bias_disposition')
  if (disposition != null) {
    cards.push({
      label: 'Disposition Effect',
      value: disposition,
      interpretation: disposition > 1
        ? `Score of ${disposition.toFixed(2)}. You hold losers longer than winners.`
        : `Score of ${disposition.toFixed(2)}. You manage winners and losers evenly.`,
      color: disposition > 1 ? '#A84B3F' : '#4A7C59',
    })
  }

  const overconfidence = feat(features, 'bias_overconfidence')
  if (overconfidence != null) {
    cards.push({
      label: 'Overconfidence',
      value: overconfidence,
      interpretation: overconfidence > 1
        ? `Score of ${overconfidence.toFixed(2)}. You increase size after wins.`
        : `Score of ${overconfidence.toFixed(2)}. Consistent sizing regardless of streak.`,
      color: overconfidence > 1 ? '#C4873B' : '#4A7C59',
    })
  }

  const actionBias = feat(features, 'bias_action')
  if (actionBias != null) {
    cards.push({
      label: 'Action Bias',
      value: actionBias,
      interpretation: actionBias > 70
        ? `Score of ${actionBias.toFixed(0)}. High compulsion to trade when you should wait.`
        : `Score of ${actionBias.toFixed(0)}. You can resist the urge to overtrade.`,
      color: actionBias > 70 ? '#C4873B' : '#4A7C59',
    })
  }

  const recency = feat(features, 'bias_recency')
  if (recency != null) {
    cards.push({
      label: 'Recency Bias',
      value: recency,
      interpretation: recency > 0
        ? `Score of ${recency.toFixed(2)}. Recent events disproportionately influence decisions.`
        : `Score of ${recency.toFixed(2)}. Negative recency -- you go against recent trends.`,
      color: Math.abs(recency) > 0.5 ? '#C4873B' : '#4A7C59',
    })
  }

  // Revenge trading from dimension evidence
  const disciplineEvidence = dimensions?.disciplined_emotional?.evidence || []
  let revengeInfo: string | null = null
  for (const e of disciplineEvidence) {
    if (/revenge/i.test(e)) {
      revengeInfo = e
      break
    }
  }

  return (
    <div>
      {/* Risk personality narrative */}
      {riskPersonality && (
        <div style={{
          background: '#F5F2EC',
          borderRadius: 10,
          padding: '16px 20px',
          marginBottom: 20,
        }}>
          <p style={{
            fontFamily: "'Inter', system-ui, sans-serif",
            fontSize: 14,
            color: '#1A1715',
            lineHeight: 1.7,
            margin: 0,
          }}>
            {riskPersonality}
          </p>
        </div>
      )}

      {/* Bias cards */}
      {cards.length > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
          gap: 12,
        }}>
          {cards.map((card, i) => (
            <div key={i} style={{
              background: 'white',
              border: '1px solid #E8E4DE',
              borderRadius: 10,
              padding: '16px 18px',
            }}>
              <div style={{
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: 10,
                color: '#A09A94',
                textTransform: 'uppercase',
                letterSpacing: 1,
                marginBottom: 8,
              }}>
                {card.label}
              </div>
              {/* Circular gauge */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <svg width={56} height={56} viewBox="0 0 56 56">
                  <circle cx={28} cy={28} r={22} fill="none" stroke="#EEEAE3" strokeWidth={4} />
                  <circle
                    cx={28} cy={28} r={22}
                    fill="none"
                    stroke={card.color}
                    strokeWidth={4}
                    strokeDasharray={`${Math.PI * 44}`}
                    strokeDashoffset={`${Math.PI * 44 * (1 - Math.min(Math.abs(card.value) / (card.label === 'Action Bias' ? 100 : 2), 1))}`}
                    strokeLinecap="round"
                    transform="rotate(-90 28 28)"
                    style={{ transition: 'stroke-dashoffset 0.5s ease' }}
                  />
                  <text
                    x={28} y={28}
                    textAnchor="middle"
                    dominantBaseline="central"
                    style={{
                      fontFamily: "'IBM Plex Mono', monospace",
                      fontSize: 12,
                      fontWeight: 600,
                      fill: '#1A1715',
                    }}
                  >
                    {card.label === 'Action Bias' ? Math.round(card.value) : card.value.toFixed(1)}
                  </text>
                </svg>
                <p style={{
                  fontFamily: "'Inter', system-ui, sans-serif",
                  fontSize: 12,
                  color: '#6B6560',
                  lineHeight: 1.5,
                  margin: 0,
                  flex: 1,
                }}>
                  {card.interpretation}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Revenge trading callout */}
      {revengeInfo && (
        <div style={{
          marginTop: 16,
          padding: '12px 16px',
          background: 'rgba(168,75,63,0.04)',
          borderLeft: '3px solid #A84B3F',
          borderRadius: '0 8px 8px 0',
        }}>
          <p style={{
            fontFamily: "'Inter', system-ui, sans-serif",
            fontSize: 12,
            color: '#6B6560',
            lineHeight: 1.6,
            margin: 0,
          }}>
            {revengeInfo}
          </p>
        </div>
      )}
    </div>
  )
}
