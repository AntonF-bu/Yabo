'use client'

import type { AccountPurpose } from '@/lib/profile/types'

interface AccountCardProps {
  account: AccountPurpose
}

export default function AccountCard({ account }: AccountCardProps) {
  return (
    <div style={{
      background: 'white',
      border: '1px solid #E8E4DE',
      borderRadius: 10,
      padding: '16px 18px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div>
          <div style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 12,
            fontWeight: 500,
            color: '#1A1715',
          }}>
            {account.account_id}
          </div>
          <div style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 10,
            color: '#A09A94',
            textTransform: 'uppercase',
            letterSpacing: 1,
            marginTop: 2,
          }}>
            {account.account_type}
          </div>
        </div>
        <span style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 14,
          fontWeight: 600,
          color: '#9A7B5B',
        }}>
          {account.estimated_value}
        </span>
      </div>
      <div style={{
        fontFamily: "'Inter', system-ui, sans-serif",
        fontSize: 12,
        fontWeight: 500,
        color: '#1A1715',
        marginBottom: 4,
      }}>
        {account.purpose}
      </div>
      <p style={{
        fontFamily: "'Inter', system-ui, sans-serif",
        fontSize: 12,
        color: '#8A8580',
        lineHeight: 1.5,
        margin: 0,
      }}>
        {account.strategy}
      </p>
    </div>
  )
}
