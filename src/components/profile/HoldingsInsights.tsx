'use client'

import { truncateSentences } from '@/lib/profile/formatters'
import type { AccountPurpose } from '@/lib/profile/types'
import { M } from '@/lib/profile/meridian'
import AccountCard from './AccountCard'

interface HoldingsInsightsProps {
  portfolioNarrative: Record<string, unknown> | null
}

interface InsightSection {
  tag: string
  headline: string
  body: string
}

function getStr(obj: unknown, key: string): string {
  if (!obj || typeof obj !== 'object') return ''
  const val = (obj as Record<string, unknown>)[key]
  return typeof val === 'string' ? val : ''
}

function getObj(obj: unknown, key: string): Record<string, unknown> | null {
  if (!obj || typeof obj !== 'object') return null
  const val = (obj as Record<string, unknown>)[key]
  if (val && typeof val === 'object' && !Array.isArray(val)) return val as Record<string, unknown>
  return null
}

export default function HoldingsInsights({ portfolioNarrative }: HoldingsInsightsProps) {
  if (!portfolioNarrative) return null

  const sections: InsightSection[] = []

  const concentration = getObj(portfolioNarrative, 'concentration_analysis')
  if (concentration) {
    const headline = getStr(concentration, 'headline')
    const narrative = getStr(concentration, 'narrative')
    if (headline || narrative) {
      sections.push({
        tag: 'CONCENTRATION',
        headline: headline || 'Concentration Analysis',
        body: truncateSentences(narrative, 2),
      })
    }
  }

  const income = getObj(portfolioNarrative, 'income_analysis')
  if (income) {
    const headline = getStr(income, 'headline')
    const narrative = getStr(income, 'narrative')
    if (headline || narrative) {
      sections.push({
        tag: 'INCOME',
        headline: headline || 'Income Analysis',
        body: truncateSentences(narrative, 2),
      })
    }
  }

  const options = getObj(portfolioNarrative, 'options_strategy')
  if (options) {
    const headline = getStr(options, 'headline')
    const narrative = getStr(options, 'narrative')
    if (headline || narrative) {
      sections.push({
        tag: 'OPTIONS',
        headline: headline || 'Options Strategy',
        body: truncateSentences(narrative, 2),
      })
    }
  }

  const tax = getObj(portfolioNarrative, 'tax_context')
  if (tax) {
    const narrative = getStr(tax, 'narrative')
    if (narrative) {
      sections.push({
        tag: 'TAX CONTEXT',
        headline: 'Tax Profile',
        body: truncateSentences(narrative, 2),
      })
    }
  }

  // Account purposes
  const structure = getObj(portfolioNarrative, 'portfolio_structure')
  const accountPurposes: AccountPurpose[] = []
  if (structure) {
    const purposes = (structure as Record<string, unknown>).account_purposes
    if (Array.isArray(purposes)) {
      for (const p of purposes) {
        if (p && typeof p === 'object') {
          const ap = p as Record<string, unknown>
          accountPurposes.push({
            account_id: String(ap.account_id || ''),
            account_type: String(ap.account_type || ''),
            purpose: String(ap.purpose || ''),
            strategy: String(ap.strategy || ''),
            estimated_value: String(ap.estimated_value || ''),
          })
        }
      }
    }
  }

  return (
    <div>
      {/* Insight cards */}
      {sections.length > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: 14,
          marginBottom: accountPurposes.length > 0 ? 24 : 0,
        }}>
          {sections.map((s, i) => (
            <div key={i} style={{
              background: M.white,
              border: `1px solid ${M.border}`,
              borderRadius: 10,
              padding: '16px 18px',
            }}>
              <div style={{
                fontFamily: M.mono,
                fontSize: 10,
                color: M.inkGhost,
                textTransform: 'uppercase' as const,
                letterSpacing: 2,
                marginBottom: 8,
              }}>
                {s.tag}
              </div>
              <h4 style={{
                fontFamily: M.serif,
                fontSize: 15,
                fontWeight: 500,
                color: M.ink,
                margin: '0 0 8px',
                lineHeight: 1.4,
              }}>
                {s.headline}
              </h4>
              <p style={{
                fontFamily: M.sans,
                fontSize: 13,
                color: M.inkSecondary,
                lineHeight: 1.6,
                margin: 0,
              }}>
                {s.body}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Account structure */}
      {accountPurposes.length > 0 && (
        <div>
          <div style={{
            fontFamily: M.mono,
            fontSize: 10,
            color: M.inkGhost,
            textTransform: 'uppercase' as const,
            letterSpacing: 2,
            marginBottom: 12,
          }}>
            ACCOUNT STRUCTURE
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
            gap: 12,
          }}>
            {accountPurposes.map((a, i) => (
              <AccountCard key={i} account={a} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
