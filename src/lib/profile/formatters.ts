/* ------------------------------------------------------------------ */
/*  Dollar, percentage, and score formatting utilities                  */
/* ------------------------------------------------------------------ */

export function formatDollars(value: number | null | undefined): string {
  if (value == null) return '--'
  const abs = Math.abs(value)
  const sign = value < 0 ? '-' : ''
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(0)}K`
  return `${sign}$${abs.toFixed(0)}`
}

export function formatPct(value: number | null | undefined, decimals = 1): string {
  if (value == null) return '--'
  return `${(value * 100).toFixed(decimals)}%`
}

export function formatPctRaw(value: number | null | undefined, decimals = 1): string {
  if (value == null) return '--'
  return `${value.toFixed(decimals)}%`
}

export function formatScore(value: number | null | undefined): string {
  if (value == null) return '--'
  return `${Math.round(value)}`
}

export function formatMultiplier(value: number | null | undefined): string {
  if (value == null) return '--'
  return `${value.toFixed(2)}x`
}

export function truncateSentences(text: string, count: number): string {
  if (!text) return ''
  const sentences = text.match(/[^.!?]+[.!?]+/g) || [text]
  return sentences.slice(0, count).join(' ').trim()
}

export function computeObservationWindow(trades: { date: string }[] | null): string {
  if (!trades || trades.length === 0) return '--'
  const dates = trades.map(t => new Date(t.date).getTime()).filter(d => !isNaN(d))
  if (dates.length === 0) return '--'
  const min = new Date(Math.min(...dates))
  const max = new Date(Math.max(...dates))
  const fmt = (d: Date) => d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
  return `${fmt(min)} - ${fmt(max)}`
}
