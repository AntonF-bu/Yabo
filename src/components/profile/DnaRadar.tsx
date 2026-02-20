'use client'

import { DIMENSION_CONFIG } from '@/lib/profile/types'
import type { DimensionData } from '@/lib/profile/types'

interface DnaRadarProps {
  dimensions: Record<string, DimensionData>
}

export default function DnaRadar({ dimensions }: DnaRadarProps) {
  const size = 400
  const cx = size / 2
  const cy = size / 2
  const maxR = 150
  const pad = 60
  const viewSize = size + pad * 2

  const entries = Object.entries(DIMENSION_CONFIG)
    .sort((a, b) => a[1].order - b[1].order)
    .filter(([key]) => dimensions[key])

  const n = entries.length
  if (n === 0) return null

  const getPoint = (index: number, radius: number) => {
    const angle = (Math.PI * 2 * index) / n - Math.PI / 2
    return {
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
    }
  }

  const levels = [25, 50, 75, 100]

  const guidePolygons = levels.map(level => {
    const r = (level / 100) * maxR
    const points = entries.map((_, i) => {
      const p = getPoint(i, r)
      return `${p.x},${p.y}`
    }).join(' ')
    return { level, points }
  })

  const dataPoints = entries.map(([key], i) => {
    const score = dimensions[key]?.score ?? 50
    const r = (score / 100) * maxR
    return getPoint(i, r)
  })
  const dataPolygon = dataPoints.map(p => `${p.x},${p.y}`).join(' ')

  const axisLines = entries.map((_, i) => getPoint(i, maxR))

  const labels = entries.map(([key, config], i) => {
    const p = getPoint(i, maxR + 28)
    const score = dimensions[key]?.score ?? 50
    const displayLabel = score >= 50 ? config.right : config.left
    return { x: p.x, y: p.y, label: displayLabel, score }
  })

  return (
    <svg
      viewBox={`${-pad} ${-pad} ${viewSize} ${viewSize}`}
      style={{ width: '100%', maxWidth: 380, height: 'auto' }}
    >
      {/* Guide rings */}
      {guidePolygons.map(({ level, points }) => (
        <polygon
          key={level}
          points={points}
          fill="none"
          stroke="#E8E4DE"
          strokeWidth={level === 50 ? 1 : 0.5}
          strokeDasharray={level === 50 ? undefined : '4 3'}
        />
      ))}

      {/* Axis lines */}
      {axisLines.map((p, i) => (
        <line
          key={i}
          x1={cx}
          y1={cy}
          x2={p.x}
          y2={p.y}
          stroke="#E8E4DE"
          strokeWidth={0.5}
        />
      ))}

      {/* Data polygon */}
      <polygon
        points={dataPolygon}
        fill="#9A7B5B"
        fillOpacity={0.12}
        stroke="#9A7B5B"
        strokeWidth={1.5}
      />

      {/* Data points */}
      {dataPoints.map((p, i) => (
        <circle
          key={i}
          cx={p.x}
          cy={p.y}
          r={4}
          fill="#9A7B5B"
        />
      ))}

      {/* Labels */}
      {labels.map((l, i) => {
        const angle = (Math.PI * 2 * i) / n - Math.PI / 2
        const isLeft = Math.cos(angle) < -0.1
        const isRight = Math.cos(angle) > 0.1
        const anchor = isLeft ? 'end' : isRight ? 'start' : 'middle'
        return (
          <g key={i}>
            <text
              x={l.x}
              y={l.y - 6}
              textAnchor={anchor}
              style={{
                fontFamily: "'Inter', system-ui, sans-serif",
                fontSize: 11,
                fill: '#8A8580',
              }}
            >
              {l.label}
            </text>
            <text
              x={l.x}
              y={l.y + 10}
              textAnchor={anchor}
              style={{
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: 11,
                fontWeight: 600,
                fill: '#1A1715',
              }}
            >
              {Math.round(l.score)}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
