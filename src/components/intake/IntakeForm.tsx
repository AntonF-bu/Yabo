'use client'

import { useState, useCallback } from 'react'
import FileUploadZone from './FileUploadZone'
import { submitIntake } from '@/lib/intake'

const BROKERAGES = [
  'Wells Fargo',
  'Schwab',
  'Fidelity',
  'Robinhood',
  'Interactive Brokers',
  'E-Trade',
  'TD Ameritrade',
  'Vanguard',
  'Merrill Lynch',
  'Morgan Stanley',
  'JP Morgan',
  'UBS',
  'Trading 212',
  'Webull',
  'Other',
]

interface IntakeFormProps {
  defaultReferral: string
  onComplete: (name: string, email: string, profileId?: string) => void
}

// Shared styles
const labelStyle: React.CSSProperties = {
  display: 'block',
  fontFamily: "'Inter', system-ui, sans-serif",
  fontSize: '13px',
  color: '#6B6560',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  marginBottom: '8px',
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  border: '1px solid #E8E0D4',
  borderRadius: '8px',
  padding: '12px 16px',
  fontFamily: "'Inter', system-ui, sans-serif",
  fontSize: '15px',
  color: '#2C2C2C',
  backgroundColor: '#FFFFFF',
  outline: 'none',
  transition: 'border-color 0.2s, box-shadow 0.2s',
  boxSizing: 'border-box' as const,
}

