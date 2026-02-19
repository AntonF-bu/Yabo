import { supabase } from '@/lib/supabase'
import type { Metadata } from 'next'
import Link from 'next/link'
import ProfileView from './ProfileView'

/* ------------------------------------------------------------------ */
/*  Shared types — exported for ProfileView                            */
/* ------------------------------------------------------------------ */

export interface ProfileDimension {
  key: string
  score: number
  label: string
  left: string
  right: string
  why: string
  details: Array<{ stat: string; desc: string }>
}

export interface StatGroup {
  title: string
  subtitle: string
  items: Array<{ v: string; l: string; h: boolean; why: string }>
}

export interface SectorData {
  name: string
  pct: number
  trades: number
  color: string
}

export interface TickerData {
  name: string
  trades: number
  weight: number
}

export interface HoldData {
  range: string
  pct: number
}

export interface BiasData {
  key: string
  label: string
  score: number
  color: string
  why: string
}

export interface ProfileData {
  headline: string
  archetype: string
  tier: string
  behavioralSummary: string
  stats: {
    winRate: number | null
    profitFactor: number | null
    avgHold: number | null
    trades: number | null
    portfolioValue: number | null
  }
  dimensions: ProfileDimension[]
  entry: { groups: StatGroup[] } | null
  exit: { groups: StatGroup[] } | null
  timing: { groups: StatGroup[] } | null
  psychology: { biases: BiasData[]; groups: StatGroup[] } | null
  sectors: SectorData[]
  tickers: TickerData[]
  holds: HoldData[]
  recommendation: string | null
  riskPersonality: string | null
  behavioralDeepDive: string | null
  taxEfficiency: string | null
  meta: { range: string; months: number; totalTrades: number }
}

/* ------------------------------------------------------------------ */
/*  Dimension config                                                   */
/* ------------------------------------------------------------------ */

const DIM_CONFIG: Array<{
  key: string
  left: string
  right: string
  shortLeft: string
  shortRight: string
}> = [
  { key: 'active_passive', left: 'Passive', right: 'Active', shortLeft: 'Passive', shortRight: 'Active' },
  { key: 'momentum_value', left: 'Value', right: 'Momentum', shortLeft: 'Value', shortRight: 'Momentum' },
  { key: 'concentrated_diversified', left: 'Spread', right: 'Focused', shortLeft: 'Spread', shortRight: 'Focused' },
  { key: 'disciplined_emotional', left: 'Reactive', right: 'Disciplined', shortLeft: 'Reactive', shortRight: 'Disciplined' },
  { key: 'sophisticated_simple', left: 'Simple', right: 'Complex', shortLeft: 'Simple', shortRight: 'Complex' },
  { key: 'improving_declining', left: 'Declining', right: 'Improving', shortLeft: 'Declining', shortRight: 'Improving' },
  { key: 'independent_herd', left: 'Herd', right: 'Independent', shortLeft: 'Herd', shortRight: 'Independent' },
  { key: 'risk_seeking_averse', left: 'Cautious', right: 'Aggressive', shortLeft: 'Cautious', shortRight: 'Aggressive' },
]

const SECTOR_COLORS = [
  '#B8860B', '#9A7B5B', '#6B8E6B', '#7B8FA8', '#A0785A',
  '#8B7355', '#6A8A6A', '#8C7BAD', '#B07D62', '#607080',
]

/* ------------------------------------------------------------------ */
/*  Explanation generators                                             */
/* ------------------------------------------------------------------ */

function pct(v: number | null | undefined): string {
  if (v == null) return '--'
  return `${(v * 100).toFixed(0)}%`
}

