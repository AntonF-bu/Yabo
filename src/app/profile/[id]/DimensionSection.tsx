'use client'

import DimensionCard from './DimensionCard'
import type { ProfileDimension } from './page'

/* ================================================================== */
/*  Types                                                              */
/* ================================================================== */

interface DimensionSectionProps {
  dimensions: ProfileDimension[]
}

/* ================================================================== */
/*  Component                                                          */
/* ================================================================== */

export default function DimensionSection({ dimensions }: DimensionSectionProps) {
  if (!dimensions || dimensions.length === 0) return null

  // Sort by score descending (strongest first)
  const sorted = [...dimensions].sort((a, b) => b.score - a.score)

  return (
    <div style={{ marginBottom: 28 }}>
      {/* Section header */}
      <p style={{
        fontFamily: "'Inter', system-ui, sans-serif",
        fontSize: 11, fontWeight: 600, letterSpacing: 2,
        color: '#9A7B5B', textTransform: 'uppercase',
        margin: '0 0 8px',
      }}>
        Behavioral Dimensions
      </p>

      {/* Dimension cards stack */}
      <div>
        {sorted.map((dim, i) => (
          <DimensionCard
            key={dim.key}
            dimensionKey={dim.key}
            score={dim.score}
            label={dim.label}
            evidence={dim.evidence || []}
            isLast={i === sorted.length - 1}
          />
        ))}
      </div>
    </div>
  )
}
