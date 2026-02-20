'use client'

import { truncateSentences } from '@/lib/profile/formatters'

interface NarrativeBlockProps {
  deepDive: string | null
  holdingsContextIncluded?: boolean
}

export default function NarrativeBlock({ deepDive, holdingsContextIncluded }: NarrativeBlockProps) {
  if (!deepDive) return null

  const truncated = truncateSentences(deepDive, 3)

  return (
    <section style={{
      background: '#1A1715',
      borderRadius: 14,
      padding: '32px 28px',
      margin: '32px 0',
    }}>
      <p style={{
        fontFamily: "'Newsreader', Georgia, serif",
        fontSize: 18,
        fontWeight: 400,
        fontStyle: 'italic',
        color: '#FAF8F4',
        lineHeight: 1.8,
        margin: 0,
        opacity: 0.95,
      }}>
        {truncated}
      </p>
      {holdingsContextIncluded && (
        <p style={{
          fontFamily: "'Inter', system-ui, sans-serif",
          fontSize: 12,
          color: '#8A8580',
          marginTop: 16,
          marginBottom: 0,
        }}>
          Analysis includes portfolio holdings context.
        </p>
      )}
    </section>
  )
}
