'use client'

import { truncateSentences } from '@/lib/profile/formatters'
import { M } from '@/lib/profile/meridian'

interface NarrativeBlockProps {
  deepDive: string | null
  holdingsContextIncluded?: boolean
}

export default function NarrativeBlock({ deepDive, holdingsContextIncluded }: NarrativeBlockProps) {
  if (!deepDive) return null

  const truncated = truncateSentences(deepDive, 3)

  return (
    <section style={{
      padding: '48px 0',
      borderBottom: `1px solid ${M.border}`,
    }}>
      <div style={{
        fontFamily: M.mono,
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: '0.15em',
        textTransform: 'uppercase' as const,
        color: M.gold,
        marginBottom: 16,
      }}>
        What the data says about you
      </div>
      <p style={{
        fontFamily: M.serif,
        fontSize: 20,
        fontWeight: 400,
        color: M.ink,
        lineHeight: 1.7,
        maxWidth: 680,
        margin: 0,
      }}>
        {truncated}
      </p>
      {holdingsContextIncluded && (
        <p style={{
          fontFamily: M.sans,
          fontSize: 12,
          color: M.inkTertiary,
          marginTop: 16,
          marginBottom: 0,
        }}>
          Analysis includes portfolio holdings context.
        </p>
      )}
    </section>
  )
}
