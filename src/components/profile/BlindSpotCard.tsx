'use client'

import { useState } from 'react'
import type { BlindSpot } from '@/lib/profile/types'
import { M } from '@/lib/profile/meridian'
import EvidenceChip from './EvidenceChip'

interface BlindSpotCardProps {
  spot: BlindSpot
  index?: number
}

const SEVERITY_ICONS: Record<BlindSpot['severity'], string> = {
  danger: '!!',
  warning: '!',
  info: 'i',
  opportunity: '+',
}

export default function BlindSpotCard({ spot, index = 0 }: BlindSpotCardProps) {
  const [hovered, setHovered] = useState(false)
  const color = M.severityColor(spot.severity)

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        position: 'relative',
        background: M.white,
        border: `1px solid ${M.border}`,
        borderRadius: M.card,
        padding: '22px 20px 18px',
        overflow: 'hidden',
        transform: hovered ? 'translateY(-2px)' : 'translateY(0)',
        boxShadow: hovered ? '0 8px 24px rgba(26,23,21,0.08)' : 'none',
        transition: 'transform 0.2s ease, box-shadow 0.2s ease',
        animation: 'blindSpotFadeIn 0.4s ease forwards',
        animationDelay: `${index * 0.1}s`,
        opacity: 0,
      }}
    >
      {/* Colored top border accent */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        height: 3,
        background: color,
      }} />

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 10 }}>
        <span style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 22,
          height: 22,
          borderRadius: '50%',
          background: color,
          color: M.bg,
          fontFamily: M.mono,
          fontSize: 11,
          fontWeight: 700,
          flexShrink: 0,
          marginTop: 1,
        }}>
          {SEVERITY_ICONS[spot.severity]}
        </span>
        <h4 style={{
          fontFamily: M.serif,
          fontSize: 18,
          fontWeight: 500,
          color: M.ink,
          margin: 0,
          lineHeight: 1.4,
        }}>
          {spot.title}
        </h4>
      </div>

      {/* Body */}
      <p style={{
        fontFamily: M.sans,
        fontSize: 13,
        color: M.inkSecondary,
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

      <style>{`
        @keyframes blindSpotFadeIn {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}
