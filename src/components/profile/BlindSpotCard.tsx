'use client'

import type { BlindSpot } from '@/lib/profile/types'
import EvidenceChip from './EvidenceChip'

interface BlindSpotCardProps {
  spot: BlindSpot
}

const SEVERITY_STYLES: Record<BlindSpot['severity'], { border: string; bg: string; icon: string }> = {
  danger: { border: '#A84B3F', bg: 'rgba(168,75,63,0.04)', icon: '!!' },
  warning: { border: '#C4873B', bg: 'rgba(196,135,59,0.04)', icon: '!' },
  info: { border: '#5B7B9A', bg: 'rgba(91,123,154,0.04)', icon: 'i' },
  opportunity: { border: '#4A7C59', bg: 'rgba(74,124,89,0.04)', icon: '+' },
}

export default function BlindSpotCard({ spot }: BlindSpotCardProps) {
  const style = SEVERITY_STYLES[spot.severity]

  return (
    <div style={{
      background: style.bg,
      border: `1px solid ${style.border}20`,
      borderLeft: `3px solid ${style.border}`,
      borderRadius: 10,
      padding: '18px 20px',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 10 }}>
        <span style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 22,
          height: 22,
          borderRadius: '50%',
          background: style.border,
          color: '#FAF8F4',
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 11,
          fontWeight: 700,
          flexShrink: 0,
          marginTop: 1,
        }}>
          {style.icon}
        </span>
        <h4 style={{
          fontFamily: "'Newsreader', Georgia, serif",
          fontSize: 16,
          fontWeight: 500,
          color: '#1A1715',
          margin: 0,
          lineHeight: 1.4,
        }}>
          {spot.title}
        </h4>
      </div>

      {/* Body */}
      <p style={{
        fontFamily: "'Inter', system-ui, sans-serif",
        fontSize: 13,
        color: '#6B6560',
        lineHeight: 1.65,
        margin: '0 0 12px 34px',
      }}>
        {spot.body}
      </p>

      {/* Evidence chips */}
      {spot.evidence.length > 0 && (
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 6,
          marginLeft: 34,
        }}>
          {spot.evidence.map((e, i) => (
            <EvidenceChip key={i} label={e.label} value={e.value} />
          ))}
        </div>
      )}
    </div>
  )
}
