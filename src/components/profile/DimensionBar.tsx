'use client'

import { useState } from 'react'
import type { DimensionData } from '@/lib/profile/types'

interface DimensionBarProps {
  dimKey: string
  data: DimensionData
  left: string
  right: string
}

function getScoreColor(score: number): string {
  if (score < 40) return '#A84B3F'
  if (score > 70) return '#9A7B5B'
  return '#1A1715'
}

export default function DimensionBar({ data, left, right }: DimensionBarProps) {
  const [expanded, setExpanded] = useState(false)
  const color = getScoreColor(data.score)

  return (
    <div style={{ marginBottom: 2 }}>
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          width: '100%',
          background: 'none',
          border: 'none',
          padding: '10px 0',
          cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        {/* Label row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <span style={{
            fontFamily: "'Inter', system-ui, sans-serif",
            fontSize: 13,
            fontWeight: 500,
            color: '#1A1715',
          }}>
            {data.label}
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              fontFamily: "'IBM Plex Mono', monospace",
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
              <path d="M2 4 L6 8 L10 4" fill="none" stroke="#A09A94" strokeWidth={1.5} strokeLinecap="round" />
            </svg>
          </div>
        </div>

        {/* Spectrum bar */}
        <div style={{ position: 'relative' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 10,
              color: '#A09A94',
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
            }}>{left}</span>
            <span style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 10,
              color: '#A09A94',
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
            }}>{right}</span>
          </div>
          <div style={{
            position: 'relative',
            height: 6,
            background: '#EEEAE3',
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
                border: '3px solid white',
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
            borderTop: '1px solid #EEEAE3',
          }}>
            <ul style={{
              margin: 0,
              padding: '0 0 0 16px',
              listStyle: 'none',
            }}>
              {data.evidence.map((e, i) => (
                <li key={i} style={{
                  fontFamily: "'Inter', system-ui, sans-serif",
                  fontSize: 12,
                  color: '#6B6560',
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
