import { supabase } from './supabase'

// Type definitions
export interface Profile {
  id?: string
  clerk_id: string
  username?: string
  display_name?: string
  trader_type?: string
  sectors?: string[]
  risk_tolerance?: string
  experience_level?: string
  scenario_choice?: string
  archetype?: string
  tier?: string
  rank_score?: number
  level?: number
  xp?: number
  streak?: number
  starting_capital?: number
  current_value?: number
  trait_entry_timing?: number
  trait_hold_discipline?: number
  trait_position_sizing?: number
  trait_conviction_accuracy?: number
  trait_risk_management?: number
  trait_sector_focus?: number
  trait_drawdown_resilience?: number
  trait_thesis_quality?: number
  onboarding_complete?: boolean
  ai_profile_text?: string
  ai_archetype_description?: string
  ai_key_stats?: Record<string, unknown>
  ai_recommendations?: Record<string, unknown>[]
  ai_analyzed_at?: string
  created_at?: string
  updated_at?: string
}

export interface OnboardingResults {
  traderType: string
  sectors: string[]
  riskTolerance: string
  experienceLevel: string
  scenarioChoice: string
}

// Profile functions
export async function getProfile(clerkId: string): Promise<Profile | null> {
  const { data, error } = await supabase
    .from('profiles')
    .select('*')
    .eq('clerk_id', clerkId)
    .single()

  if (error && error.code !== 'PGRST116') throw error
  return data
}

export async function createProfile(clerkId: string, data: Partial<Profile>): Promise<Profile> {
  const { data: profile, error } = await supabase
    .from('profiles')
    .insert({ clerk_id: clerkId, ...data })
    .select()
    .single()

  if (error) throw error
  return profile
}

export async function updateProfile(clerkId: string, data: Partial<Profile>): Promise<Profile> {
  const { data: profile, error } = await supabase
    .from('profiles')
    .update({ ...data, updated_at: new Date().toISOString() })
    .eq('clerk_id', clerkId)
    .select()
    .single()

  if (error) throw error
  return profile
}

export async function saveOnboardingResults(clerkId: string, quizResults: OnboardingResults): Promise<Profile> {
  const archetype = computeArchetype(quizResults)
  const traits = computePreliminaryTraits(quizResults)

  const profileData: Partial<Profile> = {
    trader_type: quizResults.traderType,
    sectors: quizResults.sectors,
    risk_tolerance: quizResults.riskTolerance,
    experience_level: quizResults.experienceLevel,
    scenario_choice: quizResults.scenarioChoice,
    archetype: archetype,
    trait_entry_timing: traits.entryTiming,
    trait_hold_discipline: traits.holdDiscipline,
    trait_position_sizing: traits.positionSizing,
    trait_conviction_accuracy: traits.convictionAccuracy,
    trait_risk_management: traits.riskManagement,
    trait_sector_focus: traits.sectorFocus,
    trait_drawdown_resilience: traits.drawdownResilience,
    trait_thesis_quality: traits.thesisQuality,
    onboarding_complete: true,
  }

  const existing = await getProfile(clerkId)
  if (existing) {
    return updateProfile(clerkId, profileData)
  } else {
    return createProfile(clerkId, profileData)
  }
}

// Compute archetype from quiz answers
export function computeArchetype(results: OnboardingResults): string {
  const archetypes: Record<string, string> = {
    'momentum': 'Momentum Rider',
    'value': 'Disciplined Contrarian',
    'options': 'Premium Collector',
    'quant': 'Pattern Hunter',
    'swing': 'Patient Holder',
    'exploring': 'Versatile Generalist',
  }
  return archetypes[results.traderType] || 'Versatile Generalist'
}

