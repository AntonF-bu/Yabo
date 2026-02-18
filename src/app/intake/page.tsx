'use client'

import { useState, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import IntakeForm from '@/components/intake/IntakeForm'
import ConfirmationScreen from '@/components/intake/ConfirmationScreen'

const REF_MAP: Record<string, string> = {
  daniel: 'Daniel Starr',
}

function IntakeContent() {
  const searchParams = useSearchParams()
  const refCode = searchParams.get('ref')
  const defaultReferral = (refCode && REF_MAP[refCode]) || ''

  const [submitted, setSubmitted] = useState(false)
  const [submittedName, setSubmittedName] = useState('')
  const [submittedEmail, setSubmittedEmail] = useState('')

  if (submitted) {
    return <ConfirmationScreen name={submittedName} email={submittedEmail} />
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        padding: '2rem',
      }}
    >
      <div style={{ maxWidth: '540px', width: '100%', paddingTop: '4rem', paddingBottom: '4rem' }}>
        {/* Logo */}
        <div
          style={{
            fontFamily: "'Newsreader', Georgia, serif",
            fontSize: '24px',
            fontWeight: 500,
            color: '#2C2C2C',
            letterSpacing: '0.02em',
            textAlign: 'center',
            marginBottom: '2.5rem',
          }}
        >
          Yabo
        </div>

        {/* Headline */}
        <h1
          style={{
            fontFamily: "'Newsreader', Georgia, serif",
            fontSize: '28px',
            fontWeight: 400,
            color: '#2C2C2C',
            textAlign: 'center',
            marginBottom: '0.75rem',
          }}
        >
          Discover Your Trading DNA
        </h1>

        {/* Subtext */}
        <p
          style={{
            fontFamily: "'Inter', system-ui, sans-serif",
            fontSize: '16px',
            color: '#6B6560',
            textAlign: 'center',
            maxWidth: '400px',
            margin: '0 auto 2.5rem',
            lineHeight: 1.5,
          }}
        >
          Upload your trading history and we&apos;ll build your personalized
          behavioral profile. We&apos;ll reach out when your analysis is ready.
        </p>

        {/* Form */}
        <IntakeForm
          defaultReferral={defaultReferral}
          onComplete={(name, email) => {
            setSubmittedName(name)
            setSubmittedEmail(email)
            setSubmitted(true)
          }}
        />
      </div>
    </div>
  )
}

export default function IntakePage() {
  return (
    <Suspense
      fallback={
        <div
          style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <div
            style={{
              fontFamily: "'Inter', system-ui, sans-serif",
              fontSize: '15px',
              color: '#6B6560',
            }}
          >
            Loading...
          </div>
        </div>
      }
    >
      <IntakeContent />
    </Suspense>
  )
}