function getEntryExplanation(key: string, v: number | null): string {
  if (v == null) return ''
  switch (key) {
    case 'above_ma':
      if (v > 0.9) return `${pct(v)} of your entries are above the 20-day moving average. You almost never buy below it -- every entry waits for confirmed momentum.`
      if (v > 0.7) return `${pct(v)} of entries are in stocks with established upward momentum above the 20-day MA.`
      if (v > 0.5) return `About ${pct(v)} of entries are above the MA. You blend momentum with some contrarian entries.`
      return `Only ${pct(v)} of entries are above the 20-day MA. You frequently buy into weakness, a contrarian approach.`
    case 'breakout':
      if (v > 0.3) return `${pct(v)} of entries happen on breakout days. You actively chase momentum.`
      if (v > 0.15) return `${pct(v)} of entries catch breakouts. A moderate momentum approach.`
      return `${pct(v)} breakout entries. You rarely chase price spikes.`
    case 'rsi':
      if (v > 65) return `Average RSI at entry is ${v.toFixed(0)}. You tend to buy into strength, when stocks are already running.`
      if (v > 50) return `Average RSI of ${v.toFixed(0)} at entry. A balanced approach -- neither overbought nor oversold territory.`
      return `Average RSI of ${v.toFixed(0)} at entry. You lean toward buying in cooler conditions.`
    case 'dip_buy':
      if (v > 0.5) return `${pct(v)} of entries are dip buys. You consistently look for pullbacks before entering.`
      if (v > 0.2) return `${pct(v)} of your entries are dip buys. You sometimes wait for weakness.`
      return `Only ${pct(v)} dip buying. You prefer entering on strength, not waiting for pullbacks.`
    case 'green_day':
      if (v > 0.7) return `${pct(v)} of entries are on green days. You buy when the market confirms your thesis.`
      if (v > 0.5) return `${pct(v)} of entries on green days. A slight preference for confirmed momentum.`
      return `${pct(v)} green day entries. You often buy into red days, a contrarian signal.`
    case 'volume':
      if (v > 1.5) return `You enter at ${v.toFixed(1)}x average volume. You trade when the market is paying attention.`
      if (v > 0.8) return `Volume at entry is ${v.toFixed(1)}x average. Normal volume conditions.`
      return `Entry volume is ${v.toFixed(1)}x average. You tend to enter during quiet periods.`
    default: return ''
  }
}

function getExitExplanation(key: string, v: number | null): string {
  if (v == null) return ''
  switch (key) {
    case 'avg_gain':
      if (v > 20) return `Average winner is +${v.toFixed(1)}%. You let profits run significantly before closing.`
      if (v > 10) return `Average winner is +${v.toFixed(1)}%. Healthy gain capture.`
      return `Average winner is +${v.toFixed(1)}%. You tend to take profits quickly.`
    case 'avg_loss':
      if (Math.abs(v) > 15) return `Average loser is ${v.toFixed(1)}%. Your losses run deep before you cut them.`
      if (Math.abs(v) > 7) return `Average loser is ${v.toFixed(1)}%. Moderate loss tolerance.`
      return `Average loser is ${v.toFixed(1)}%. Tight stops -- you cut losses fast.`
    case 'partial':
      if (v > 0.3) return `${pct(v)} of exits are partial closes. You scale out of positions rather than exiting all at once.`
      if (v > 0.1) return `${pct(v)} partial exits. Occasional scaling out.`
      return `${pct(v)} partial exits. You typically exit positions in full.`
    case 'strength':
      if (v > 0.6) return `${pct(v)} of exits are into strength. You sell while the stock is still rising -- disciplined profit-taking.`
      if (v > 0.3) return `${pct(v)} of exits into strength. A mix of profit targets and momentum exits.`
      return `Only ${pct(v)} exits into strength. You tend to hold through peaks.`
    case 'panic':
      if (v > 0.3) return `Panic score of ${pct(v)}. A notable pattern of reactive selling during sharp drawdowns.`
      if (v > 0.1) return `Panic score of ${pct(v)}. Some reactive exits during sharp moves.`
      return `Panic score of ${pct(v)}. You stay calm under pressure.`
    case 'profit_target':
      if (v > 15) return `Implicit profit target around +${v.toFixed(0)}%. You tend to exit winners around this level.`
      if (v > 5) return `Exits cluster around +${v.toFixed(0)}%, suggesting an implicit profit target.`
      return `Exits cluster at +${v.toFixed(0)}%. Tight profit taking.`
    default: return ''
  }
}

