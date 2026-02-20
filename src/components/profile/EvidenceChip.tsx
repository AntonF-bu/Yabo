'use client'

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
        padding: '4px 10px',
        background: '#F5F2EC',
        borderRadius: 6,
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: 12,
        lineHeight: 1.4,
      }}
    >
      <span style={{ color: '#8A8580' }}>{label}</span>
      <span style={{ color: '#1A1715', fontWeight: 500 }}>{value}</span>
    </span>
  )
}
