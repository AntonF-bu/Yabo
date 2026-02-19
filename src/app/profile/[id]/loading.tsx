export default function ProfileLoading() {
  return (
    <main style={{
      minHeight: '100vh', background: '#F5F3EF',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24,
    }}>
      <div style={{ textAlign: 'center', maxWidth: 420 }}>
        <div style={{ marginBottom: 24 }}>
          <svg
            width="32" height="32" viewBox="0 0 24 24"
            fill="none" stroke="#B8860B" strokeWidth="2"
            style={{ animation: 'spin 1s linear infinite' }}
          >
            <path d="M21 12a9 9 0 1 1-6.219-8.56" />
          </svg>
        </div>
        <h1 style={{
          fontFamily: "'Newsreader', Georgia, serif", fontSize: 24,
          fontWeight: 400, color: '#1A1715', marginBottom: 8,
        }}>
          Loading your Trading DNA...
        </h1>
        <p style={{
          fontFamily: "'Inter', system-ui, sans-serif", fontSize: 14,
          color: '#8A8580',
        }}>
          Preparing your behavioral profile.
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
