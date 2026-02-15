"use client";

import { ImportedTrade } from "@/types";
import { TrendingUp, TrendingDown, Hash, Calendar, DollarSign } from "lucide-react";

interface ImportPreviewProps {
  trades: ImportedTrade[];
}

export default function ImportPreview({ trades }: ImportPreviewProps) {
  const buys = trades.filter((t) => t.action === "buy");
  const sells = trades.filter((t) => t.action === "sell");
  const uniqueTickers = Array.from(new Set(trades.map((t) => t.ticker)));
  const uniqueSectors = Array.from(new Set(trades.map((t) => t.sector).filter(Boolean)));
  const dateRange =
    trades.length > 0
      ? {
          from: trades.reduce((a, b) => (a.date < b.date ? a : b)).date,
          to: trades.reduce((a, b) => (a.date > b.date ? a : b)).date,
        }
      : null;

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-surface rounded-xl border border-border p-4">
          <div className="flex items-center gap-2 mb-1">
            <Hash className="w-3.5 h-3.5 text-text-tertiary" />
            <span className="text-[10px] text-text-tertiary uppercase tracking-wider font-semibold">
              Total Trades
            </span>
          </div>
          <p className="font-mono text-2xl font-bold text-text-primary">{trades.length}</p>
        </div>

        <div className="bg-surface rounded-xl border border-border p-4">
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp className="w-3.5 h-3.5 text-gain" />
            <span className="text-[10px] text-text-tertiary uppercase tracking-wider font-semibold">
              Buys / Sells
            </span>
          </div>
          <p className="font-mono text-2xl font-bold text-text-primary">
            <span className="text-gain">{buys.length}</span>
            <span className="text-text-tertiary mx-1">/</span>
            <span className="text-loss">{sells.length}</span>
          </p>
        </div>

        <div className="bg-surface rounded-xl border border-border p-4">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-3.5 h-3.5 text-text-tertiary" />
            <span className="text-[10px] text-text-tertiary uppercase tracking-wider font-semibold">
              Tickers
            </span>
          </div>
          <p className="font-mono text-2xl font-bold text-text-primary">{uniqueTickers.length}</p>
        </div>

        <div className="bg-surface rounded-xl border border-border p-4">
          <div className="flex items-center gap-2 mb-1">
            <Calendar className="w-3.5 h-3.5 text-text-tertiary" />
            <span className="text-[10px] text-text-tertiary uppercase tracking-wider font-semibold">
              Date Range
            </span>
          </div>
          <p className="font-mono text-sm font-bold text-text-primary">
            {dateRange ? `${dateRange.from} to ${dateRange.to}` : "-"}
          </p>
        </div>
      </div>

      {/* Sector Breakdown */}
      {uniqueSectors.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-3">
            Sectors Detected
          </p>
          <div className="flex flex-wrap gap-2">
            {uniqueSectors.map((sector) => {
              const count = trades.filter((t) => t.sector === sector).length;
              return (
                <span
                  key={sector}
                  className="px-3 py-1.5 rounded-lg bg-surface-hover text-xs font-medium text-text-secondary"
                >
                  {sector}{" "}
                  <span className="font-mono text-text-tertiary ml-1">{count}</span>
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* Trade Table */}
      <div>
        <p className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-3">
          Parsed Trades ({trades.length})
        </p>
        <div className="overflow-x-auto rounded-lg border border-border max-h-[400px] overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-surface-hover">
              <tr className="border-b border-border-light">
                <th className="px-3 py-2 text-left text-text-tertiary font-semibold">Date</th>
                <th className="px-3 py-2 text-left text-text-tertiary font-semibold">Ticker</th>
                <th className="px-3 py-2 text-left text-text-tertiary font-semibold">Action</th>
                <th className="px-3 py-2 text-right text-text-tertiary font-semibold">Qty</th>
                <th className="px-3 py-2 text-right text-text-tertiary font-semibold">Price</th>
                <th className="px-3 py-2 text-right text-text-tertiary font-semibold">Total</th>
                <th className="px-3 py-2 text-left text-text-tertiary font-semibold">Sector</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((trade, i) => (
                <tr
                  key={i}
                  className="border-b border-border-light last:border-b-0 hover:bg-surface-hover/50"
                >
                  <td className="px-3 py-2 font-mono text-text-secondary">{trade.date}</td>
                  <td className="px-3 py-2 font-mono font-semibold text-text-primary">
                    {trade.ticker}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                        trade.action === "buy"
                          ? "bg-gain-light text-gain"
                          : "bg-loss-light text-loss"
                      }`}
                    >
                      {trade.action === "buy" ? (
                        <TrendingUp className="w-2.5 h-2.5" />
                      ) : (
                        <TrendingDown className="w-2.5 h-2.5" />
                      )}
                      {trade.action.toUpperCase()}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-mono text-right text-text-secondary">
                    {trade.quantity}
                  </td>
                  <td className="px-3 py-2 font-mono text-right text-text-secondary">
                    ${trade.price.toFixed(2)}
                  </td>
                  <td className="px-3 py-2 font-mono text-right text-text-primary font-medium">
                    ${trade.total.toFixed(2)}
                  </td>
                  <td className="px-3 py-2 text-text-tertiary">{trade.sector || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
