import { ImportedTrade, ComputedPortfolio } from "@/types";

const TRADES_KEY = "yabo_imported_trades";
const PORTFOLIO_KEY = "yabo_computed_portfolio";

export function saveTrades(trades: ImportedTrade[]): void {
  try {
    localStorage.setItem(TRADES_KEY, JSON.stringify(trades));
  } catch {
    console.error("Failed to save trades to localStorage");
  }
}

export function loadTrades(): ImportedTrade[] | null {
  try {
    const raw = localStorage.getItem(TRADES_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as ImportedTrade[];
  } catch {
    return null;
  }
}

export function savePortfolio(portfolio: ComputedPortfolio): void {
  try {
    localStorage.setItem(PORTFOLIO_KEY, JSON.stringify(portfolio));
  } catch {
    console.error("Failed to save portfolio to localStorage");
  }
}

export function loadPortfolio(): ComputedPortfolio | null {
  try {
    const raw = localStorage.getItem(PORTFOLIO_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as ComputedPortfolio;
  } catch {
    return null;
  }
}

export function clearImportedData(): void {
  try {
    localStorage.removeItem(TRADES_KEY);
    localStorage.removeItem(PORTFOLIO_KEY);
  } catch {
    console.error("Failed to clear imported data");
  }
}

export function hasImportedData(): boolean {
  try {
    return localStorage.getItem(TRADES_KEY) !== null;
  } catch {
    return false;
  }
}
