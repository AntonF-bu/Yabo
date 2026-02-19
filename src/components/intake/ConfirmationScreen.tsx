'use client'

interface ConfirmationScreenProps {
  name: string
  email: string
  profileId?: string
}

export default function ConfirmationScreen({ name, email, profileId }: ConfirmationScreenProps) {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem',
      }}
    >
      <div style={{ maxWidth: '540px', width: '100%', textAlign: 'center' }}>
        {/* Logo */}
        <div
          style={{
            fontFamily: "'Newsreader', Georgia, serif",
            fontSize: '24px',
            fontWeight: 500,
            color: '#2C2C2C',
            letterSpacing: '0.02em',
            marginBottom: '3rem',
          }}
        >
          Yabo
        </div>

        {/* Checkmark */}
        <div
          style={{
            width: '56px',
            height: '56px',
            borderRadius: '50%',
            backgroundColor: 'rgba(184, 134, 11, 0.1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 2rem',
          }}
        >
          <svg
            width="28"
            height="28"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#B8860B"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="20 6 9 17 4 12" />
          </svg>
        </div>

        {/* Thank you message */}
        <h1
          style={{
            fontFamily: "'Newsreader', Georgia, serif",
            fontSize: '28px',
            fontWeight: 400,
            color: '#2C2C2C',
            marginBottom: '1rem',
          }}
        >
          Thank you, {name}.
        </h1>

        <p
          style={{
            fontFamily: "'Inter', system-ui, sans-serif",
            fontSize: '16px',
            color: '#6B6560',
            lineHeight: 1.6,
            maxWidth: '400px',
            margin: '0 auto 3rem',
          }}
        >
          Your trading data has been received. Our system is analyzing your
          behavioral patterns and we&apos;ll share your personalized Trading DNA
          profile at {email} once it&apos;s ready.
        </p>

        {profileId && (
          <a
            href={`/profile/${profileId}`}
            style={{
              display: 'inline-block',
              padding: '12px 28px',
              backgroundColor: '#B8860B',
              color: '#FFFFFF',
              fontFamily: "'Inter', system-ui, sans-serif",
              fontSize: '15px',
              fontWeight: 600,
              border: 'none',
              borderRadius: '8px',
              textDecoration: 'none',
              transition: 'background-color 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#9A7209'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = '#B8860B'
            }}
          >
            View Your Profile
          </a>
        )}

      </div>
    </div>
  )
}
