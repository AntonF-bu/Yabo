'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { M } from '@/lib/profile/meridian'

export default function ProcessingScreen({ profileId }: { profileId: string }) {
  const router = useRouter()

  // Auto-refresh every 10 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      router.refresh()
    }, 10_000)
    return () => clearInterval(interval)
  }, [router])

  return (
    <main
      style={{
        minHeight: '100vh',
        background: M.surface,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
      }}
    >
      <div style={{ textAlign: 'center', maxWidth: 420 }}>
        {/* Spinner */}
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: '50%',
            backgroundColor: 'rgba(154, 123, 91, 0.1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 24px',
          }}
        >
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke={M.gold}
            strokeWidth="2"
            style={{ animation: 'spin 1.5s linear infinite' }}
          >
            <path d="M21 12a9 9 0 1 1-6.219-8.56" />
          </svg>
        </div>

        <h1
          style={{
            fontFamily: M.serif,
            fontSize: 28,
            fontWeight: 400,
            color: M.ink,
            marginBottom: 12,
          }}
        >
          Analyzing your data
        </h1>

        <p
          style={{
            fontFamily: M.sans,
            fontSize: 15,
            color: M.inkTertiary,
            lineHeight: 1.6,
            marginBottom: 8,
          }}
        >
          We&apos;re processing your brokerage data and building your
          Trading DNA profile. This usually takes 1-2 minutes.
        </p>

        <p
          style={{
            fontFamily: M.sans,
            fontSize: 13,
            color: M.inkGhost,
          }}
        >
          This page refreshes automatically.
        </p>

        <p
          style={{
            fontFamily: M.mono,
            fontSize: 12,
            color: '#C5C0B8',
            marginTop: 24,
          }}
        >
          Profile: {profileId}
        </p>
      </div>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </main>
  )
}
