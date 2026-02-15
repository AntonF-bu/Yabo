import { updateProfile, Profile } from './db'

export interface AnalysisResult {
  archetype: string
  archetypeDescription: string
  profileText: string
  keyStats: {
    winRate: string
    avgHoldDays: string
    bestSector: string
    worstTrait: string
    signaturePattern: string
  }
  traits: {
    entry_timing: number
    hold_discipline: number
    position_sizing: number
    conviction_accuracy: number
    risk_management: number
    sector_focus: number
    drawdown_resilience: number
    thesis_quality: number
  }
  recommendations: Array<{
    priority: 'high' | 'medium' | 'low'
    title: string
    body: string
    actionLabel: string
    impact: string
  }>
}

/**
 * Call the /api/analyze-trades endpoint and save results to profile.
 */
export async function analyzeAndSave(
  clerkId: string,
  trades: Array<{ date: string; ticker: string; action: string; quantity: number; price: number; total: number; sector?: string }>,
  positions: Array<{ ticker: string; shares: number; avgCost: number; currentPrice: number; sector: string }>,
  portfolioValue: number,
  cashBalance: number,
): Promise<AnalysisResult> {
  const res = await fetch('/api/analyze-trades', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ trades, positions, portfolioValue, cashBalance }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Analysis failed' }))
    throw new Error(err.error || 'Analysis failed')
  }

  const result: AnalysisResult = await res.json()

  // Save to profile
  const profileUpdate: Partial<Profile> = {
    archetype: result.archetype,
    trait_entry_timing: result.traits.entry_timing,
    trait_hold_discipline: result.traits.hold_discipline,
    trait_position_sizing: result.traits.position_sizing,
    trait_conviction_accuracy: result.traits.conviction_accuracy,
    trait_risk_management: result.traits.risk_management,
    trait_sector_focus: result.traits.sector_focus,
    trait_drawdown_resilience: result.traits.drawdown_resilience,
    trait_thesis_quality: result.traits.thesis_quality,
    ai_profile_text: result.profileText,
    ai_archetype_description: result.archetypeDescription,
    ai_key_stats: result.keyStats as unknown as Record<string, unknown>,
    ai_recommendations: result.recommendations as unknown as Record<string, unknown>[],
    ai_analyzed_at: new Date().toISOString(),
  }

  await updateProfile(clerkId, profileUpdate)
  return result
}
