/* ------------------------------------------------------------------ */
/*  Blind spot computation — pure functions, no API calls               */
/* ------------------------------------------------------------------ */

import type { BlindSpot, DimensionData, TradeRow } from './types'
import { formatDollars, formatPct, formatMultiplier, feat } from './formatters'
import { computeWashSales } from './computeWashSales'

export function computeBlindSpots(
  features: Record<string, unknown> | null,
  holdingsFeatures: Record<string, unknown> | null,
  portfolioNarrative: Record<string, unknown> | null,
  trades: TradeRow[] | null,
  dimensions: Record<string, DimensionData> | null
): BlindSpot[] {
  const spots: BlindSpot[] = []

  // 1. Concentration Risk
  const top1 = feat(holdingsFeatures, 'h_top1_pct')
  if (top1 != null && top1 > 0.25) {
    const top3 = feat(holdingsFeatures, 'h_top3_pct')
    const maxLoss = feat(holdingsFeatures, 'h_max_single_position_loss')
    spots.push({
      severity: 'danger',
      title: top1 > 0.4
        ? 'Half your portfolio rides on one name'
        : 'Top position dominates your portfolio',
      body: `Your largest single position is ${formatPct(top1, 1)} of total value.${
        top3 != null ? ` Your top 3 positions account for ${formatPct(top3, 1)}.` : ''
      }${
        maxLoss != null ? ` A full wipeout of your top holding would cost ${formatDollars(maxLoss)}.` : ''
      }`,
      evidence: [
        { label: 'Top position', value: formatPct(top1, 1) },
        ...(top3 != null ? [{ label: 'Top 3', value: formatPct(top3, 1) }] : []),
        ...(maxLoss != null ? [{ label: 'Max single loss', value: formatDollars(maxLoss) }] : []),
      ],
    })
  }

  // 2. Zero Hedging
  const hedgingScore = feat(holdingsFeatures, 'h_hedging_score')
  const optionsNotional = feat(holdingsFeatures, 'h_options_notional')
  if (hedgingScore === 0 && optionsNotional != null && optionsNotional > 1_000_000) {
    const putCount = feat(holdingsFeatures, 'h_protective_put_count')
    const leverage = feat(holdingsFeatures, 'h_options_leverage_ratio')
    spots.push({
      severity: 'warning',
      title: `${formatDollars(optionsNotional)} in options exposure. Zero hedging.`,
      body: `You have significant options notional exposure with no protective puts detected. ${
        leverage != null ? `Your options leverage ratio is ${formatMultiplier(leverage)}.` : ''
      }`,
      evidence: [
        { label: 'Options notional', value: formatDollars(optionsNotional) },
        ...(putCount != null ? [{ label: 'Protective puts', value: String(putCount) }] : []),
        ...(leverage != null ? [{ label: 'Leverage ratio', value: formatMultiplier(leverage) }] : []),
      ],
    })
  }

  // 3. Mistake Repetition
  const disciplineScore = dimensions?.disciplined_emotional?.score
  if (disciplineScore != null && disciplineScore < 50) {
    const evidence = dimensions?.disciplined_emotional?.evidence || []
    let mistakeRate: string | null = null
    let revengeRate: string | null = null
    for (const e of evidence) {
      const mistakeMatch = e.match(/(\d+)%?\s*(?:of\s+)?(?:similar\s+)?(?:losing\s+)?(?:mistakes?|patterns?)\s+(?:are\s+)?repeat/i)
        || e.match(/(\d+)%\s+mistake\s+repetition/i)
        || e.match(/mistake[^.]*?(\d+)%/i)
        || e.match(/(\d+)%.*repeat/i)
      if (mistakeMatch) mistakeRate = `${mistakeMatch[1]}%`
      const revengeMatch = e.match(/(\d+)%.*revenge/i) || e.match(/revenge[^.]*?(\d+)%/i)
      if (revengeMatch) revengeRate = `${revengeMatch[1]}%`
    }
    spots.push({
      severity: 'warning',
      title: 'You keep making the same mistakes',
      body: evidence.length > 0
        ? evidence.slice(0, 2).join('. ') + '.'
        : `Your discipline score is ${Math.round(disciplineScore)}, indicating patterns of repeated errors.`,
      evidence: [
        ...(mistakeRate ? [{ label: 'Mistake repetition', value: mistakeRate }] : []),
        { label: 'Discipline score', value: String(Math.round(disciplineScore)) },
        ...(revengeRate ? [{ label: 'Revenge trading', value: revengeRate }] : []),
      ],
    })
  }

  // 4. Wash Sale Exposure
  const washSales = computeWashSales(trades)
  if (washSales) {
    spots.push({
      severity: 'info',
      title: 'Potential wash sale events detected',
      body: `${washSales.tickerCount} ticker${washSales.tickerCount !== 1 ? 's' : ''} show sell-then-rebuy patterns within 30 days. ${
        washSales.topTicker
          ? `${washSales.topTicker} is the most active with ${washSales.topTickerEvents} events.`
          : ''
      }${
        washSales.crossAccountCount > 0
          ? ` Cross-account wash sale activity detected in ${washSales.crossAccountCount} events.`
          : ''
      }`,
      evidence: [
        { label: 'Tickers flagged', value: String(washSales.tickerCount) },
        ...(washSales.topTicker
          ? [{ label: `${washSales.topTicker} events`, value: String(washSales.topTickerEvents) }]
          : []),
        ...(washSales.crossAccountCount > 0
          ? [{ label: 'Cross-account', value: String(washSales.crossAccountCount) }]
          : []),
      ],
    })
  }

  // 5. Fee Drag
  const feeDrag = feat(holdingsFeatures, 'h_fee_drag_pct')
  if (feeDrag != null && feeDrag > 0.01) {
    const annualYield = feat(holdingsFeatures, 'h_annual_yield')
    const totalValue = feat(holdingsFeatures, 'h_total_value')
    const feeDollars = totalValue != null ? feeDrag * totalValue : null
    const yieldRatio = annualYield != null && annualYield > 0
      ? ((feeDrag / annualYield) * 100).toFixed(1)
      : null
    spots.push({
      severity: 'info',
      title: `Fees consume ${formatPct(feeDrag, 1)} of your portfolio`,
      body: `Annual fee drag of ${formatPct(feeDrag, 1)}${
        feeDollars != null ? ` (${formatDollars(feeDollars)})` : ''
      }${
        annualYield != null ? ` against a ${formatPct(annualYield, 1)} yield` : ''
      }${
        yieldRatio ? ` means ${yieldRatio}% of your income goes to fees` : ''
      }.`,
      evidence: [
        { label: 'Fee drag', value: formatPct(feeDrag, 2) },
        ...(annualYield != null ? [{ label: 'Annual yield', value: formatPct(annualYield, 1) }] : []),
        ...(feeDollars != null ? [{ label: 'Fee cost', value: formatDollars(feeDollars) }] : []),
      ],
    })
  }

  // 6. Earnings-Adjacent Edge
  const earningsProximity = feat(features, 'entry_earnings_proximity')
  if (earningsProximity != null && earningsProximity > 0.4) {
    const preEarnings = feat(features, 'entry_pre_earnings')
    const postEarnings = feat(features, 'entry_post_earnings')
    spots.push({
      severity: 'opportunity',
      title: 'Your edge sharpens near earnings',
      body: `${formatPct(earningsProximity, 0)} of your entries occur near earnings announcements. ${
        preEarnings != null && postEarnings != null
          ? `You split ${formatPct(preEarnings, 0)} pre-earnings and ${formatPct(postEarnings, 0)} post-earnings.`
          : 'This concentration suggests earnings-driven conviction.'
      }`,
      evidence: [
        { label: 'Earnings proximity', value: formatPct(earningsProximity, 0) },
        ...(preEarnings != null ? [{ label: 'Pre-earnings', value: formatPct(preEarnings, 0) }] : []),
        ...(postEarnings != null ? [{ label: 'Post-earnings', value: formatPct(postEarnings, 0) }] : []),
      ],
    })
  }

  return spots
}
