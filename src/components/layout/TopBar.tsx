"use client";

import { Search, Bell } from "lucide-react";
import { currentUser } from "@/lib/mock-data";

export default function TopBar() {
  return (
    <header className="h-14 border-b border-border bg-surface flex items-center justify-between px-6">
      <div className="flex items-center gap-4">
        <span className="text-sm text-text-tertiary font-medium lg:hidden">
          Yabo
        </span>
      </div>

      <div className="flex-1 max-w-md mx-auto">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-tertiary" />
          <input
            type="text"
            placeholder="Search traders, tickers, theses..."
            className="w-full pl-9 pr-4 py-2 rounded-lg bg-background border border-border-light
              text-sm text-text-primary placeholder:text-text-tertiary
              focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20
              transition-all duration-150"
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button className="relative p-2 rounded-lg hover:bg-surface-hover transition-colors">
          <Bell className="w-4.5 h-4.5 text-text-secondary" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-accent" />
        </button>

        <button className="flex items-center gap-2 pl-2 pr-3 py-1.5 rounded-lg hover:bg-surface-hover transition-colors">
          <div className="w-7 h-7 rounded-full bg-accent flex items-center justify-center">
            <span className="text-xs font-semibold text-white">AT</span>
          </div>
          <span className="text-sm font-medium text-text-primary hidden sm:block">
            Anton
          </span>
        </button>
      </div>
    </header>
  );
}