export default function IntakeForm({ defaultReferral, onComplete }: IntakeFormProps) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [referredBy, setReferredBy] = useState(defaultReferral)
  const [brokerage, setBrokerage] = useState('')
  const [csvFiles, setCsvFiles] = useState<File[]>([])
  const [screenshots, setScreenshots] = useState<File[]>([])
  const [portfolioFiles, setPortfolioFiles] = useState<File[]>([])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  const hasFile = csvFiles.length > 0 || screenshots.length > 0 || portfolioFiles.length > 0
  const canSubmit = name.trim() && email.trim() && hasFile && !isSubmitting

  const handleFocus = useCallback((e: React.FocusEvent<HTMLInputElement | HTMLSelectElement>) => {
    e.target.style.borderColor = '#B8860B'
    e.target.style.boxShadow = '0 0 0 3px rgba(184, 134, 11, 0.1)'
  }, [])

  const handleBlur = useCallback((e: React.FocusEvent<HTMLInputElement | HTMLSelectElement>) => {
    e.target.style.borderColor = '#E8E0D4'
    e.target.style.boxShadow = 'none'
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!name.trim() || !email.trim()) {
      setError('Please enter your name and email.')
      return
    }
    if (!hasFile) {
      setError('Please upload at least one CSV or screenshot.')
      return
    }

    setIsSubmitting(true)

    const result = await submitIntake(
      { name: name.trim(), email: email.trim(), phone: phone.trim(), brokerage, referredBy: referredBy.trim() },
      csvFiles[0] || null,
      screenshots,
      portfolioFiles[0] || null
    )

    if (result.success) {
      onComplete(name.trim(), email.trim(), result.traderId)
    } else {
      setError(result.error || 'Upload failed. Please try again.')
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        {/* Name */}
        <div>
          <label style={labelStyle}>Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Full name"
            style={inputStyle}
            onFocus={handleFocus}
            onBlur={handleBlur}
          />
        </div>

        {/* Email */}
        <div>
          <label style={labelStyle}>Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            style={inputStyle}
            onFocus={handleFocus}
            onBlur={handleBlur}
          />
        </div>

        {/* Phone */}
        <div>
          <label style={labelStyle}>Phone (optional)</label>
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="(555) 123-4567"
            style={inputStyle}
            onFocus={handleFocus}
            onBlur={handleBlur}
          />
        </div>

        {/* Referred By */}
        <div>
          <label style={labelStyle}>Referred by</label>
          <input
            type="text"
            value={referredBy}
            onChange={(e) => setReferredBy(e.target.value)}
            placeholder="Who sent you?"
            style={inputStyle}
            onFocus={handleFocus}
            onBlur={handleBlur}
          />
        </div>

        {/* Brokerage */}
        <div>
          <label style={labelStyle}>Brokerage</label>
          <select
            value={brokerage}
            onChange={(e) => setBrokerage(e.target.value)}
            onFocus={handleFocus as any}
            onBlur={handleBlur as any}
            style={{
              ...inputStyle,
              appearance: 'none',
              backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236B6560' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E")`,
              backgroundRepeat: 'no-repeat',
              backgroundPosition: 'right 16px center',
              paddingRight: '40px',
              color: brokerage ? '#2C2C2C' : '#A09A94',
            }}
          >
            <option value="" disabled>
              Select your brokerage
            </option>
            {BROKERAGES.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
        </div>

        {/* Upload section heading */}
        <div
          style={{
            fontFamily: "'Newsreader', Georgia, serif",
            fontSize: '20px',
            color: '#2C2C2C',
            marginTop: '0.5rem',
          }}
        >
          Upload Trading Data
        </div>

        {/* CSV Upload */}
        <FileUploadZone
          accept=".csv"
          multiple={false}
          label="Trade History (CSV)"
          hint="Accepted: .csv files from any brokerage"
          files={csvFiles}
          onFilesChange={setCsvFiles}
        />

        {/* Screenshot Upload */}
        <FileUploadZone
          accept=".jpg,.jpeg,.png"
          multiple={true}
          label="Screenshots (optional)"
          hint="Accepted: .jpg, .png — portfolio screenshots, trade confirmations"
          files={screenshots}
          onFilesChange={setScreenshots}
          showThumbnails={true}
        />

        {/* Portfolio upload section */}
        <div
          style={{
            fontFamily: "'Newsreader', Georgia, serif",
            fontSize: '20px',
            color: '#2C2C2C',
            marginTop: '0.5rem',
          }}
        >
          Upload Activity Data
        </div>
        <p
          style={{
            fontFamily: "'Inter', system-ui, sans-serif",
            fontSize: '14px',
            color: '#6B6560',
            lineHeight: 1.5,
            margin: '-0.5rem 0 0',
          }}
        >
          Upload your brokerage activity export to unlock portfolio analysis,
          concentration risk, and tax insights.
        </p>
        <FileUploadZone
          accept=".csv"
          multiple={false}
          label="Activity Export (CSV)"
          hint="Accepted: .csv activity/transaction exports from your brokerage"
          files={portfolioFiles}
          onFilesChange={setPortfolioFiles}
        />

        {/* Error message */}
        {error && (
          <div
            style={{
              fontFamily: "'Inter', system-ui, sans-serif",
              fontSize: '14px',
              color: '#C45A4A',
              textAlign: 'center',
            }}
          >
            {error}
          </div>
        )}

        {/* Submit button */}
        <button
          type="submit"
          disabled={!canSubmit}
          style={{
            width: '100%',
            padding: '14px 0',
            backgroundColor: canSubmit ? '#B8860B' : '#D4C9B5',
            color: '#FFFFFF',
            fontFamily: "'Inter', system-ui, sans-serif",
            fontSize: '15px',
            fontWeight: 600,
            border: 'none',
            borderRadius: '8px',
            cursor: canSubmit ? 'pointer' : 'not-allowed',
            transition: 'background-color 0.2s',
            marginTop: '0.5rem',
          }}
          onMouseEnter={(e) => {
            if (canSubmit) e.currentTarget.style.backgroundColor = '#9A7209'
          }}
          onMouseLeave={(e) => {
            if (canSubmit) e.currentTarget.style.backgroundColor = '#B8860B'
          }}
        >
          {isSubmitting ? (
            <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                style={{ animation: 'spin 1s linear infinite' }}
              >
                <path d="M21 12a9 9 0 1 1-6.219-8.56" />
              </svg>
              Submitting...
            </span>
          ) : (
            'Submit'
          )}
        </button>
      </div>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </form>
  )
}
