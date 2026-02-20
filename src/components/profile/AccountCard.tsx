'use client'

import type { AccountPurpose } from '@/lib/profile/types'
import { M } from '@/lib/profile/meridian'

interface AccountCardProps {
  account: AccountPurpose
}

export default function AccountCard({ account }: AccountCardProps) {
  return (
    <div style={{
      background: M.white,
      border: `1px solid ${M.border}`,
      borderRadius: 10,
      padding: '16px 18px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div>
          <div style={{
            fontFamily: M.mono,
            fontSize: 12,
            fontWeight: 500,
            color: M.ink,
          }}>
            {account.account_id}
          </div>
          <div style={{
            fontFamily: M.mono,
            fontSize: 10,
            color: M.inkGhost,
            textTransform: 'uppercase' as const,
            letterSpacing: 1,
            marginTop: 2,
          }}>
            {account.account_type}
          </div>
        </div>
        <span style={{
          fontFamily: M.mono,
          fontSize: 14,
          fontWeight: 600,
          color: M.gold,
        }}>
          {account.estimated_value}
        </span>
      </div>
      <div style={{
        fontFamily: M.sans,
        fontSize: 12,
        fontWeight: 500,
        color: M.ink,
        marginBottom: 4,
      }}>
        {account.purpose}
      </div>
      <p style={{
        fontFamily: M.sans,
        fontSize: 12,
        color: M.inkTertiary,
        lineHeight: 1.5,
        margin: 0,
      }}>
        {account.strategy}
      </p>
    </div>
  )
}
