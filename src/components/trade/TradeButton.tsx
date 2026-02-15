'use client'

import { Plus } from 'lucide-react'

interface TradeButtonProps {
  onClick: () => void
}

export default function TradeButton({ onClick }: TradeButtonProps) {
  return (
    <button
      onClick={onClick}
      className="fixed bottom-6 right-6 z-30 w-14 h-14 rounded-full bg-teal flex items-center justify-center shadow-[0_4px_20px_rgba(0,191,166,0.3)] hover:scale-105 transition-transform md:bottom-6 md:right-6 bottom-20 right-4"
      aria-label="New Trade"
    >
      <Plus className="w-6 h-6 text-bg" />
    </button>
  )
}
