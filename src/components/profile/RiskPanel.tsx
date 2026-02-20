'use client'

import { formatDollars, formatMultiplier, formatPct } from '@/lib/profile/formatters'
import type { RiskItem } from '@/lib/profile/types'

interface RiskPanelProps {
  holdingsFeatures: Record<string, unknown> | null
  portfolioNarrative: Record<string, unknown> | null
}

function feat(features: Record<string, unknown> | null, key: string): number | null {
  if (!features) return null
  const v = features[key]
  if (v == null || typeof v !== 'number') return null
  return v
}

const SEVERITY_COLORS: Record<string, string> = {
  high: '#A84B3F',
  medium: '#C4873B',
  moderate: '#C4873B',
  low: '#4A7C59',
}

export default function RiskPanel({ holdingsFeatures, portfolioNarrative }: RiskPanelProps) {
  const stressTest = feat(holdingsFeatures, 'h_stress_test_20pct')
  const totalValue = feat(holdingsFeatures, 'h_total_value')
  const maxSingleLoss = feat(holdingsFeatures, 'h_max_single_position_loss')
  const leverage = feat(holdingsFeatures, 'h_options_leverage_ratio')
  const correlation = feat(holdingsFeatures, 'h_correlation_estimate')
  const hedgingScore = feat(holdingsFeatures, 'h_hedging_score')

  // Risk items from portfolio narrative
  const riskItems: RiskItem[] = []
  if (portfolioNarrative) {
    const assessment = portfolioNarrative.risk_assessment
    if (assessment && typeof assessment === 'object') {
      const keyRisks = (assessment as Record<string, unknown>).key_risks
      if (Array.isArray(keyRisks)) {
        for (const r of keyRisks) {
          if (r && typeof r === 'object') {
            const ri = r as Record<string, unknown>
            riskItems.push({
              risk: String(ri.risk || ''),
              detail: String(ri.detail || ''),
              severity: String(ri.severity || 'medium'),
            })
          }
        }
      }
    }
  }

  const stressPct = stressTest != null && totalValue != null && totalValue > 0
    ? (stressTest / totalValue) * 100
    : null

  return (
    <div>
      {/* Stress test visualization */}
      {stressTest != null && totalValue != null && (
        <div style={{
          background: 'white',
          border: '1px solid #E8E4DE',
          borderRadius: 14,
          padding: 20,
          marginBottom: 20,
        }}>
          <div style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 10,
            color: '#A09A94',
            textTransform: 'uppercase',
            letterSpacing: 2,
            marginBottom: 14,
          }}>
            STRESS TEST: 20% MARKET DECLINE
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 12 }}>
            <span style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 28,
              fontWeight: 600,
              color: '#A84B3F',
            }}>
              {formatDollars(stressTest)}
            </span>
            <span style={{
              fontFamily: "'Inter', system-ui, sans-serif",
              fontSize: 13,
              color: '#8A8580',
            }}>
              estimated loss
            </span>
          </div>

          {/* Bar visualization */}
          <div style={{ position: 'relative', height: 28, background: '#EEEAE3', borderRadius: 6, overflow: 'hidden' }}>
            <div style={{
              position: 'absolute',
              left: 0,
              top: 0,
              height: '100%',
              width: `${stressPct ?? 20}%`,
              background: 'linear-gradient(90deg, #A84B3F, #C45A4A)',
              borderRadius: 6,
              transition: 'width 0.8s ease',
            }} />
            <div style={{
              position: 'absolute',
              left: 8,
              top: '50%',
              transform: 'translateY(-50%)',
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 11,
              fontWeight: 600,
              color: 'white',
            }}>
              {stressPct != null ? `${stressPct.toFixed(1)}%` : ''}
            </div>
          </div>

          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginTop: 6,
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 10,
            color: '#A09A94',
          }}>
            <span>$0</span>
            <span>{formatDollars(totalValue)}</span>
          </div>
        </div>
      )}

      {/* Key metrics grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
        gap: 10,
        marginBottom: riskItems.length > 0 ? 20 : 0,
      }}>
        {stressTest != null && (
          <div style={{ background: '#F5F2EC', borderRadius: 8, padding: '12px 14px', textAlign: 'center' }}>
            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, color: '#A09A94', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>
              Stress Loss
            </div>
            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 16, fontWeight: 600, color: '#A84B3F' }}>
              {formatDollars(stressTest)}
            </div>
          </div>
        )}
        {maxSingleLoss != null && (
          <div style={{ background: '#F5F2EC', borderRadius: 8, padding: '12px 14px', textAlign: 'center' }}>
            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, color: '#A09A94', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>
              Max Single Loss
            </div>
            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 16, fontWeight: 600, color: '#A84B3F' }}>
              {formatDollars(maxSingleLoss)}
            </div>
          </div>
        )}
        {leverage != null && (
          <div style={{ background: '#F5F2EC', borderRadius: 8, padding: '12px 14px', textAlign: 'center' }}>
            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, color: '#A09A94', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>
              Options Leverage
            </div>
            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 16, fontWeight: 600, color: '#C4873B' }}>
              {formatMultiplier(leverage)}
            </div>
          </div>
        )}
        {correlation != null && (
          <div style={{ background: '#F5F2EC', borderRadius: 8, padding: '12px 14px', textAlign: 'center' }}>
            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, color: '#A09A94', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>
              Correlation
            </div>
            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 16, fontWeight: 600, color: '#1A1715' }}>
              {formatPct(correlation)}
            </div>
          </div>
        )}
        {hedgingScore != null && (
          <div style={{ background: '#F5F2EC', borderRadius: 8, padding: '12px 14px', textAlign: 'center' }}>
            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, color: '#A09A94', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>
              Hedging Score
            </div>
            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 16, fontWeight: 600, color: hedgingScore === 0 ? '#A84B3F' : '#4A7C59' }}>
              {Math.round(hedgingScore)}
            </div>
          </div>
        )}
      </div>

      {/* Risk items from narrative */}
      {riskItems.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {riskItems.map((r, i) => {
            const color = SEVERITY_COLORS[r.severity] || '#C4873B'
            return (
              <div key={i} style={{
                background: 'white',
                border: '1px solid #E8E4DE',
                borderLeft: `3px solid ${color}`,
                borderRadius: '0 10px 10px 0',
                padding: '14px 18px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span style={{
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: 9,
                    fontWeight: 600,
                    color,
                    textTransform: 'uppercase',
                    letterSpacing: 1.5,
                    padding: '2px 6px',
                    background: `${color}10`,
                    borderRadius: 3,
                  }}>
                    {r.severity}
                  </span>
                  <h4 style={{
                    fontFamily: "'Newsreader', Georgia, serif",
                    fontSize: 14,
                    fontWeight: 500,
                    color: '#1A1715',
                    margin: 0,
                  }}>
                    {r.risk}
                  </h4>
                </div>
                <p style={{
                  fontFamily: "'Inter', system-ui, sans-serif",
                  fontSize: 12,
                  color: '#6B6560',
                  lineHeight: 1.6,
                  margin: 0,
                }}>
                  {r.detail}
                </p>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
