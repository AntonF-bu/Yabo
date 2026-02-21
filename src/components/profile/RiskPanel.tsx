'use client'

import { formatDollars, formatMultiplier, formatPct, feat } from '@/lib/profile/formatters'
import type { RiskItem } from '@/lib/profile/types'
import { M } from '@/lib/profile/meridian'

interface RiskPanelProps {
  holdingsFeatures: Record<string, unknown> | null
  portfolioNarrative: Record<string, unknown> | null
}

export default function RiskPanel({ holdingsFeatures, portfolioNarrative }: RiskPanelProps) {
  const stressTest = feat(holdingsFeatures, 'h_stress_test_20pct')
  const totalValue = feat(holdingsFeatures, 'h_total_value')
  const maxSingleLoss = feat(holdingsFeatures, 'h_max_single_position_loss')
  const leverage = feat(holdingsFeatures, 'h_options_leverage_ratio')
  const correlation = feat(holdingsFeatures, 'h_correlation_estimate')
  const hedgingScore = feat(holdingsFeatures, 'h_hedging_score')

  // Price source metadata
  const livePrices = feat(holdingsFeatures, '_meta_live_price_count')
  const storedPrices = feat(holdingsFeatures, '_meta_stored_price_count')
  const hasLivePricing = livePrices != null && livePrices > 0

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
          background: M.white,
          border: `1px solid ${M.border}`,
          borderRadius: M.card,
          padding: 20,
          marginBottom: 20,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <div style={{
              fontFamily: M.mono,
              fontSize: 10,
              color: M.inkGhost,
              textTransform: 'uppercase' as const,
              letterSpacing: 2,
            }}>
              STRESS TEST: 20% MARKET DECLINE
            </div>
            {hasLivePricing && (
              <div style={{
                fontFamily: M.mono,
                fontSize: 9,
                color: M.profit,
                background: `${M.profit}10`,
                padding: '2px 8px',
                borderRadius: 3,
                letterSpacing: 0.5,
              }}>
                LIVE PRICING
              </div>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 12 }}>
            <span style={{
              fontFamily: M.mono,
              fontSize: 28,
              fontWeight: 600,
              color: M.loss,
            }}>
              {formatDollars(stressTest)}
            </span>
            <span style={{
              fontFamily: M.sans,
              fontSize: 13,
              color: M.inkTertiary,
            }}>
              estimated loss
            </span>
          </div>

          {/* Bar visualization */}
          <div style={{ position: 'relative', height: 28, background: M.surfaceDeep, borderRadius: 6, overflow: 'hidden' }}>
            <div style={{
              position: 'absolute',
              left: 0,
              top: 0,
              height: '100%',
              width: `${stressPct ?? 20}%`,
              background: `linear-gradient(90deg, ${M.loss}, #C45A4A)`,
              borderRadius: 6,
              transition: 'width 0.8s ease',
            }} />
            <div style={{
              position: 'absolute',
              left: 8,
              top: '50%',
              transform: 'translateY(-50%)',
              fontFamily: M.mono,
              fontSize: 11,
              fontWeight: 600,
              color: M.white,
            }}>
              {stressPct != null ? `${stressPct.toFixed(1)}%` : ''}
            </div>
          </div>

          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginTop: 6,
            fontFamily: M.mono,
            fontSize: 10,
            color: M.inkGhost,
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
          <div style={{ background: M.surface, borderRadius: 8, padding: '12px 14px', textAlign: 'center' }}>
            <div style={{ fontFamily: M.mono, fontSize: 10, color: M.inkGhost, textTransform: 'uppercase' as const, letterSpacing: 1, marginBottom: 4 }}>
              Stress Loss
            </div>
            <div style={{ fontFamily: M.mono, fontSize: 16, fontWeight: 600, color: M.loss }}>
              {formatDollars(stressTest)}
            </div>
          </div>
        )}
        {maxSingleLoss != null && (
          <div style={{ background: M.surface, borderRadius: 8, padding: '12px 14px', textAlign: 'center' }}>
            <div style={{ fontFamily: M.mono, fontSize: 10, color: M.inkGhost, textTransform: 'uppercase' as const, letterSpacing: 1, marginBottom: 4 }}>
              Max Single Loss
            </div>
            <div style={{ fontFamily: M.mono, fontSize: 16, fontWeight: 600, color: M.loss }}>
              {formatDollars(maxSingleLoss)}
            </div>
          </div>
        )}
        {leverage != null && (
          <div style={{ background: M.surface, borderRadius: 8, padding: '12px 14px', textAlign: 'center' }}>
            <div style={{ fontFamily: M.mono, fontSize: 10, color: M.inkGhost, textTransform: 'uppercase' as const, letterSpacing: 1, marginBottom: 4 }}>
              Options Leverage
            </div>
            <div style={{ fontFamily: M.mono, fontSize: 16, fontWeight: 600, color: M.warning }}>
              {formatMultiplier(leverage)}
            </div>
          </div>
        )}
        {correlation != null && (
          <div style={{ background: M.surface, borderRadius: 8, padding: '12px 14px', textAlign: 'center' }}>
            <div style={{ fontFamily: M.mono, fontSize: 10, color: M.inkGhost, textTransform: 'uppercase' as const, letterSpacing: 1, marginBottom: 4 }}>
              Correlation
            </div>
            <div style={{ fontFamily: M.mono, fontSize: 16, fontWeight: 600, color: M.ink }}>
              {formatPct(correlation)}
            </div>
          </div>
        )}
        {hedgingScore != null && (
          <div style={{ background: M.surface, borderRadius: 8, padding: '12px 14px', textAlign: 'center' }}>
            <div style={{ fontFamily: M.mono, fontSize: 10, color: M.inkGhost, textTransform: 'uppercase' as const, letterSpacing: 1, marginBottom: 4 }}>
              Hedging Score
            </div>
            <div style={{ fontFamily: M.mono, fontSize: 16, fontWeight: 600, color: hedgingScore === 0 ? M.loss : M.profit }}>
              {Math.round(hedgingScore)}
            </div>
          </div>
        )}
      </div>

      {/* Risk items from narrative */}
      {riskItems.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {riskItems.map((r, i) => {
            const color = M.severityColor(r.severity)
            return (
              <div key={i} style={{
                background: M.white,
                border: `1px solid ${M.border}`,
                borderLeft: `3px solid ${color}`,
                borderRadius: `0 10px 10px 0`,
                padding: '14px 18px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span style={{
                    fontFamily: M.mono,
                    fontSize: 9,
                    fontWeight: 600,
                    color,
                    textTransform: 'uppercase' as const,
                    letterSpacing: 1.5,
                    padding: '2px 6px',
                    background: `${color}10`,
                    borderRadius: 3,
                  }}>
                    {r.severity}
                  </span>
                  <h4 style={{
                    fontFamily: M.serif,
                    fontSize: 14,
                    fontWeight: 500,
                    color: M.ink,
                    margin: 0,
                  }}>
                    {r.risk}
                  </h4>
                </div>
                <p style={{
                  fontFamily: M.sans,
                  fontSize: 12,
                  color: M.inkSecondary,
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