function getTimingExplanation(key: string, v: number | null): string {
  if (v == null) return ''
  switch (key) {
    case 'peak_hour':
      if (v <= 10) return `Your peak activity is ${v}:00. You prefer the opening volatility.`
      if (v >= 15) return `Peak activity at ${v}:00. You trade in the late session, often the power hour.`
      return `Peak activity at ${v}:00. You trade during the midday session.`
    case 'active_days':
      if (v > 15) return `Active ${v.toFixed(0)} days per month. You are a consistent, daily presence in the market.`
      if (v > 8) return `Active ${v.toFixed(0)} days per month. Regular but not obsessive.`
      return `Only ${v.toFixed(0)} active days per month. You trade selectively and infrequently.`
    case 'trades_per_day':
      if (v > 5) return `${v.toFixed(1)} trades per active day. Heavy session activity.`
      if (v > 2) return `${v.toFixed(1)} trades per session. Moderate activity when engaged.`
      return `${v.toFixed(1)} trades per session. Deliberate, one-at-a-time execution.`
    case 'longest_gap':
      return `Longest break was ${v.toFixed(0)} days. ${v > 30 ? 'You take extended periods away from the market.' : v > 14 ? 'Occasional multi-week breaks.' : 'You stay consistently engaged.'}`
    case 'avg_gap':
      return `Average gap between trades is ${v.toFixed(1)} days. ${v > 7 ? 'A patient, selective cadence.' : v > 3 ? 'Regular but measured.' : 'Highly active -- rarely more than a few days off.'}`
    case 'friday_bias':
      if (v > 1.3) return `Friday activity ${v.toFixed(1)}x normal. You are notably more active heading into weekends.`
      if (v > 0.8) return `Friday activity is ${v.toFixed(1)}x normal. No strong weekend positioning bias.`
      return `Friday activity ${v.toFixed(1)}x normal. You ease off before weekends.`
    default: return ''
  }
}

function getBiasExplanation(key: string, v: number | null): string {
  if (v == null) return ''
  const s = v > 1 ? v : v * 100
  switch (key) {
    case 'disposition':
      if (s > 60) return `Score of ${s.toFixed(0)}. You are significantly more likely to sell winners too early while holding losers too long. This is the classic disposition effect.`
      if (s > 30) return `Score of ${s.toFixed(0)}. A moderate disposition bias. You sometimes cut winners short.`
      return `Score of ${s.toFixed(0)}. Low disposition bias -- you manage winners and losers evenly.`
    case 'revenge':
      if (s > 30) return `Score of ${s.toFixed(0)}%. After losses, you tend to increase activity -- trading to "make it back" rather than pausing to reset.`
      if (s > 10) return `Score of ${s.toFixed(0)}%. Some revenge trading patterns after losses.`
      return `Score of ${s.toFixed(0)}%. You stay composed after losses and avoid revenge trades.`
    case 'overconfidence':
      if (s > 60) return `Score of ${s.toFixed(0)}. You tend to increase position sizes after wins, a sign of overconfidence.`
      if (s > 30) return `Score of ${s.toFixed(0)}. Moderate tendency to scale up after success.`
      return `Score of ${s.toFixed(0)}. You keep sizing consistent regardless of recent performance.`
    case 'familiarity':
      if (s > 60) return `Score of ${s.toFixed(0)}. You heavily favor familiar names, potentially missing opportunities in new areas.`
      if (s > 30) return `Score of ${s.toFixed(0)}. Some home-field bias toward familiar tickers.`
      return `Score of ${s.toFixed(0)}. You are open to trading unfamiliar names.`
    case 'anchoring':
      if (s > 60) return `Score of ${s.toFixed(0)}. Previous entry prices strongly influence your next decisions, creating anchor bias.`
      if (s > 30) return `Score of ${s.toFixed(0)}. Some price anchoring patterns.`
      return `Score of ${s.toFixed(0)}. You evaluate each trade on current merit, not past prices.`
    case 'loss_rebuy':
      if (s > 40) return `${s.toFixed(0)}% of losing positions are re-entered. You frequently go back to stocks that burned you.`
      if (s > 15) return `${s.toFixed(0)}% loss rebuy rate. You occasionally re-enter losers.`
      return `${s.toFixed(0)}% rebuy rate on losers. You move on from bad trades.`
    default: return `Score: ${s.toFixed(0)}`
  }
}

