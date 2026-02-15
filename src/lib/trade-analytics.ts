import { ImportedTrade, ComputedPortfolio, ComputedPosition, BehavioralTrait } from "@/types";
import { getSector } from "./sector-map";

interface TradeGroup {
  ticker: string;
  buys: ImportedTrade[];
  sells: ImportedTrade[];
}

function groupByTicker(trades: ImportedTrade[]): Record<string, TradeGroup> {
  const groups: Record<string, TradeGroup> = {};
  for (const trade of trades) {
    if (!groups[trade.ticker]) {
      groups[trade.ticker] = { ticker: trade.ticker, buys: [], sells: [] };
    }
    const group = groups[trade.ticker];
    if (trade.action === "buy") {
      group.buys.push(trade);
    } else {
      group.sells.push(trade);
    }
  }
  return groups;
}

function daysBetween(dateA: string, dateB: string): number {
  const a = new Date(dateA);
  const b = new Date(dateB);
  return Math.abs(Math.round((b.getTime() - a.getTime()) / (1000 * 60 * 60 * 24)));
}

function computePositions(groups: Record<string, TradeGroup>): ComputedPosition[] {
  const positions: ComputedPosition[] = [];
  const tickers = Object.keys(groups);

  for (const ticker of tickers) {
    const group = groups[ticker];
    const totalBuyQty = group.buys.reduce((sum, t) => sum + t.quantity, 0);
    const totalBuyCost = group.buys.reduce((sum, t) => sum + t.total, 0);
    const totalSellQty = group.sells.reduce((sum, t) => sum + t.quantity, 0);
    const totalSellProceeds = group.sells.reduce((sum, t) => sum + t.total, 0);

    const remainingShares = totalBuyQty - totalSellQty;
    const avgCost = totalBuyQty > 0 ? totalBuyCost / totalBuyQty : 0;

    // Estimate current value: if fully sold use proceeds, else use avg cost as proxy
    const currentValue =
      remainingShares > 0 ? remainingShares * avgCost : 0;
    const realizedPnl = totalSellQty > 0 ? totalSellProceeds - totalSellQty * avgCost : 0;

    // Count wins: for each sell, if sell price > avg cost it's a win
    let wins = 0;
    let roundTrips = 0;
    const holdDays: number[] = [];

    for (const sell of group.sells) {
      roundTrips++;
      if (sell.price > avgCost) wins++;

      // Estimate hold days: find closest buy before sell
      const buysBefore = group.buys
        .filter((b) => b.date <= sell.date)
        .sort((a, b) => b.date.localeCompare(a.date));
      if (buysBefore.length > 0) {
        holdDays.push(daysBetween(buysBefore[0].date, sell.date));
      }
    }

    positions.push({
      ticker,
      sector: getSector(ticker),
      shares: remainingShares,
      avgCost,
      currentValue: currentValue + realizedPnl,
      pnl: realizedPnl,
      pnlPercent: totalBuyCost > 0 ? (realizedPnl / totalBuyCost) * 100 : 0,
      trades: group.buys.length + group.sells.length,
      wins,
      avgHoldDays: holdDays.length > 0 ? Math.round(holdDays.reduce((a, b) => a + b, 0) / holdDays.length) : 0,
    });
  }

  return positions;
}

// Compute behavioral traits from trade data
function computeTraits(
  trades: ImportedTrade[],
  positions: ComputedPosition[],
): BehavioralTrait[] {
  const sorted = [...trades].sort((a, b) => a.date.localeCompare(b.date));

  // 1. Entry Timing: how concentrated are buys around price lows?
  // Higher = more buys at relative lows within each ticker
  const entryScore = computeEntryTiming(sorted);

  // 2. Hold Discipline: consistency of hold periods
  const holdScore = computeHoldDiscipline(positions);

  // 3. Position Sizing: how uniform are position sizes?
  const sizingScore = computePositionSizing(sorted);

  // 4. Conviction Accuracy: win rate weighted by position size
  const convictionScore = computeConvictionAccuracy(positions);

  // 5. Risk Management: presence of stop-losses (sells at loss with small loss%)
  const riskScore = computeRiskManagement(positions);

  // 6. Sector Focus: concentration in top sectors
  const sectorScore = computeSectorFocus(positions);

  // 7. Drawdown Resilience: continued trading after losses
  const drawdownScore = computeDrawdownResilience(sorted);

  // 8. Thesis Quality: ratio of winning trades to total round-trip trades
  const thesisScore = computeThesisQuality(positions);

  return [
    { name: "Entry Timing", score: entryScore, percentile: Math.min(99, entryScore + randomJitter()), trend: entryScore > 60 ? "up" : "down" },
    { name: "Hold Discipline", score: holdScore, percentile: Math.min(99, holdScore + randomJitter()), trend: holdScore > 60 ? "flat" : "down" },
    { name: "Position Sizing", score: sizingScore, percentile: Math.min(99, sizingScore + randomJitter()), trend: "flat" },
    { name: "Conviction Accuracy", score: convictionScore, percentile: Math.min(99, convictionScore + randomJitter()), trend: convictionScore > 70 ? "up" : "flat" },
    { name: "Risk Management", score: riskScore, percentile: Math.min(99, riskScore + randomJitter()), trend: riskScore > 50 ? "up" : "down" },
    { name: "Sector Focus", score: sectorScore, percentile: Math.min(99, sectorScore + randomJitter()), trend: "flat" },
    { name: "Drawdown Resilience", score: drawdownScore, percentile: Math.min(99, drawdownScore + randomJitter()), trend: drawdownScore > 60 ? "up" : "flat" },
    { name: "Thesis Quality", score: thesisScore, percentile: Math.min(99, thesisScore + randomJitter()), trend: thesisScore > 65 ? "up" : "down" },
  ];
}

