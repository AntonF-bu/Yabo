"use client";

import { useState, useEffect, useCallback } from "react";
import { useUser } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, TrendingUp, TrendingDown, Loader2 } from "lucide-react";
import { getQuote, getStockProfile, getCandles, getTimeRange, Quote, StockProfile, CandlePoint } from "@/lib/market-data";
import { supabase } from "@/lib/supabase";
import { PortfolioPositionRow, TradeRow } from "@/hooks/usePortfolio";
import { usePortfolio } from "@/hooks/usePortfolio";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

const periods = ["1W", "1M", "3M", "6M", "1Y"];

function formatMarketCap(cap: number): string {
  if (!cap) return "N/A";
  if (cap >= 1e6) return `$${(cap / 1e6).toFixed(1)}T`;
  if (cap >= 1e3) return `$${(cap / 1e3).toFixed(1)}B`;
  return `$${cap.toFixed(0)}M`;
}

export default function TickerPage({ params }: { params: { symbol: string } }) {
  const symbol = params.symbol.toUpperCase();
  const { user } = useUser();
  const router = useRouter();
  const { positions: allPositions, trades: allTrades, cash, totalValue, refresh: refreshPortfolio } = usePortfolio();

  const [quote, setQuote] = useState<Quote | null>(null);
  const [profile, setProfile] = useState<StockProfile | null>(null);
  const [candles, setCandles] = useState<CandlePoint[]>([]);
  const [period, setPeriod] = useState("3M");
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);

  // User data for this ticker
  const position = allPositions.find((p) => p.ticker === symbol) || null;
  const tickerTrades = allTrades.filter((t) => t.ticker === symbol);

  // Fetch quote + profile
  useEffect(() => {
    let cancelled = false;
    async function fetchData() {
      setLoading(true);
      try {
        const [q, p] = await Promise.all([
          getQuote(symbol),
          getStockProfile(symbol).catch(() => null),
        ]);
        if (cancelled) return;
        setQuote(q);
        setProfile(p);
      } catch {
        // API error
      }
      if (!cancelled) setLoading(false);
    }
    fetchData();
    return () => { cancelled = true; };
  }, [symbol]);

  // Fetch candles (initial + period changes)
  useEffect(() => {
    let cancelled = false;
    async function fetchCandles() {
      setChartLoading(true);
      try {
        const { from, to } = getTimeRange(period);
        const c = await getCandles(symbol, "D", from, to);
        if (!cancelled) setCandles(c);
      } catch {
        // ignore
      }
      if (!cancelled) setChartLoading(false);
    }
    fetchCandles();
    return () => { cancelled = true; };
  }, [period, symbol]);

  // Auto-refresh quote every 15s
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const q = await getQuote(symbol);
        setQuote(q);
      } catch {
        // ignore
      }
    }, 15000);
    return () => clearInterval(interval);
  }, [symbol]);

  const isPositive = quote ? quote.d >= 0 : true;

  const handleOpenTrade = (side: "buy" | "sell") => {
    // Navigate back to dashboard with trade panel params
    router.push(`/dashboard?trade=${symbol}&side=${side}`);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-bg p-6">
        <div className="max-w-3xl mx-auto">
          <Link href="/dashboard" className="flex items-center gap-2 text-sm text-text-sec hover:text-text transition-colors font-body mb-8">
            <ArrowLeft className="w-4 h-4" />
            Back to Dashboard
          </Link>
          {/* Skeleton */}
          <div className="space-y-6 animate-pulse">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-full bg-surface-hover" />
              <div className="space-y-2">
                <div className="w-24 h-7 rounded bg-surface-hover" />
                <div className="w-40 h-4 rounded bg-surface-hover" />
              </div>
              <div className="ml-auto text-right space-y-2">
                <div className="w-32 h-10 rounded bg-surface-hover" />
                <div className="w-20 h-4 rounded bg-surface-hover ml-auto" />
              </div>
            </div>
            <div className="h-[300px] rounded-xl bg-surface-hover" />
            <div className="grid grid-cols-2 gap-3">
              {[1,2,3,4].map(i => <div key={i} className="h-20 rounded-xl bg-surface-hover" />)}
            </div>
          </div>
        </div>
      </div>
    );
  }

  const shares = position ? Number(position.shares) : 0;
  const avgCost = position ? Number(position.avg_cost) : 0;
  const currentPrice = quote?.c || 0;
  const marketValue = shares * currentPrice;
  const positionPnl = shares > 0 ? (currentPrice - avgCost) * shares : 0;
  const positionPnlPct = avgCost > 0 ? ((currentPrice - avgCost) / avgCost) * 100 : 0;
  const portfolioPct = totalValue > 0 ? (marketValue / totalValue) * 100 : 0;

  // Rules preview for buying 1 share
  const oneBuyValue = currentPrice;
  const newPositionPct = totalValue > 0 ? ((marketValue + oneBuyValue) / totalValue) * 100 : 0;
  const sectorPositions = allPositions.filter(p => p.sector === (position?.sector || profile?.finnhubIndustry || ""));
  const sectorValue = sectorPositions.reduce((s, p) => s + Number(p.shares) * Number(p.current_price), 0);
  const sectorPct = totalValue > 0 ? ((sectorValue + oneBuyValue) / totalValue) * 100 : 0;

  return (
    <div className="min-h-screen bg-bg p-6">
      <div className="max-w-3xl mx-auto">
        {/* Back */}
        <Link href="/dashboard" className="flex items-center gap-2 text-sm text-text-sec hover:text-text transition-colors font-body mb-6">
          <ArrowLeft className="w-4 h-4" />
          Back to Dashboard
        </Link>

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-4">
            {profile?.logo ? (
              <img src={profile.logo} alt={symbol} className="w-10 h-10 rounded-full object-cover border border-border" />
            ) : (
              <div className="w-10 h-10 rounded-full bg-surface-hover flex items-center justify-center">
                <span className="font-display text-lg text-text">{symbol[0]}</span>
              </div>
            )}
            <div>
              <div className="flex items-center gap-3">
                <h1 className="font-mono text-[28px] font-bold text-text">{symbol}</h1>
                {profile?.exchange && (
                  <span className="text-xs text-text-ter font-body">{profile.exchange}</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {profile?.name && (
                  <span className="text-base text-text-sec font-body">{profile.name}</span>
                )}
                {profile?.finnhubIndustry && (
                  <span className="px-2 py-0.5 rounded-lg bg-surface border border-border text-xs text-text-sec font-body">
                    {profile.finnhubIndustry}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="text-right">
            <div className="flex items-center gap-2 justify-end">
              <span className="font-display text-[42px] font-medium text-text leading-none">
                ${currentPrice.toFixed(2)}
              </span>
              <span className={`w-1.5 h-1.5 rounded-full ${isPositive ? "bg-green" : "bg-text-ter"}`} />
            </div>
            {quote && (
              <span className={`font-mono text-base font-semibold ${isPositive ? "text-green" : "text-red"}`}>
                {isPositive ? "+" : ""}${quote.d?.toFixed(2) || "0.00"} ({isPositive ? "+" : ""}{quote.dp?.toFixed(2) || "0.00"}%)
              </span>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3 mb-8">
          <button
            onClick={() => handleOpenTrade("buy")}
            className="flex-1 py-3 rounded-xl bg-text text-bg text-sm font-semibold font-body hover:bg-text/80 transition-colors flex items-center justify-center gap-2"
          >
            <TrendingUp className="w-4 h-4" />
            Buy {symbol}
          </button>
          {shares > 0 && (
            <button
              onClick={() => handleOpenTrade("sell")}
              className="flex-1 py-3 rounded-xl border border-border text-sm font-semibold text-text font-body hover:bg-surface-hover transition-colors flex items-center justify-center gap-2"
            >
              <TrendingDown className="w-4 h-4" />
              Sell {symbol}
            </button>
          )}
        </div>

        {/* Price Chart */}
        <div className="bg-surface rounded-xl border border-border p-5 mb-6">
          <div className="flex items-center gap-2 mb-4">
            {periods.map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold font-body transition-colors ${
                  period === p
                    ? "bg-text text-bg"
                    : "bg-bg text-text-sec hover:text-text"
                }`}
              >
                {p}
              </button>
            ))}
          </div>
          {chartLoading ? (
            <div className="h-[300px] flex items-center justify-center">
              <Loader2 className="w-5 h-5 text-text-ter animate-spin" />
            </div>
          ) : candles.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={candles}>
                <defs>
                  <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={isPositive ? "#4A8C6A" : "#C45A4A"} stopOpacity={0.15} />
                    <stop offset="95%" stopColor={isPositive ? "#4A8C6A" : "#C45A4A"} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: "#A09A94", fontFamily: "IBM Plex Mono" }}
                  axisLine={false}
                  tickLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "#A09A94", fontFamily: "IBM Plex Mono" }}
                  axisLine={false}
                  tickLine={false}
                  domain={["auto", "auto"]}
                  width={60}
                  tickFormatter={(v: number) => `$${v.toFixed(0)}`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#F3F0EA",
                    border: "1px solid #EDE9E3",
                    borderRadius: "8px",
                    fontSize: "12px",
                    fontFamily: "IBM Plex Mono",
                  }}
                  formatter={(value: number | undefined) => [`$${(value ?? 0).toFixed(2)}`, "Price"]}
                />
                <Area
                  type="monotone"
                  dataKey="close"
                  stroke={isPositive ? "#4A8C6A" : "#C45A4A"}
                  strokeWidth={2}
                  fill="url(#priceGrad)"
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[300px] flex items-center justify-center text-text-ter text-sm font-body">
              No chart data available
            </div>
          )}
        </div>

        {/* Key Stats */}
        {quote && (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
            {[
              { label: "Open", value: `$${quote.o?.toFixed(2) || "N/A"}` },
              { label: "Prev Close", value: `$${quote.pc?.toFixed(2) || "N/A"}` },
              { label: "Day High", value: `$${quote.h?.toFixed(2) || "N/A"}` },
              { label: "Day Low", value: `$${quote.l?.toFixed(2) || "N/A"}` },
              { label: "Market Cap", value: profile ? formatMarketCap(profile.marketCapitalization) : "N/A" },
              { label: "Industry", value: profile?.finnhubIndustry || "N/A" },
            ].map((stat) => (
              <div key={stat.label} className="bg-surface rounded-xl border border-border p-4">
                <p className="text-xs text-text-ter font-body">{stat.label}</p>
                <p className="font-mono text-[15px] font-medium text-text mt-1">{stat.value}</p>
              </div>
            ))}
          </div>
        )}

        {/* Your Position */}
        {shares > 0 && (
          <div className="mb-6">
            <h2 className="font-display text-xl text-text mb-3">Your Position</h2>
            <div className="bg-surface rounded-xl border border-border p-5">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-text-ter font-body">Shares</p>
                  <p className="font-mono text-2xl font-bold text-text">{shares}</p>
                </div>
                <div>
                  <p className="text-xs text-text-ter font-body">Avg Cost</p>
                  <p className="font-mono text-base text-text-sec">${avgCost.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-xs text-text-ter font-body">Market Value</p>
                  <p className="font-mono text-base text-text">${marketValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                </div>
                <div>
                  <p className="text-xs text-text-ter font-body">Total P&L</p>
                  <p className={`font-mono text-base font-semibold ${positionPnl >= 0 ? "text-green" : "text-red"}`}>
                    {positionPnl >= 0 ? "+" : ""}${positionPnl.toFixed(2)} ({positionPnlPct >= 0 ? "+" : ""}{positionPnlPct.toFixed(1)}%)
                  </p>
                </div>
              </div>
              {/* Portfolio % bar */}
              <div className="mt-4 pt-4 border-t border-border">
                <div className="flex items-center justify-between mb-1.5">
                  <p className="text-xs text-text-ter font-body">Portfolio allocation</p>
                  <p className="font-mono text-xs text-text-sec">{portfolioPct.toFixed(1)}% of portfolio</p>
                </div>
                <div className="relative h-2 rounded-full bg-bg overflow-hidden">
                  <div
                    className="absolute h-full rounded-full bg-teal transition-all duration-500"
                    style={{ width: `${Math.min(portfolioPct, 100)}%` }}
                  />
                  {/* 15% marker */}
                  <div className="absolute top-0 h-full w-px bg-text-ter" style={{ left: "15%" }} />
                </div>
                <p className="text-[10px] text-text-ter font-mono mt-1">15% max per position</p>
              </div>
              <div className="flex gap-3 mt-4">
                <button
                  onClick={() => handleOpenTrade("buy")}
                  className="flex-1 py-2.5 rounded-xl border border-border text-xs font-semibold text-text font-body hover:bg-surface-hover transition-colors"
                >
                  Buy More
                </button>
                <button
                  onClick={() => handleOpenTrade("sell")}
                  className="flex-1 py-2.5 rounded-xl border border-border text-xs font-semibold text-text font-body hover:bg-surface-hover transition-colors"
                >
                  Sell
                </button>
              </div>
            </div>
          </div>
        )}

        {/* No position */}
        {shares === 0 && (
          <div className="mb-6 bg-surface rounded-xl border border-border p-5 text-center">
            <p className="text-sm text-text-ter font-body">You don&apos;t hold {symbol}</p>
            <button
              onClick={() => handleOpenTrade("buy")}
              className="mt-3 px-6 py-2.5 rounded-xl bg-text text-bg text-sm font-semibold font-body hover:bg-text/80 transition-colors"
            >
              Buy {symbol}
            </button>
          </div>
        )}

        {/* Trade History */}
        {tickerTrades.length > 0 && (
          <div className="mb-6">
            <h2 className="font-display text-xl text-text mb-3">Your Trade History</h2>
            <div className="bg-surface rounded-xl border border-border overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border bg-surface-hover">
                    <th className="px-4 py-2.5 text-left text-text-ter font-semibold font-mono">Date</th>
                    <th className="px-4 py-2.5 text-left text-text-ter font-semibold font-mono">Side</th>
                    <th className="px-4 py-2.5 text-right text-text-ter font-semibold font-mono">Qty</th>
                    <th className="px-4 py-2.5 text-right text-text-ter font-semibold font-mono">Price</th>
                    <th className="px-4 py-2.5 text-right text-text-ter font-semibold font-mono">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {tickerTrades.map((t) => (
                    <tr key={t.id} className="border-b border-border last:border-b-0">
                      <td className="px-4 py-2.5 font-mono text-text-sec">
                        {new Date(t.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                          t.side === "buy" ? "bg-teal/10 text-teal" : "bg-red/10 text-red"
                        }`}>
                          {t.side}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 font-mono text-right text-text-sec">{t.quantity}</td>
                      <td className="px-4 py-2.5 font-mono text-right text-text-sec">${Number(t.price).toFixed(2)}</td>
                      <td className="px-4 py-2.5 font-mono text-right text-text font-medium">${Number(t.total_value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Company Info */}
        {profile?.name && (
          <div className="mb-6">
            <h2 className="font-display text-xl text-text mb-3">About {profile.name}</h2>
            <div className="bg-surface rounded-xl border border-border p-5">
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <p className="text-xs text-text-ter font-body">Industry</p>
                  <p className="text-sm text-text-sec font-body mt-0.5">{profile.finnhubIndustry || "N/A"}</p>
                </div>
                <div>
                  <p className="text-xs text-text-ter font-body">Market Cap</p>
                  <p className="font-mono text-sm text-text mt-0.5">{formatMarketCap(profile.marketCapitalization)}</p>
                </div>
                <div>
                  <p className="text-xs text-text-ter font-body">Exchange</p>
                  <p className="text-sm text-text-ter font-body mt-0.5">{profile.country} / {profile.exchange}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Rules Preview */}
        <div className="mb-10">
          <h3 className="text-[13px] font-semibold text-text font-body mb-3">Rules Preview</h3>
          <div className="bg-surface rounded-xl border border-border p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-sec font-body">Position size would be</span>
              <span className={`font-mono text-xs font-semibold ${newPositionPct > 15 ? "text-red" : newPositionPct > 12 ? "text-teal" : "text-green"}`}>
                {newPositionPct.toFixed(1)}% (limit: 15%)
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-sec font-body">Sector allocation would be</span>
              <span className={`font-mono text-xs font-semibold ${sectorPct > 40 ? "text-red" : sectorPct > 30 ? "text-teal" : "text-green"}`}>
                {sectorPct.toFixed(1)}% (limit: 40%)
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-sec font-body">Cash available</span>
              <span className="font-mono text-xs font-semibold text-text">${Math.round(cash).toLocaleString()}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