/* ------------------------------------------------------------------ */
/*  Transform raw engine output → ProfileData                          */
/* ------------------------------------------------------------------ */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function transformRawResult(raw: any): ProfileData {
  const f = raw?.features || {}
  const cl = raw?.classification_v2 || {}
  const narr = raw?.narrative || {}
  const ss = raw?.summary_stats || {}
  const dims = cl.dimensions || {}

  // ── Stats ──
  const winRate = ss.win_rate ?? f.portfolio_win_rate ?? null
  const profitFactor = ss.profit_factor ?? f.portfolio_profit_factor ?? null
  const avgHold = ss.avg_hold_days ?? f.holding_mean_days ?? null
  const totalTrades = ss.total_trades ?? f.portfolio_total_round_trips ?? null
  const portfolioValue = f.portfolio_estimated_value ?? null

  // ── Dimensions ──
  const dimensions: ProfileDimension[] = DIM_CONFIG
    .filter(dc => dims[dc.key])
    .map(dc => {
      const d = dims[dc.key]
      const evidence: string[] = d.evidence || []
      const condensed = evidence.length > 0
        ? evidence[0]
        : d.label || ''
      const details = evidence.slice(0, 4).map((e: string) => {
        const colonIdx = e.indexOf(':')
        if (colonIdx > 0 && colonIdx < 40) {
          return { stat: e.slice(0, colonIdx).trim(), desc: e.slice(colonIdx + 1).trim() }
        }
        return { stat: '', desc: e }
      })
      return {
        key: dc.key,
        score: d.score ?? 50,
        label: d.label || '',
        left: dc.left,
        right: dc.right,
        why: condensed,
        details,
      }
    })
    .sort((a, b) => Math.abs(b.score - 50) - Math.abs(a.score - 50))

  // ── Entry ──
  const hasEntry = f.entry_timing_pct_above_ma != null ||
    f.entry_timing_breakout_pct != null ||
    f.entry_timing_avg_rsi != null
  const entry = hasEntry ? {
    groups: [{
      title: 'Entry Patterns',
      subtitle: 'How you get into positions',
      items: [
        f.entry_timing_pct_above_ma != null ? { v: pct(f.entry_timing_pct_above_ma), l: 'Entries above 20d MA', h: f.entry_timing_pct_above_ma > 0.8, why: getEntryExplanation('above_ma', f.entry_timing_pct_above_ma) } : null,
        f.entry_timing_breakout_pct != null ? { v: pct(f.entry_timing_breakout_pct), l: 'Breakout entries', h: f.entry_timing_breakout_pct > 0.25, why: getEntryExplanation('breakout', f.entry_timing_breakout_pct) } : null,
        f.entry_timing_avg_rsi != null ? { v: f.entry_timing_avg_rsi.toFixed(0), l: 'Avg RSI at entry', h: f.entry_timing_avg_rsi > 60 || f.entry_timing_avg_rsi < 40, why: getEntryExplanation('rsi', f.entry_timing_avg_rsi) } : null,
        f.entry_timing_dip_buy_pct != null ? { v: pct(f.entry_timing_dip_buy_pct), l: 'Dip buying', h: f.entry_timing_dip_buy_pct > 0.4, why: getEntryExplanation('dip_buy', f.entry_timing_dip_buy_pct) } : null,
        f.entry_timing_green_day_pct != null ? { v: pct(f.entry_timing_green_day_pct), l: 'Green day entries', h: f.entry_timing_green_day_pct > 0.7, why: getEntryExplanation('green_day', f.entry_timing_green_day_pct) } : null,
        f.entry_timing_volume_relative != null ? { v: `${f.entry_timing_volume_relative.toFixed(1)}x`, l: 'Volume vs average', h: f.entry_timing_volume_relative > 1.3, why: getEntryExplanation('volume', f.entry_timing_volume_relative) } : null,
      ].filter(Boolean) as StatGroup['items'],
    }],
  } : null

  // ── Exit ──
  const hasExit = f.exit_avg_gain_pct != null ||
    f.exit_avg_loss_pct != null ||
    f.exit_partial_close_pct != null
  const exit = hasExit ? {
    groups: [{
      title: 'Exit Patterns',
      subtitle: 'How you close positions',
      items: [
        f.exit_avg_gain_pct != null ? { v: `+${f.exit_avg_gain_pct.toFixed(1)}%`, l: 'Avg winner', h: f.exit_avg_gain_pct > 15, why: getExitExplanation('avg_gain', f.exit_avg_gain_pct) } : null,
        f.exit_avg_loss_pct != null ? { v: `${f.exit_avg_loss_pct.toFixed(1)}%`, l: 'Avg loser', h: Math.abs(f.exit_avg_loss_pct) > 10, why: getExitExplanation('avg_loss', f.exit_avg_loss_pct) } : null,
        f.exit_partial_close_pct != null ? { v: pct(f.exit_partial_close_pct), l: 'Partial exits', h: f.exit_partial_close_pct > 0.2, why: getExitExplanation('partial', f.exit_partial_close_pct) } : null,
        f.exit_into_strength_pct != null ? { v: pct(f.exit_into_strength_pct), l: 'Exits into strength', h: f.exit_into_strength_pct > 0.5, why: getExitExplanation('strength', f.exit_into_strength_pct) } : null,
        f.exit_panic_score != null ? { v: pct(f.exit_panic_score), l: 'Panic exit score', h: f.exit_panic_score > 0.2, why: getExitExplanation('panic', f.exit_panic_score) } : null,
        f.exit_profit_target_cluster != null ? { v: `+${f.exit_profit_target_cluster.toFixed(0)}%`, l: 'Implicit profit target', h: true, why: getExitExplanation('profit_target', f.exit_profit_target_cluster) } : null,
      ].filter(Boolean) as StatGroup['items'],
    }],
  } : null

  // ── Timing ──
  const hasTiming = f.timing_preferred_hour != null ||
    f.timing_active_days_per_month != null
  const timing = hasTiming ? {
    groups: [{
      title: 'Activity Patterns',
      subtitle: 'When and how often you trade',
      items: [
        f.timing_preferred_hour != null ? { v: `${f.timing_preferred_hour}:00`, l: 'Peak hour', h: f.timing_preferred_hour <= 10 || f.timing_preferred_hour >= 15, why: getTimingExplanation('peak_hour', f.timing_preferred_hour) } : null,
        f.timing_active_days_per_month != null ? { v: `${f.timing_active_days_per_month.toFixed(0)}d`, l: 'Active days/month', h: f.timing_active_days_per_month > 15, why: getTimingExplanation('active_days', f.timing_active_days_per_month) } : null,
        f.timing_trades_per_active_day != null ? { v: f.timing_trades_per_active_day.toFixed(1), l: 'Trades per session', h: f.timing_trades_per_active_day > 4, why: getTimingExplanation('trades_per_day', f.timing_trades_per_active_day) } : null,
        f.timing_longest_gap_days != null ? { v: `${f.timing_longest_gap_days.toFixed(0)}d`, l: 'Longest break', h: f.timing_longest_gap_days > 30, why: getTimingExplanation('longest_gap', f.timing_longest_gap_days) } : null,
        f.timing_avg_gap_days != null ? { v: `${f.timing_avg_gap_days.toFixed(1)}d`, l: 'Avg gap between trades', h: false, why: getTimingExplanation('avg_gap', f.timing_avg_gap_days) } : null,
        f.timing_friday_bias != null ? { v: `${f.timing_friday_bias.toFixed(1)}x`, l: 'Friday activity', h: f.timing_friday_bias > 1.3 || f.timing_friday_bias < 0.7, why: getTimingExplanation('friday_bias', f.timing_friday_bias) } : null,
      ].filter(Boolean) as StatGroup['items'],
    }],
  } : null

  // ── Psychology / Biases ──
  const biases: BiasData[] = [
    f.psychology_disposition_bias != null ? { key: 'disposition', label: 'Disposition Effect', score: f.psychology_disposition_bias > 1 ? f.psychology_disposition_bias : f.psychology_disposition_bias * 100, color: '#C45A4A', why: getBiasExplanation('disposition', f.psychology_disposition_bias) } : null,
    f.psychology_revenge_trading_score != null ? { key: 'revenge', label: 'Revenge Trading', score: f.psychology_revenge_trading_score > 1 ? f.psychology_revenge_trading_score : f.psychology_revenge_trading_score * 100, color: '#C45A4A', why: getBiasExplanation('revenge', f.psychology_revenge_trading_score) } : null,
    f.psychology_overconfidence_score != null ? { key: 'overconfidence', label: 'Overconfidence', score: f.psychology_overconfidence_score > 1 ? f.psychology_overconfidence_score : f.psychology_overconfidence_score * 100, color: '#B8860B', why: getBiasExplanation('overconfidence', f.psychology_overconfidence_score) } : null,
    f.psychology_familiarity_bias != null ? { key: 'familiarity', label: 'Familiarity Bias', score: f.psychology_familiarity_bias > 1 ? f.psychology_familiarity_bias : f.psychology_familiarity_bias * 100, color: '#9A7B5B', why: getBiasExplanation('familiarity', f.psychology_familiarity_bias) } : null,
    f.psychology_anchoring_bias != null ? { key: 'anchoring', label: 'Anchoring', score: f.psychology_anchoring_bias > 1 ? f.psychology_anchoring_bias : f.psychology_anchoring_bias * 100, color: '#7B8FA8', why: getBiasExplanation('anchoring', f.psychology_anchoring_bias) } : null,
    f.psychology_loss_rebuy_rate != null ? { key: 'loss_rebuy', label: 'Loss Rebuy', score: f.psychology_loss_rebuy_rate > 1 ? f.psychology_loss_rebuy_rate : f.psychology_loss_rebuy_rate * 100, color: '#C45A4A', why: getBiasExplanation('loss_rebuy', f.psychology_loss_rebuy_rate) } : null,
  ].filter(Boolean) as BiasData[]

  const hasPsych = biases.length > 0 || f.psychology_emotional_index != null
  const psychItems: StatGroup['items'] = [
    f.psychology_emotional_index != null ? { v: f.psychology_emotional_index.toFixed(0), l: 'Emotional Index', h: f.psychology_emotional_index > 50, why: `Emotional index of ${f.psychology_emotional_index.toFixed(0)}. ${f.psychology_emotional_index > 60 ? 'Your trading shows significant emotional influence.' : f.psychology_emotional_index > 35 ? 'Moderate emotional influence on your decisions.' : 'Low emotional influence -- you trade with discipline.'}` } : null,
    f.psychology_max_consecutive_wins != null ? { v: String(f.psychology_max_consecutive_wins), l: 'Max win streak', h: f.psychology_max_consecutive_wins >= 5, why: `Longest winning streak: ${f.psychology_max_consecutive_wins} trades in a row.` } : null,
    f.psychology_max_consecutive_losses != null ? { v: String(f.psychology_max_consecutive_losses), l: 'Max loss streak', h: f.psychology_max_consecutive_losses >= 4, why: `Longest losing streak: ${f.psychology_max_consecutive_losses} trades. ${f.psychology_max_consecutive_losses >= 5 ? 'Extended drawdowns test your emotional resilience.' : 'Manageable losing streaks.'}` } : null,
    f.psychology_mistake_repetition_rate != null ? { v: pct(f.psychology_mistake_repetition_rate), l: 'Mistake repetition', h: f.psychology_mistake_repetition_rate > 0.3, why: `${pct(f.psychology_mistake_repetition_rate)} of similar losing setups are repeated. ${f.psychology_mistake_repetition_rate > 0.3 ? 'You tend to make the same mistakes.' : 'You generally learn from losing trades.'}` } : null,
  ].filter(Boolean) as StatGroup['items']

  const psychology = hasPsych ? {
    biases,
    groups: psychItems.length > 0 ? [{ title: 'Mental Patterns', subtitle: 'Streaks, emotions, and repetition', items: psychItems }] : [],
  } : null

  // ── Sectors ──
  const rawSectors = f.concentration_dominant_sectors || []
  const sectors: SectorData[] = rawSectors.slice(0, 8).map((s: any, i: number) => ({
    name: typeof s === 'string' ? s : (s.sector || s.name || 'Unknown'),
    pct: typeof s === 'object' ? ((s.weight ?? 0) * 100) : 0,
    trades: typeof s === 'object' ? (s.trade_count ?? 0) : 0,
    color: SECTOR_COLORS[i % SECTOR_COLORS.length],
  }))

  // ── Tickers ──
  const rawTickers = f.concentration_top_tickers || []
  const tickers: TickerData[] = rawTickers.slice(0, 10).map((t: any) => ({
    name: typeof t === 'string' ? t : (t.ticker || t.name || ''),
    trades: typeof t === 'object' ? (t.count ?? t.trades ?? 0) : 0,
    weight: typeof t === 'object' ? ((t.weight ?? t.pct ?? 0) * 100) : 0,
  }))

  // ── Hold distribution ──
  const rawHolds = f.holding_period_distribution || {}
  const holds: HoldData[] = Object.entries(rawHolds).map(([range, count]) => ({
    range,
    pct: typeof count === 'number' ? count : 0,
  }))

  // ── Date range ──
  const dateStart = f.timing_date_range_start || raw?.extraction?.metadata?.date_range?.start || ''
  const dateEnd = f.timing_date_range_end || raw?.extraction?.metadata?.date_range?.end || ''
  let rangeStr = ''
  let months = 0
  if (dateStart && dateEnd) {
    const fmt = (d: string) => {
      try { return new Date(d).toLocaleDateString('en-US', { month: 'short', year: 'numeric' }) } catch { return d }
    }
    rangeStr = `${fmt(dateStart)} – ${fmt(dateEnd)}`
    try {
      const d0 = new Date(dateStart)
      const d1 = new Date(dateEnd)
      months = Math.max(1, Math.round((d1.getTime() - d0.getTime()) / (30 * 24 * 60 * 60 * 1000)))
    } catch { /* ignore */ }
  }

  return {
    headline: narr.headline || cl.primary_archetype || 'Your Trading DNA',
    archetype: cl.primary_archetype || '',
    tier: cl.confidence_tier || narr.confidence_metadata?.tier_label || '',
    behavioralSummary: cl.behavioral_summary || narr.archetype_summary || '',
    stats: { winRate, profitFactor, avgHold, trades: totalTrades, portfolioValue },
    dimensions,
    entry,
    exit,
    timing,
    psychology,
    sectors,
    tickers,
    holds,
    recommendation: narr.key_recommendation || null,
    riskPersonality: narr.risk_personality || null,
    behavioralDeepDive: narr.behavioral_deep_dive || null,
    taxEfficiency: narr.tax_efficiency || null,
    meta: { range: rangeStr, months, totalTrades: totalTrades ?? 0 },
  }
}

