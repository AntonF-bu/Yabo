"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, X, BookOpen } from "lucide-react";
import { searchTickers, SearchResult } from "@/lib/market-data";

interface TopBarProps {
  guideActive?: boolean;
  onToggleGuide?: () => void;
}

export default function TopBar({ guideActive, onToggleGuide }: TopBarProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSearch = useCallback(async (q: string) => {
    if (q.length < 1) {
      setResults([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    try {
      const res = await searchTickers(q);
      setResults(res);
      setOpen(res.length > 0);
    } catch {
      setResults([]);
    }
    setLoading(false);
  }, []);

  const handleChange = (val: string) => {
    setQuery(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => handleSearch(val), 300);
  };

  const handleSelect = (symbol: string) => {
    setQuery("");
    setResults([]);
    setOpen(false);
    router.push(`/dashboard/ticker/${symbol}`);
  };

  const handleClear = () => {
    setQuery("");
    setResults([]);
    setOpen(false);
    inputRef.current?.focus();
  };

  // Close on click outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Close on escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        inputRef.current?.blur();
      }
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, []);

  return (
    <header className="h-14 border-b border-border bg-bg flex items-center justify-between px-6">
      <div className="flex items-center gap-4">
        <span className="text-sm text-text-ter font-medium lg:hidden font-body">
          Yabo
        </span>
      </div>

      <div className="flex-1 max-w-md mx-auto" ref={containerRef}>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-ter" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => handleChange(e.target.value)}
            onFocus={() => { if (results.length > 0) setOpen(true); }}
            placeholder="Search tickers..."
            className="w-full pl-9 pr-8 py-2 rounded-[10px] bg-surface border border-border
              text-sm text-text placeholder:text-text-ter font-body
              focus:border-border-hover focus:shadow-sm focus:outline-none transition-all"
          />
          {query && (
            <button
              onClick={handleClear}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-text-ter hover:text-text transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}

          {/* Dropdown */}
          {open && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-surface border border-border rounded-xl shadow-lg overflow-hidden z-50">
              {results.map((r) => (
                <button
                  key={r.symbol}
                  onClick={() => handleSelect(r.symbol)}
                  className="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface-hover transition-colors text-left"
                >
                  <span className="font-mono text-sm font-bold text-text">{r.displaySymbol}</span>
                  <span className="text-xs text-text-sec font-body truncate">{r.description}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3">
        {onToggleGuide && (
          <button
            onClick={onToggleGuide}
            className={`
              flex items-center gap-1.5 px-3 py-1.5 rounded-full
              text-[11px] font-semibold uppercase tracking-wider font-body
              transition-all duration-200
              ${
                guideActive
                  ? "bg-teal/[0.08] border border-teal text-teal"
                  : "border border-border text-text-ter hover:text-teal hover:border-teal/30"
              }
            `}
          >
            <BookOpen className="w-3.5 h-3.5" />
            Guide
          </button>
        )}
      </div>
    </header>
  );
}