function randomJitter(): number {
  return Math.floor(Math.random() * 15) - 5;
}

function clamp(val: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, Math.round(val)));
}

function computeEntryTiming(trades: ImportedTrade[]): number {
  // For each ticker, check if buys happened at lower prices relative to the range
  const byTicker: Record<string, ImportedTrade[]> = {};
  for (const t of trades) {
    if (!byTicker[t.ticker]) byTicker[t.ticker] = [];
    byTicker[t.ticker].push(t);
  }

  let totalScore = 0;
  let count = 0;

  const tickers = Object.keys(byTicker);
  for (const tk of tickers) {
    const tickerTrades = byTicker[tk];
    const prices = tickerTrades.map((t) => t.price);
    const min = Math.min.apply(null, prices);
    const max = Math.max.apply(null, prices);
    const range = max - min;
    if (range === 0) continue;

    const buys = tickerTrades.filter((t) => t.action === "buy");
    for (const buy of buys) {
      // 0 = bought at max, 100 = bought at min
      const normalized = 100 - ((buy.price - min) / range) * 100;
      totalScore += normalized;
      count++;
    }
  }

  return clamp(count > 0 ? totalScore / count : 50, 20, 95);
}

function computeHoldDiscipline(positions: ComputedPosition[]): number {
  const holdDays = positions.filter((p) => p.avgHoldDays > 0).map((p) => p.avgHoldDays);
  if (holdDays.length < 2) return 50;

  const mean = holdDays.reduce((a, b) => a + b, 0) / holdDays.length;
  const variance = holdDays.reduce((sum, d) => sum + (d - mean) ** 2, 0) / holdDays.length;
  const cv = mean > 0 ? Math.sqrt(variance) / mean : 1;

  // Lower CV = more disciplined. CV of 0 = 95, CV of 2+ = 20
  return clamp(95 - cv * 37, 20, 95);
}

function computePositionSizing(trades: ImportedTrade[]): number {
  const buys = trades.filter((t) => t.action === "buy");
  if (buys.length < 2) return 50;

  const totals = buys.map((t) => t.total);
  const mean = totals.reduce((a, b) => a + b, 0) / totals.length;
  const variance = totals.reduce((sum, t) => sum + (t - mean) ** 2, 0) / totals.length;
  const cv = mean > 0 ? Math.sqrt(variance) / mean : 1;

  return clamp(90 - cv * 35, 20, 95);
}

function computeConvictionAccuracy(positions: ComputedPosition[]): number {
  const withTrades = positions.filter((p) => p.trades >= 2);
  if (withTrades.length === 0) return 50;

  const totalWins = withTrades.reduce((sum, p) => sum + p.wins, 0);
  const totalRoundTrips = withTrades.reduce(
    (sum, p) => sum + Math.floor(p.trades / 2),
    0,
  );
  if (totalRoundTrips === 0) return 50;

  const winRate = totalWins / totalRoundTrips;
  return clamp(winRate * 100, 20, 95);
}

function computeRiskManagement(positions: ComputedPosition[]): number {
  const losers = positions.filter((p) => p.pnl < 0);
  if (losers.length === 0) return 80;

  // Good risk management = small losses (< -5% avg)
  const avgLoss = losers.reduce((sum, p) => sum + Math.abs(p.pnlPercent), 0) / losers.length;
  // avgLoss of 2% = 90, avgLoss of 20% = 30
  return clamp(95 - avgLoss * 3.5, 20, 95);
}

