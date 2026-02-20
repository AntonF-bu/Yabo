'use client'

import { useState } from 'react'
import type { DimensionData } from '@/lib/profile/types'
import { M } from '@/lib/profile/meridian'

interface DimensionBarProps {
  dimKey: string
  data: DimensionData
  left: string
  right: string
}

function getScoreColor(score: number): string {
  if (score < 40) return M.loss
  if (score > 70) return M.gold
  return M.ink
}

export default function DimensionBar({ data, left, right }: DimensionBarProps) {
  const [expanded, setExpanded] = useState(false)
  const [hovered, setHovered] = useState(false)
  const color = getScoreColor(data.score)

  return (
    <div style={{ marginBottom: 2 }}>
      <button
        onClick={() => setExpanded(!expanded)}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{
          width: hovered ? 'calc(100% + 24px)' : '100%',
          background: hovered ? M.goldLight : 'none',
          border: 'none',
          borderBottom: `1px solid ${M.border}`,
          padding: '10px 12px',
          margin: hovered ? '0 -12px' : 0,
          borderRadius: hovered ? 8 : 0,
          cursor: 'pointer',
          textAlign: 'left' as const,
          transition: 'background 0.15s ease',
        }}
      >
        {/* Label row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <span style={{
            fontFamily: M.sans,
            fontSize: 13,
            fontWeight: 500,
            color: M.ink,
          }}>
            {data.label}
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              fontFamily: M.mono,
              fontSize: 13,
              fontWeight: 600,
              color,
            }}>
              {Math.round(data.score)}
            </span>
            <svg
              width={12} height={12} viewBox="0 0 12 12"
              style={{
                transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: 'transform 0.2s ease',
              }}
            >
              <path d="M2 4 L6 8 L10 4" fill="none" stroke={M.inkGhost} strokeWidth={1.5} strokeLinecap="round" />
            </svg>
          </div>
        </div>

        {/* Spectrum bar */}
        <div style={{ position: 'relative' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{
              fontFamily: M.mono,
              fontSize: 10,
              color: M.inkGhost,
              textTransform: 'uppercase' as const,
              letterSpacing: '0.5px',
            }}>{left}</span>
            <span style={{
              fontFamily: M.mono,
              fontSize: 10,
              color: M.inkGhost,
              textTransform: 'uppercase' as const,
              letterSpacing: '0.5px',
            }}>{right}</span>
          </div>
          <div style={{
            position: 'relative',
            height: 6,
            background: M.surfaceDeep,
            borderRadius: 3,
          }}>
            <div
              style={{
                position: 'absolute',
                top: '50%',
                left: `${data.score}%`,
                transform: 'translate(-50%, -50%)',
                width: 14,
                height: 14,
                borderRadius: '50%',
                background: color,
                border: `3px solid ${M.white}`,
                boxShadow: '0 1px 4px rgba(0,0,0,0.15)',
              }}
            />
          </div>
        </div>
      </button>

      {/* Evidence (expanded) */}
      <div style={{
        maxHeight: expanded ? 300 : 0,
        overflow: 'hidden',
        transition: 'max-height 0.35s ease',
      }}>
        {data.evidence.length > 0 && (
          <div style={{
            padding: '8px 0 12px',
            borderTop: `1px solid ${M.surfaceDeep}`,
          }}>
            <ul style={{
              margin: 0,
              padding: '0 0 0 16px',
              listStyle: 'none',
            }}>
              {data.evidence.map((e, i) => (
                <li key={i} style={{
                  fontFamily: M.sans,
                  fontSize: 12,
                  color: M.inkSecondary,
                  lineHeight: 1.6,
                  marginBottom: 4,
                  position: 'relative',
                  paddingLeft: 12,
                }}>
                  <span style={{
                    position: 'absolute',
                    left: 0,
                    color: '#D5D0C8',
                  }}>-</span>
                  {e}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
