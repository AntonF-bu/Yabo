export interface Portfolio {
  cashBalance: number
  totalValue: number
  startingCapital: number
  positions: PortfolioPosition[]
  peakValue: number
}

export interface PortfolioPosition {
  ticker: string
  shares: number
  avgCost: number
  currentPrice: number
  sector: string
  marketValue: number
}

export interface TradeOrder {
  ticker: string
  side: 'buy' | 'sell'
  quantity: number
  price: number
  sector: string
}

export interface RuleCheck {
  rule: string
  passed: boolean
  message: string
  current: string
  limit: string
  severity: 'error' | 'warning'
}

export function validateTrade(order: TradeOrder, portfolio: Portfolio): RuleCheck[] {
  const checks: RuleCheck[] = []
  const orderValue = order.quantity * order.price

  if (order.side === 'buy') {
    // 1. Sufficient funds
    if (orderValue > portfolio.cashBalance) {
      checks.push({
        rule: 'Insufficient Funds',
        passed: false,
        message: `Order costs $${orderValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} but you have $${portfolio.cashBalance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} cash.`,
        current: `$${portfolio.cashBalance.toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
        limit: `$${orderValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
        severity: 'error',
      })
    }

    // 2. Max Single Position: 15%
    const existingPosition = portfolio.positions.find(p => p.ticker === order.ticker)
    const existingValue = existingPosition ? existingPosition.marketValue : 0
    const newPositionValue = existingValue + orderValue
    const newTotalValue = portfolio.totalValue
    const positionPct = (newPositionValue / newTotalValue) * 100

    if (positionPct > 15) {
      checks.push({
        rule: 'Max Single Position (15%)',
        passed: false,
        message: `This would put ${order.ticker} at ${positionPct.toFixed(1)}% of your portfolio, exceeding the 15% limit.`,
        current: `${positionPct.toFixed(1)}%`,
        limit: '15%',
        severity: 'error',
      })
    } else if (positionPct > 12) {
      checks.push({
        rule: 'Max Single Position (15%)',
        passed: true,
        message: `${order.ticker} would be ${positionPct.toFixed(1)}% of portfolio. Approaching 15% limit.`,
        current: `${positionPct.toFixed(1)}%`,
        limit: '15%',
        severity: 'warning',
      })
    }

    // 3. Sector Limit: 40%
    const sectorPositions = portfolio.positions.filter(p => p.sector === order.sector)
    const sectorValue = sectorPositions.reduce((sum, p) => sum + p.marketValue, 0)
    const newSectorValue = sectorValue + orderValue
    const sectorPct = (newSectorValue / newTotalValue) * 100

    if (sectorPct > 40) {
      checks.push({
        rule: 'Sector Limit (40%)',
        passed: false,
        message: `${order.sector} sector would be ${sectorPct.toFixed(1)}%, exceeding the 40% limit.`,
        current: `${sectorPct.toFixed(1)}%`,
        limit: '40%',
        severity: 'error',
      })
    } else if (sectorPct > 35) {
      checks.push({
        rule: 'Sector Limit (40%)',
        passed: true,
        message: `${order.sector} sector at ${sectorPct.toFixed(1)}%. Approaching 40% limit.`,
        current: `${sectorPct.toFixed(1)}%`,
        limit: '40%',
        severity: 'warning',
      })
    }

    // 4. Max Drawdown: 30%
    const drawdownPct = ((portfolio.peakValue - portfolio.totalValue) / portfolio.peakValue) * 100
    if (drawdownPct >= 30) {
      checks.push({
        rule: 'Max Drawdown (30%)',
        passed: false,
        message: `Portfolio in ${drawdownPct.toFixed(1)}% drawdown. Trading paused until recovery below 25%.`,
        current: `${drawdownPct.toFixed(1)}%`,
        limit: '30%',
        severity: 'error',
      })
    }
  }

  if (order.side === 'sell') {
    const position = portfolio.positions.find(p => p.ticker === order.ticker)
    if (!position || position.shares < order.quantity) {
      checks.push({
        rule: 'Insufficient Shares',
        passed: false,
        message: `You own ${position ? position.shares : 0} shares of ${order.ticker}.`,
        current: `${position ? position.shares : 0}`,
        limit: `${order.quantity}`,
        severity: 'error',
      })
    }

    // Minimum positions warning (5)
    if (position && order.quantity >= position.shares) {
      const remaining = portfolio.positions.filter(p => p.ticker !== order.ticker && p.shares > 0).length
      if (remaining < 5) {
        checks.push({
          rule: 'Minimum Positions (5)',
          passed: true,
          message: `Closing ${order.ticker} leaves ${remaining} positions. Minimum is 5.`,
          current: `${remaining}`,
          limit: '5',
          severity: 'warning',
        })
      }
    }
  }

  if (checks.length === 0) {
    checks.push({
      rule: 'All Rules',
      passed: true,
      message: 'Trade complies with all rules.',
      current: '',
      limit: '',
      severity: 'warning',
    })
  }

  return checks
}

export function calculateSlippage(price: number, side: 'buy' | 'sell'): number {
  const slippagePct = 0.0002
  const slippage = price * slippagePct
  return side === 'buy' ? price + slippage : price - slippage
}

export function calculateCommission(quantity: number): number {
  return Math.max(0.50, quantity * 0.01)
}