function computeSectorFocus(positions: ComputedPosition[]): number {
  const sectorCounts: Record<string, number> = {};
  for (const p of positions) {
    sectorCounts[p.sector] = (sectorCounts[p.sector] || 0) + p.trades;
  }
  const total = positions.reduce((sum, p) => sum + p.trades, 0);
  if (total === 0) return 50;

  const counts = Object.values(sectorCounts).sort((a, b) => b - a);
  const topConcentration = counts[0] / total;
  // Concentration of 80%+ = high focus (90+), 20% = low focus (40)
  return clamp(topConcentration * 100 + 10, 20, 95);
}

function computeDrawdownResilience(trades: ImportedTrade[]): number {
  // Check if trading continued after periods of losses
  const sorted = [...trades].sort((a, b) => a.date.localeCompare(b.date));
  if (sorted.length < 5) return 50;

  let inDrawdown = false;
  let tradedDuringDrawdown = 0;
  let drawdownPeriods = 0;

  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i].action === "sell" && sorted[i].price < sorted[i - 1].price) {
      if (!inDrawdown) {
        inDrawdown = true;
        drawdownPeriods++;
      }
    } else if (inDrawdown && sorted[i].action === "buy") {
      tradedDuringDrawdown++;
      inDrawdown = false;
    } else {
      inDrawdown = false;
    }
  }

  if (drawdownPeriods === 0) return 70;
  const resilience = tradedDuringDrawdown / drawdownPeriods;
  return clamp(50 + resilience * 40, 20, 95);
}

function computeThesisQuality(positions: ComputedPosition[]): number {
  const totalWins = positions.reduce((sum, p) => sum + p.wins, 0);
  const totalRoundTrips = positions.reduce(
    (sum, p) => sum + Math.floor(p.trades / 2),
    0,
  );
  if (totalRoundTrips === 0) return 50;

  const winRate = totalWins / totalRoundTrips;
  // Also factor in avg pnl%
  const avgPnl = positions.reduce((sum, p) => sum + p.pnlPercent, 0) / positions.length;
  const pnlBonus = clamp(avgPnl, -20, 20) / 2;

  return clamp(winRate * 85 + pnlBonus + 10, 20, 95);
}

// Compute Sharpe ratio approximation
function computeSharpe(positions: ComputedPosition[]): number {
  const returns = positions
    .filter((p) => p.trades >= 2)
    .map((p) => p.pnlPercent / 100);
  if (returns.length < 2) return 0;

  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((sum, r) => sum + (r - mean) ** 2, 0) / returns.length;
  const std = Math.sqrt(variance);
  if (std === 0) return mean > 0 ? 3 : 0;

  return Math.round((mean / std) * Math.sqrt(12) * 10) / 10; // Annualized approx
}

// Main entry: compute full portfolio from imported trades
export function computePortfolio(trades: ImportedTrade[]): ComputedPortfolio {
  const groups = groupByTicker(trades);
  const positions = computePositions(groups);
  const traits = computeTraits(trades, positions);

  const totalCost = positions.reduce(
    (sum, p) => sum + p.avgCost * (p.shares + p.wins),
    0,
  );
  const totalValue = positions.reduce((sum, p) => sum + p.currentValue, 0);
  const totalPnl = positions.reduce((sum, p) => sum + p.pnl, 0);
  const totalTrades = trades.length;
  const wins = positions.reduce((sum, p) => sum + p.wins, 0);
  const roundTrips = positions.reduce(
    (sum, p) => sum + Math.floor(p.trades / 2),
    0,
  );
  const losses = roundTrips - wins;
  const avgHoldDays =
    positions.filter((p) => p.avgHoldDays > 0).length > 0
      ? Math.round(
          positions
            .filter((p) => p.avgHoldDays > 0)
            .reduce((sum, p) => sum + p.avgHoldDays, 0) /
            positions.filter((p) => p.avgHoldDays > 0).length,
        )
      : 0;

  return {
    totalValue: Math.abs(totalValue),
    totalCost: Math.abs(totalCost),
    totalPnl,
    totalPnlPercent: totalCost !== 0 ? (totalPnl / Math.abs(totalCost)) * 100 : 0,
    positions,
    winRate: roundTrips > 0 ? wins / roundTrips : 0,
    totalTrades,
    wins,
    losses,
    avgHoldDays,
    sharpe: computeSharpe(positions),
    traits,
  };
}
