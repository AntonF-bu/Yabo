'use client'

import { useState, useEffect } from 'react'
import { supabase } from '@/lib/supabase'

/* ================================================================== */
/*  Types                                                              */
/* ================================================================== */

interface RadarDimension {
  key: string
  score: number
  label: string // e.g. "Active Trader", "Fully Independent"
}

interface BehavioralRadarProps {
  profileId: string
}

/* ================================================================== */
/*  Dimension display config                                           */
/* ================================================================== */

const DISPLAY_ORDER = [
  'active_passive',
  'momentum_value',
  'independent_herd',
  'improving_declining',
  'risk_seeking_averse',
  'sophisticated_simple',
  'disciplined_emotional',
  'concentrated_diversified',
]

const SHORT_LABELS: Record<string, string> = {
  active_passive: 'Active',
  momentum_value: 'Momentum',
  independent_herd: 'Independent',
  improving_declining: 'Improving',
  risk_seeking_averse: 'Risk',
  sophisticated_simple: 'Sophistication',
  disciplined_emotional: 'Discipline',
  concentrated_diversified: 'Concentration',
}

/* ================================================================== */
/*  Component                                                          */
/* ================================================================== */

export default function BehavioralRadar({ profileId }: BehavioralRadarProps) {
  const [dimensions, setDimensions] = useState<RadarDimension[] | null>(null)
  const [behavioralSummary, setBehavioralSummary] = useState('')
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 50)
    return () => clearTimeout(t)
  }, [])

  useEffect(() => {
    const fetchData = async () => {
      const { data } = await supabase
        .from('analysis_results')
        .select('dimensions, narrative')
        .eq('profile_id', profileId)
        .eq('analysis_type', 'behavioral')
        .in('status', ['completed', 'partial'])
        .order('created_at', { ascending: false })
        .limit(1)
        .maybeSingle()

      if (!data) {
        setDimensions([])
        return
      }

      // Parse JSONB (may arrive as string from some Supabase configs)
      const rawDims = typeof data.dimensions === 'string'
        ? JSON.parse(data.dimensions)
        : data.dimensions
      const rawNarr = typeof data.narrative === 'string'
        ? JSON.parse(data.narrative)
        : data.narrative

      if (rawDims && typeof rawDims === 'object' && !Array.isArray(rawDims)) {
        // TODO: Restore when sophistication scoring is recalibrated for managed accounts
        const parsed: RadarDimension[] = DISPLAY_ORDER
          .filter(key => rawDims[key])
          .map(key => ({
            key,
            score: rawDims[key].score ?? 50,
            label: rawDims[key].label || '',
          }))
          .filter(d => d.key !== 'sophisticated_simple')
        setDimensions(parsed)
      } else {
        setDimensions([])
      }

      // Extract behavioral summary
      const cl = rawNarr?.classification_v2 || {}
      setBehavioralSummary(cl.behavioral_summary || rawNarr?.archetype_summary || '')
    }
    fetchData()
  }, [profileId])

  // Loading skeleton
  if (dimensions === null) {
    return (
      <div style={{ textAlign: 'center', padding: '40px 16px 0' }}>
        <div style={{ maxWidth: 720, margin: '0 auto' }}>
          <div style={{
            width: 300, height: 300, margin: '0 auto',
            borderRadius: '50%', border: '1px solid #EDE9E3',
            animation: 'radar-pulse 1.5s ease-in-out infinite',
          }} />
          <style>{`
            @keyframes radar-pulse {
              0%, 100% { background: #F3F0EA; }
              50% { background: #E4DFD7; }
            }
          `}</style>
        </div>
      </div>
    )
  }

  // Empty state
  if (dimensions.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '40px 16px 0' }}>
        <div style={{ maxWidth: 720, margin: '0 auto' }}>
          <p style={{
            fontFamily: "'Newsreader', Georgia, serif",
            fontSize: 16, fontStyle: 'italic', color: '#A09A94',
          }}>
            Behavioral analysis not yet available
          </p>
        </div>
      </div>
    )
  }

  // Order dimensions for octagon layout
  const ordered = DISPLAY_ORDER
    .map(key => dimensions.find(d => d.key === key))
    .filter(Boolean) as RadarDimension[]

  // If fewer than expected, use what we have
  const dims = ordered.length >= 3 ? ordered : dimensions

  const n = dims.length
  const size = 440
  const viewPad = 30
  const cx = size / 2
  const cy = size / 2
  const maxR = size / 2 - 86 // leave room for labels
  const levels = [25, 50, 75, 100]

  const angle = (i: number) => (Math.PI * 2 * i) / n - Math.PI / 2
  const point = (i: number, r: number) => ({
    x: cx + (r / 100) * maxR * Math.cos(angle(i)),
    y: cy + (r / 100) * maxR * Math.sin(angle(i)),
  })

  const dataPoints = dims.map((d, i) => point(i, d.score))
  const polyStr = dataPoints.map(p => `${p.x},${p.y}`).join(' ')

  // Build fallback summary if none provided
  const sorted = [...dims].sort((a, b) => b.score - a.score)
  const summary = behavioralSummary
    || (sorted.length >= 2
      ? `An ${sorted[0].label} trader with ${sorted[1].label} tendencies`
      : sorted.length === 1
        ? `An ${sorted[0].label} trader`
        : '')

  return (
    <div style={{
      textAlign: 'center', padding: '40px 16px 0',
      opacity: visible ? 1 : 0,
      transition: 'opacity 0.6s ease',
    }}>
      <div style={{ maxWidth: size + viewPad * 2, margin: '0 auto' }}>
        <svg
          viewBox={`${-viewPad} ${-viewPad} ${size + viewPad * 2} ${size + viewPad * 2}`}
          style={{ width: '100%', maxWidth: size + viewPad * 2, display: 'block', margin: '0 auto', overflow: 'visible' }}
        >
          {/* Concentric guide rings */}
          {levels.map(lv => {
            const pts = dims.map((_, i) => point(i, lv))
            return (
              <polygon
                key={lv}
                points={pts.map(p => `${p.x},${p.y}`).join(' ')}
                fill="none"
                stroke="#EDE9E3"
                strokeWidth={0.5}
                strokeDasharray="4 3"
              />
            )
          })}

          {/* Axis lines */}
          {dims.map((_, i) => {
            const outer = point(i, 100)
            return (
              <line
                key={`axis-${i}`}
                x1={cx} y1={cy}
                x2={outer.x} y2={outer.y}
                stroke="#EDE9E3"
                strokeWidth={1}
              />
            )
          })}

          {/* Data polygon */}
          <polygon
            points={polyStr}
            fill="#9A7B5B"
            fillOpacity={0.15}
            stroke="#9A7B5B"
            strokeWidth={1.5}
          />

          {/* Score dots */}
          {dims.map((_, i) => {
            const p = dataPoints[i]
            return (
              <circle
                key={`dot-${i}`}
                cx={p.x} cy={p.y} r={4}
                fill="#9A7B5B"
              />
            )
          })}

          {/* Labels */}
          {dims.map((d, i) => {
            const labelR = 118
            const lp = point(i, labelR)
            const a = angle(i)
            const cosA = Math.cos(a)
            const anchor = cosA < -0.3 ? 'end' : cosA > 0.3 ? 'start' : 'middle'

            const sinA = Math.sin(a)
            const yOffset = sinA < -0.3 ? 4 : sinA > 0.3 ? -2 : 0
            const shortLabel = SHORT_LABELS[d.key] || d.label

            return (
              <g key={`label-${d.key}`}>
                <text
                  x={lp.x} y={lp.y + yOffset}
                  textAnchor={anchor}
                  dominantBaseline="middle"
                  style={{
                    fontFamily: "'Inter', system-ui, sans-serif",
                    fontSize: 12,
                    fill: '#8A8580',
                  }}
                >
                  {shortLabel}
                </text>
                <text
                  x={lp.x} y={lp.y + yOffset + 16}
                  textAnchor={anchor}
                  dominantBaseline="middle"
                  style={{
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: 11,
                    fill: '#1A1715',
                  }}
                >
                  {Math.round(d.score)}
                </text>
              </g>
            )
          })}
        </svg>
      </div>

      {/* Behavioral summary line */}
      {summary && (
        <p style={{
          fontFamily: "'Newsreader', Georgia, serif",
          fontSize: 18, fontStyle: 'italic', color: '#1A1715',
          margin: '16px auto 32px', maxWidth: 520, lineHeight: 1.5,
        }}>
          {summary}
        </p>
      )}
    </div>
  )
}
