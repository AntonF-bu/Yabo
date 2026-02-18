import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Yabo - Discover Your Trading DNA',
  description: 'Upload your trading history and get your personalized behavioral profile.',
}

export default function IntakeLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen" style={{ backgroundColor: '#FAF7F2' }}>
      {children}
    </div>
  )
}