/* ------------------------------------------------------------------ */
/*  State screens                                                      */
/* ------------------------------------------------------------------ */

function NotFoundState() {
  return (
    <main style={{ minHeight: '100vh', background: '#F5F3EF', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px' }}>
      <div style={{ textAlign: 'center', maxWidth: 420 }}>
        <h1 style={{ fontFamily: "'Newsreader', Georgia, serif", fontSize: 28, fontWeight: 400, color: '#1A1715', marginBottom: 12 }}>
          Profile not found
        </h1>
        <p style={{ fontFamily: "'Inter', system-ui, sans-serif", fontSize: 15, color: '#8A8580', lineHeight: 1.6 }}>
          This analysis may still be in progress, or the link may be incorrect.
        </p>
        <Link href="/intake" style={{ display: 'inline-block', marginTop: 24, fontFamily: "'Inter', system-ui, sans-serif", fontSize: 14, color: '#B8860B', textDecoration: 'none' }}>
          Start a new analysis
        </Link>
      </div>
    </main>
  )
}

function ProcessingState() {
  return (
    <main style={{ minHeight: '100vh', background: '#F5F3EF', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px' }}>
      <div style={{ textAlign: 'center', maxWidth: 420 }}>
        <h1 style={{ fontFamily: "'Newsreader', Georgia, serif", fontSize: 28, fontWeight: 400, color: '#1A1715', marginBottom: 12 }}>
          Your analysis is being processed
        </h1>
        <p style={{ fontFamily: "'Inter', system-ui, sans-serif", fontSize: 15, color: '#8A8580', lineHeight: 1.6 }}>
          Check back shortly. We&apos;ll have your Trading DNA ready soon.
        </p>
      </div>
    </main>
  )
}

/* ------------------------------------------------------------------ */
/*  Metadata + Page                                                    */
/* ------------------------------------------------------------------ */

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: 'Trading DNA Profile | Yabo',
    description: 'Behavioral trading analysis powered by Yabo',
  }
}

export default async function ProfilePage({
  params,
}: {
  params: { id: string }
}) {
  const profileId = params.id

  const { data, error } = await supabase
    .from('trade_imports')
    .select('raw_result, status, trade_count')
    .eq('profile_id', profileId)
    .order('created_at', { ascending: false })
    .limit(1)
    .maybeSingle()

  if (!data || error) return <NotFoundState />
  if (data.status !== 'processed') return <ProcessingState />
  if (!data.raw_result) return <NotFoundState />

  const profileData = transformRawResult(data.raw_result)

  return <ProfileView data={profileData} />
}
