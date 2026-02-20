'use client'

import type { DimensionData } from '@/lib/profile/types'
import { formatPct, feat } from '@/lib/profile/formatters'
import { M } from '@/lib/profile/meridian'

interface EntryInsightsProps {
  features: Record<string, unknown> | null
  dimensions: Record<string, DimensionData> | null
}

interface InsightCard {
  label: string
  value: string
  sub?: string
}

export default function EntryInsights({ features, dimensions }: EntryInsightsProps) {
  const cards: InsightCard[] = []

  const mvLabel = dimensions?.momentum_value?.label
  if (mvLabel) cards.push({ label: 'Entry Style', value: mvLabel })

  const breakout = feat(features, 'entry_breakout_score')
  if (breakout != null) cards.push({ label: 'Breakout Score', value: formatPct(breakout), sub: 'of entries on breakout days' })

  const dipBuyer = feat(features, 'entry_dip_buyer_score')
  if (dipBuyer != null) cards.push({ label: 'Dip Buyer Score', value: formatPct(dipBuyer), sub: 'of entries are dip buys' })

  const aboveMA = feat(features, 'entry_above_ma_score')
  if (aboveMA != null) cards.push({ label: 'Above MA Entries', value: formatPct(aboveMA), sub: 'entered above moving average' })

  const buildup = feat(features, 'entry_buildup_days')
  if (buildup != null) cards.push({ label: 'Avg Buildup', value: `${Math.round(buildup)} days`, sub: 'average buildup before entry' })

  const earnings = feat(features, 'entry_earnings_proximity')
  if (earnings != null) cards.push({ label: 'Earnings Proximity', value: formatPct(earnings), sub: 'of entries near earnings' })

  if (cards.length === 0) return null

  // Entry zone visualization
  const aboveScore = feat(features, 'entry_above_ma_score') ?? 0.5
  const belowScore = 1 - aboveScore
  const breakoutWidth = Math.max(aboveScore * 100, 10)
  const dipWidth = Math.max(belowScore * 100, 10)

  const evidence = dimensions?.momentum_value?.evidence || []

  return (
    <div>
      {/* Entry zone diagram */}
      <div style={{
        background: M.white,
        border: `1px solid ${M.border}`,
        borderRadius: M.card,
        padding: 20,
        marginBottom: 20,
      }}>
        <div style={{
          fontFamily: M.mono,
          fontSize: 10,
          color: M.inkGhost,
          textTransform: 'uppercase' as const,
          letterSpacing: 2,
          marginBottom: 14,
        }}>
          ENTRY ZONE
        </div>
        <svg viewBox="0 0 400 50" style={{ width: '100%', height: 50 }}>
          {/* Breakout zone */}
          <rect
            x={0}
            y={8}
            width={breakoutWidth * 4}
            height={34}
            rx={6}
            fill={aboveScore >= 0.5 ? M.gold : M.surfaceDeep}
            fillOpacity={aboveScore >= 0.5 ? 0.2 : 1}
            stroke={aboveScore >= 0.5 ? M.gold : M.border}
            strokeWidth={1}
          />
          <text
            x={breakoutWidth * 2}
            y={30}
            textAnchor="middle"
            style={{ fontFamily: M.mono, fontSize: 11, fill: aboveScore >= 0.5 ? M.gold : M.inkTertiary }}
          >
            Momentum {Math.round(aboveScore * 100)}%
          </text>

          {/* Dip buy zone */}
          <rect
            x={breakoutWidth * 4}
            y={8}
            width={dipWidth * 4}
            height={34}
            rx={6}
            fill={belowScore > 0.5 ? M.gold : M.surfaceDeep}
            fillOpacity={belowScore > 0.5 ? 0.2 : 1}
            stroke={belowScore > 0.5 ? M.gold : M.border}
            strokeWidth={1}
          />
          <text
            x={breakoutWidth * 4 + dipWidth * 2}
            y={30}
            textAnchor="middle"
            style={{ fontFamily: M.mono, fontSize: 11, fill: belowScore > 0.5 ? M.gold : M.inkTertiary }}
          >
            Dip Buy {Math.round(belowScore * 100)}%
          </text>
        </svg>
      </div>

      {/* Insight cards grid */}
      <div className="entry-grid" style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
        gap: 12,
      }}>
        {cards.map((card, i) => (
          <div key={i} style={{
            background: M.white,
            border: `1px solid ${M.border}`,
            borderRadius: 10,
            padding: '14px 16px',
          }}>
            <div style={{
              fontFamily: M.mono,
              fontSize: 10,
              color: M.inkGhost,
              textTransform: 'uppercase' as const,
              letterSpacing: 1,
              marginBottom: 6,
            }}>
              {card.label}
            </div>
            <div style={{
              fontFamily: M.mono,
              fontSize: 20,
              fontWeight: 600,
              color: M.ink,
              lineHeight: 1.2,
            }}>
              {card.value}
            </div>
            {card.sub && (
              <div style={{
                fontFamily: M.sans,
                fontSize: 11,
                color: M.inkTertiary,
                marginTop: 4,
              }}>
                {card.sub}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Evidence from dimension */}
      {evidence.length > 0 && (
        <div style={{
          marginTop: 16,
          padding: '12px 16px',
          background: M.surface,
          borderRadius: 8,
        }}>
          {evidence.slice(0, 2).map((e, i) => (
            <p key={i} style={{
              fontFamily: M.sans,
              fontSize: 12,
              color: M.inkSecondary,
              lineHeight: 1.6,
              margin: i > 0 ? '6px 0 0' : 0,
            }}>
              {e}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}
