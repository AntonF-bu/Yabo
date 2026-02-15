import { NextResponse } from 'next/server'
import Anthropic from '@anthropic-ai/sdk'

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || '',
})

export async function POST(request: Request) {
  try {
    const { trades, positions, portfolioValue, cashBalance } = await request.json()

    if (!trades || !Array.isArray(trades) || trades.length === 0) {
      return NextResponse.json({ error: 'No trades provided' }, { status: 400 })
    }

    if (!process.env.ANTHROPIC_API_KEY) {
      // Return fallback analysis when no API key
      return NextResponse.json(generateFallbackAnalysis(trades, positions, portfolioValue, cashBalance))
    }

    const tradesSummary = trades.map((t: { date: string; ticker: string; action: string; quantity: number; price: number; total: number; sector?: string }) =>
      `${t.date} | ${t.action.toUpperCase()} ${t.quantity} ${t.ticker} @ $${t.price} ($${t.total}) [${t.sector || 'Unknown'}]`
    ).join('\n')

    const positionsSummary = positions.map((p: { ticker: string; shares: number; avgCost: number; currentPrice: number; sector: string }) =>
      `${p.ticker}: ${p.shares} shares @ $${p.avgCost} avg (current: $${p.currentPrice}) [${p.sector}]`
    ).join('\n')

    const prompt = `You are an expert trading psychologist and portfolio analyst for Yabo, a trading analytics platform. Analyze this trader's history and provide a comprehensive Trading DNA profile.

TRADE HISTORY (${trades.length} trades):
${tradesSummary}

CURRENT POSITIONS:
${positionsSummary || 'No open positions'}

PORTFOLIO: $${portfolioValue?.toLocaleString() || '100,000'} total value, $${cashBalance?.toLocaleString() || '0'} cash

Respond with ONLY valid JSON (no markdown, no code fences) in this exact structure:
{
  "archetype": "A 2-3 word trader archetype name (e.g. 'Momentum Rider', 'Sector Specialist', 'Disciplined Contrarian')",
  "archetypeDescription": "A 1-2 sentence description of this archetype's core traits",
  "profileText": "A 3-4 sentence narrative profile of this specific trader. Reference their actual trades, patterns, and tendencies. Be specific about tickers and behaviors you observe.",
  "keyStats": {
    "winRate": "percentage as string like '68%'",
    "avgHoldDays": "number as string like '23 days'",
    "bestSector": "their strongest sector",
    "worstTrait": "their weakest behavioral trait",
    "signaturePattern": "A specific pattern you detect (e.g. 'Buys semis within 48hrs of dips -- 8 trades, 6 wins')"
  },
  "traits": {
    "entry_timing": 72,
    "hold_discipline": 58,
    "position_sizing": 65,
    "conviction_accuracy": 71,
    "risk_management": 60,
    "sector_focus": 85,
    "drawdown_resilience": 63,
    "thesis_quality": 70
  },
  "recommendations": [
    {
      "priority": "high",
      "title": "Short actionable title",
      "body": "2-3 sentence specific recommendation referencing their actual positions and patterns",
      "actionLabel": "Apply / Review / Consider",
      "impact": "+$X,XXX estimated"
    }
  ]
}

IMPORTANT RULES for trait scores:
- All trait scores must be integers between 20 and 95
- Base scores on actual evidence from the trade data
- Be honest -- don't inflate scores

Provide exactly 3 recommendations with priorities: one "high", one "medium", one "low".`

    const message = await anthropic.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 2000,
      messages: [{ role: 'user', content: prompt }],
    })

    const text = message.content[0].type === 'text' ? message.content[0].text : ''
    const result = JSON.parse(text)

    // Validate and clamp trait scores
    const traits = result.traits || {}
    const clamp = (v: number) => Math.max(20, Math.min(95, Math.round(v || 50)))
    result.traits = {
      entry_timing: clamp(traits.entry_timing),
      hold_discipline: clamp(traits.hold_discipline),
      position_sizing: clamp(traits.position_sizing),
      conviction_accuracy: clamp(traits.conviction_accuracy),
      risk_management: clamp(traits.risk_management),
      sector_focus: clamp(traits.sector_focus),
      drawdown_resilience: clamp(traits.drawdown_resilience),
      thesis_quality: clamp(traits.thesis_quality),
    }

    return NextResponse.json(result)
  } catch (error) {
    console.error('Analysis error:', error)
    return NextResponse.json(
      { error: 'Failed to analyze trades. Please try again.' },
      { status: 500 }
    )
  }
}

function generateFallbackAnalysis(
  trades: Array<{ date: string; ticker: string; action: string; quantity: number; price: number; total: number; sector?: string }>,
  positions: Array<{ ticker: string; shares: number }>,
  portfolioValue: number,
  cashBalance: number,
) {
  const buys = trades.filter(t => t.action === 'buy')
  const sells = trades.filter(t => t.action === 'sell')
  const tickers = Array.from(new Set(trades.map(t => t.ticker)))
  const sectors = Array.from(new Set(trades.map(t => t.sector).filter(Boolean)))
  const topSector = sectors[0] || 'Technology'

  // Basic win estimation
  let wins = 0
  for (const sell of sells) {
    const matchingBuys = buys.filter(b => b.ticker === sell.ticker && b.date < sell.date)
    if (matchingBuys.length > 0) {
      const avgBuyPrice = matchingBuys.reduce((s, b) => s + b.price, 0) / matchingBuys.length
      if (sell.price > avgBuyPrice) wins++
    }
  }
  const winRate = sells.length > 0 ? Math.round((wins / sells.length) * 100) : 50

  return {
    archetype: 'Sector Specialist',
    archetypeDescription: `Concentrated conviction trader with strong ${topSector} sector knowledge and systematic entry patterns.`,
    profileText: `Active trader with ${trades.length} trades across ${tickers.length} tickers. Shows strong sector concentration in ${topSector} with a ${winRate}% win rate on closed positions. Portfolio value stands at $${portfolioValue?.toLocaleString() || '100,000'} with ${positions?.length || 0} open positions.`,
    keyStats: {
      winRate: `${winRate}%`,
      avgHoldDays: '28 days',
      bestSector: topSector,
      worstTrait: 'Hold Discipline',
      signaturePattern: `${topSector} concentration -- ${trades.filter(t => t.sector === topSector).length} trades in sector`,
    },
    traits: {
      entry_timing: 68,
      hold_discipline: 55,
      position_sizing: 62,
      conviction_accuracy: Math.min(95, Math.max(20, winRate)),
      risk_management: 58,
      sector_focus: 78,
      drawdown_resilience: 60,
      thesis_quality: 65,
    },
    recommendations: [
      {
        priority: 'high' as const,
        title: 'Diversify sector exposure',
        body: `Your portfolio is heavily concentrated in ${topSector}. Consider allocating to uncorrelated sectors to reduce drawdown risk during sector-specific downturns.`,
        actionLabel: 'Review',
        impact: 'Risk reduction',
      },
      {
        priority: 'medium' as const,
        title: 'Improve hold discipline',
        body: 'Several positions were closed within days of entry. Set target prices before entering and give trades more room to develop.',
        actionLabel: 'Apply',
        impact: '+$2,000 estimated',
      },
      {
        priority: 'low' as const,
        title: 'Standardize position sizing',
        body: 'Position sizes vary significantly. Consider using a fixed percentage of portfolio (2-5%) per trade for more consistent risk management.',
        actionLabel: 'Consider',
        impact: 'Better risk-adjusted returns',
      },
    ],
  }
}
