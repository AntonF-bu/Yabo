'use client'

import { M } from '@/lib/profile/meridian'

interface EvidenceChipProps {
  label: string
  value: string
}

export default function EvidenceChip({ label, value }: EvidenceChipProps) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '5px 10px',
        background: M.surface,
        border: `1px solid ${M.border}`,
        borderRadius: 6,
        fontFamily: M.mono,
        fontSize: 11,
        lineHeight: 1.4,
      }}
    >
      <span style={{ color: M.inkTertiary }}>{label}</span>
      <span style={{ color: M.ink, fontWeight: 500 }}>{value}</span>
    </span>
  )
}
