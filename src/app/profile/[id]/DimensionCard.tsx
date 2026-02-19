'use client'

import { useState } from 'react'

/* ================================================================== */
/*  Dimension name mapping                                             */
/* ================================================================== */

const DIMENSION_META: Record<string, { display: string; low: string; high: string }> = {
  active_passive:           { display: 'Active vs Passive',     low: 'Passive',       high: 'Hyperactive' },
  momentum_value:           { display: 'Momentum vs Value',     low: 'Deep Value',    high: 'Pure Momentum' },
  independent_herd:         { display: 'Independent vs Herd',   low: 'Herd Follower', high: 'Fully Independent' },
  improving_declining:      { display: 'Improving vs Declining', low: 'Declining',    high: 'Rapidly Improving' },
  risk_seeking_averse:      { display: 'Risk Appetite',         low: 'Risk Averse',   high: 'Risk Seeking' },
  sophisticated_simple:     { display: 'Sophistication',        low: 'Beginner',      high: 'Highly Sophisticated' },
  disciplined_emotional:    { display: 'Discipline',            low: 'Emotional',     high: 'Highly Disciplined' },
  concentrated_diversified: { display: 'Concentration',         low: 'Diversified',   high: 'Concentrated' },
}

/* ================================================================== */
/*  Types                                                              */
/* ================================================================== */

interface DimensionCardProps {
  dimensionKey: string
  score: number
  label: string
  evidence: string[]
}

/* ================================================================== */
/*  Component                                                          */
/* ================================================================== */

export default function DimensionCard({ dimensionKey, score, label, evidence }: DimensionCardProps) {
  const [expanded, setExpanded] = useState(false)
  const meta = DIMENSION_META[dimensionKey] || { display: dimensionKey, low: '0', high: '100' }
  const pct = Math.max(0, Math.min(100, score))

  return (
    <div style={{
      border: '1px solid #EDE9E3',
      borderRadius: 12,
      padding: 16,
      background: '#FFFFFF',
    }}>
      {/* Header row: name + score badge */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <span style={{
          fontFamily: "'Newsreader', Georgia, serif",
          fontSize: 16, color: '#1A1715',
        }}>
          {meta.display}
        </span>
        <span style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 14, fontWeight: 600, color: '#1A1715',
          background: '#F3F0EA', borderRadius: 12,
          padding: '2px 10px',
        }}>
          {Math.round(score)}
        </span>
      </div>

      {/* Score bar with pole labels */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ fontFamily: "'Inter', system-ui, sans-serif", fontSize: 10, color: '#A09A94' }}>
            {meta.low}
          </span>
          <span style={{ fontFamily: "'Inter', system-ui, sans-serif", fontSize: 10, color: '#A09A94' }}>
            {meta.high}
          </span>
        </div>
        <div style={{
          width: '100%', height: 4, background: '#E4DFD7', borderRadius: 2,
          position: 'relative',
        }}>
          <div style={{
            width: `${pct}%`, height: 4, background: '#9A7B5B', borderRadius: 2,
          }} />
        </div>
      </div>

      {/* Dimension label */}
      <p style={{
        fontFamily: "'Inter', system-ui, sans-serif",
        fontSize: 13, color: '#8A8580',
        margin: '10px 0 0',
      }}>
        {label}
      </p>

      {/* Expandable evidence */}
      {evidence.length > 0 && (
        <>
          <button
            onClick={() => setExpanded(e => !e)}
            style={{
              fontFamily: "'Inter', system-ui, sans-serif",
              fontSize: 13, color: '#9A7B5B',
              background: 'none', border: 'none', cursor: 'pointer',
              padding: 0, marginTop: 8,
            }}
          >
            {expanded ? 'Hide evidence' : 'View evidence'}
          </button>
          <div style={{
            maxHeight: expanded ? 500 : 0,
            overflow: 'hidden',
            transition: 'max-height 0.3s ease',
          }}>
            <div style={{ paddingTop: 8 }}>
              {evidence.map((e, i) => (
                <div key={i} style={{
                  display: 'flex', gap: 8, alignItems: 'flex-start',
                  marginBottom: 4,
                }}>
                  <span style={{
                    color: '#9A7B5B', fontFamily: "'Inter', system-ui, sans-serif",
                    fontSize: 13, lineHeight: 1.6, flexShrink: 0,
                  }}>
                    --
                  </span>
                  <span style={{
                    fontFamily: "'Inter', system-ui, sans-serif",
                    fontSize: 13, color: '#8A8580', lineHeight: 1.6,
                  }}>
                    {e}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