// Compute preliminary trait scores from quiz answers (0-100)
export function computePreliminaryTraits(results: OnboardingResults) {
  const { traderType, riskTolerance, experienceLevel } = results

  const expBase: Record<string, number> = {
    'beginner': 35,
    '1-3years': 50,
    '3-7years': 65,
    '7plus': 78,
  }
  const base = expBase[experienceLevel] || 50

  const typeAdjustments: Record<string, Record<string, number>> = {
    'momentum': { entryTiming: 15, holdDiscipline: -5, positionSizing: 0, convictionAccuracy: 10, riskManagement: -5, sectorFocus: -10, drawdownResilience: 5, thesisQuality: 0 },
    'value': { entryTiming: -5, holdDiscipline: 15, positionSizing: 10, convictionAccuracy: 5, riskManagement: 10, sectorFocus: 5, drawdownResilience: 15, thesisQuality: 10 },
    'options': { entryTiming: 10, holdDiscipline: 5, positionSizing: 10, convictionAccuracy: 5, riskManagement: 5, sectorFocus: -5, drawdownResilience: 0, thesisQuality: 5 },
    'quant': { entryTiming: 10, holdDiscipline: 10, positionSizing: 15, convictionAccuracy: 0, riskManagement: 15, sectorFocus: -5, drawdownResilience: 10, thesisQuality: -5 },
    'swing': { entryTiming: 5, holdDiscipline: 10, positionSizing: 5, convictionAccuracy: 5, riskManagement: 5, sectorFocus: 0, drawdownResilience: 10, thesisQuality: 5 },
    'exploring': { entryTiming: 0, holdDiscipline: 0, positionSizing: 0, convictionAccuracy: 0, riskManagement: 0, sectorFocus: 0, drawdownResilience: 0, thesisQuality: 0 },
  }
  const adj = typeAdjustments[traderType] || typeAdjustments['exploring']

  const riskAdj: Record<string, Record<string, number>> = {
    'conservative': { riskManagement: 10, drawdownResilience: 10, positionSizing: 5, holdDiscipline: 5 },
    'moderate': { riskManagement: 5, positionSizing: 5 },
    'aggressive': { entryTiming: 5, convictionAccuracy: 5, riskManagement: -5 },
    'very-aggressive': { entryTiming: 10, convictionAccuracy: 10, riskManagement: -10, drawdownResilience: -5 },
  }
  const rAdj = riskAdj[riskTolerance] || {}

  const clamp = (v: number) => Math.max(20, Math.min(95, v))

  return {
    entryTiming: clamp(base + (adj.entryTiming || 0) + (rAdj.entryTiming || 0)),
    holdDiscipline: clamp(base + (adj.holdDiscipline || 0) + (rAdj.holdDiscipline || 0)),
    positionSizing: clamp(base + (adj.positionSizing || 0) + (rAdj.positionSizing || 0)),
    convictionAccuracy: clamp(base + (adj.convictionAccuracy || 0) + (rAdj.convictionAccuracy || 0)),
    riskManagement: clamp(base + (adj.riskManagement || 0) + (rAdj.riskManagement || 0)),
    sectorFocus: clamp(base + (adj.sectorFocus || 0) + (rAdj.sectorFocus || 0)),
    drawdownResilience: clamp(base + (adj.drawdownResilience || 0) + (rAdj.drawdownResilience || 0)),
    thesisQuality: clamp(base + (adj.thesisQuality || 0) + (rAdj.thesisQuality || 0)),
  }
}

// Get insight text for the profile reveal
export function getInsightText(traderType: string, riskTolerance: string): string {
  const insights: Record<string, Record<string, string>> = {
    'momentum': {
      'conservative': 'Trend follower with guardrails. You catch moves early but protect capital.',
      'moderate': 'Balanced momentum player. You ride trends but know when to step aside.',
      'aggressive': 'High-conviction trend follower. Your edge is timing. Your risk: overexposure.',
      'very-aggressive': 'Full-throttle momentum. Maximum conviction, maximum velocity.',
    },
    'value': {
      'conservative': 'Patient and disciplined. You will build slowly but survive every drawdown.',
      'moderate': 'Classic value approach. Buy cheap, hold long, let compounding work.',
      'aggressive': 'Concentrated value. Fewer positions, deeper conviction, bigger payoffs.',
      'very-aggressive': 'Contrarian deep-value. You buy what everyone else is selling.',
    },
    'options': {
      'conservative': 'Covered strategies. You sell premium with protection in place.',
      'moderate': 'Premium collector mentality. You profit from what others fear.',
      'aggressive': 'Volatility trader. You see opportunity where others see chaos.',
      'very-aggressive': 'Leveraged options player. Maximum premium extraction, calculated risk.',
    },
    'quant': {
      'conservative': 'Data-driven with strict risk controls. Every trade has a statistical edge.',
      'moderate': 'Systematic trader. Signals over sentiment, always.',
      'aggressive': 'Aggressive signal follower. When the data speaks, you act decisively.',
      'very-aggressive': 'Pure alpha seeker. Every inefficiency is your opportunity.',
    },
    'swing': {
      'conservative': 'Patient swing trader. You wait for the perfect setup and manage risk tight.',
      'moderate': 'Balanced swing approach. Capture multi-day moves with disciplined entries.',
      'aggressive': 'Aggressive swing trader. Bigger positions on high-conviction setups.',
      'very-aggressive': 'Power swing player. Maximum position size on the clearest signals.',
    },
    'exploring': {
      'conservative': 'Wide-open aperture with safety nets. The data will reveal your true style.',
      'moderate': 'Wide-open aperture. The data will reveal your true style.',
      'aggressive': 'Curious and bold. You will try everything until you find your edge.',
      'very-aggressive': 'Fearless explorer. Every strategy is worth testing at full conviction.',
    },
  }

  const typeInsights = insights[traderType] || insights['exploring']
  return typeInsights[riskTolerance] || typeInsights['moderate']
}
