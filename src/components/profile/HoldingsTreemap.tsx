'use client'

import type { HoldingRow } from '@/lib/profile/types'
import { formatDollars } from '@/lib/profile/formatters'

interface HoldingsTreemapProps {
  holdings: HoldingRow[] | null
}

interface TreemapItem {
  ticker: string
  value: number
  pct: number
  type: string
}

const TYPE_COLORS: Record<string, string> = {
  equity: '#9A7B5B',
  etf: '#7B8FA8',
  options: '#A0785A',
  muni_bond: '#6B8E6B',
  money_market: '#8A8580',
  transfer: '#A09A94',
}

function buildTreemapItems(holdings: HoldingRow[]): TreemapItem[] {
  const grouped: Record<string, { value: number; type: string }> = {}

  for (const h of holdings) {
    const ticker = h.ticker || h.description?.slice(0, 20) || 'Unknown'
    let value = h.market_value ?? 0
    // For munis without market_value, use quantity as face value
    if (value === 0 && h.instrument_type === 'muni_bond' && h.quantity) {
      value = h.quantity
    }
    if (value <= 0) continue

    if (!grouped[ticker]) {
      grouped[ticker] = { value: 0, type: h.instrument_type || 'equity' }
    }
    grouped[ticker].value += value
  }

  const entries = Object.entries(grouped)
    .map(([ticker, { value, type }]) => ({ ticker, value, type, pct: 0 }))
    .sort((a, b) => b.value - a.value)

  const total = entries.reduce((s, e) => s + e.value, 0)
  if (total > 0) {
    for (const e of entries) {
      e.pct = e.value / total
    }
  }

  return entries
}

function layoutTreemap(items: TreemapItem[], width: number, height: number) {
  if (items.length === 0) return []

  const total = items.reduce((s, i) => s + i.value, 0)
  const rects: { item: TreemapItem; x: number; y: number; w: number; h: number }[] = []

  let x = 0, y = 0, remainingW = width, remainingH = height
  let remaining = [...items]

  while (remaining.length > 0) {
    const isHorizontal = remainingW >= remainingH
    const mainDim = isHorizontal ? remainingW : remainingH
    const crossDim = isHorizontal ? remainingH : remainingW

    const remainingTotal = remaining.reduce((s, i) => s + i.value, 0)

    // Find optimal row
    let bestRow: TreemapItem[] = []
    let bestAspect = Infinity

    for (let count = 1; count <= remaining.length; count++) {
      const row = remaining.slice(0, count)
      const rowTotal = row.reduce((s, i) => s + i.value, 0)
      const rowMainLen = (rowTotal / remainingTotal) * mainDim

      let worstAspect = 0
      for (const item of row) {
        const crossLen = (item.value / rowTotal) * crossDim
        const aspect = rowMainLen > crossLen
          ? rowMainLen / crossLen
          : crossLen / rowMainLen
        worstAspect = Math.max(worstAspect, aspect)
      }

      if (worstAspect <= bestAspect) {
        bestAspect = worstAspect
        bestRow = row
      } else {
        break
      }
    }

    if (bestRow.length === 0) break

    const rowTotal = bestRow.reduce((s, i) => s + i.value, 0)
    const rowMainLen = (rowTotal / (remainingTotal || 1)) * mainDim

    let crossOffset = 0
    for (const item of bestRow) {
      const crossLen = (item.value / (rowTotal || 1)) * crossDim
      if (isHorizontal) {
        rects.push({ item, x, y: y + crossOffset, w: rowMainLen, h: crossLen })
      } else {
        rects.push({ item, x: x + crossOffset, y, w: crossLen, h: rowMainLen })
      }
      crossOffset += crossLen
    }

    if (isHorizontal) {
      x += rowMainLen
      remainingW -= rowMainLen
    } else {
      y += rowMainLen
      remainingH -= rowMainLen
    }

    remaining = remaining.slice(bestRow.length)
  }

  return rects
}

export default function HoldingsTreemap({ holdings }: HoldingsTreemapProps) {
  if (!holdings || holdings.length === 0) return null

  const items = buildTreemapItems(holdings)
  if (items.length === 0) return null

  const width = 600
  const height = 340
  const rects = layoutTreemap(items, width, height)

  return (
    <div style={{
      background: 'white',
      border: '1px solid #E8E4DE',
      borderRadius: 14,
      padding: 16,
      overflow: 'hidden',
    }}>
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 'auto' }}>
        {rects.map((r, i) => {
          const color = TYPE_COLORS[r.item.type] || '#9A7B5B'
          const showLabel = r.w > 40 && r.h > 30
          const showValue = r.w > 60 && r.h > 45
          return (
            <g key={i}>
              <rect
                x={r.x + 1}
                y={r.y + 1}
                width={Math.max(r.w - 2, 0)}
                height={Math.max(r.h - 2, 0)}
                rx={4}
                fill={color}
                fillOpacity={0.15 + r.item.pct * 0.4}
                stroke={color}
                strokeWidth={1}
                strokeOpacity={0.3}
              />
              {showLabel && (
                <text
                  x={r.x + r.w / 2}
                  y={r.y + r.h / 2 - (showValue ? 6 : 0)}
                  textAnchor="middle"
                  dominantBaseline="central"
                  style={{
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: r.w > 80 ? 12 : 10,
                    fontWeight: 600,
                    fill: '#1A1715',
                  }}
                >
                  {r.item.ticker}
                </text>
              )}
              {showValue && (
                <text
                  x={r.x + r.w / 2}
                  y={r.y + r.h / 2 + 10}
                  textAnchor="middle"
                  dominantBaseline="central"
                  style={{
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: 9,
                    fill: '#8A8580',
                  }}
                >
                  {formatDollars(r.item.value)} ({(r.item.pct * 100).toFixed(1)}%)
                </text>
              )}
            </g>
          )
        })}
      </svg>
    </div>
  )
}
