"use client";

import { Search } from "lucide-react";

export default function TopBar() {
  return (
    <header className="h-14 border-b border-border bg-surface flex items-center justify-between px-6">
      <div className="flex items-center gap-4">
        <span className="text-sm text-text-ter font-medium lg:hidden font-body">
          Yabo
        </span>
      </div>

      <div className="flex-1 max-w-md mx-auto">
        <div className="relative" style={{ opacity: 0.35, pointerEvents: "none" }}>
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-ter" />
          <input
            type="text"
            placeholder="Search coming soon..."
            disabled
            className="w-full pl-9 pr-4 py-2 rounded-lg bg-bg border border-border
              text-sm text-text placeholder:text-text-ter font-body
              cursor-not-allowed"
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* User button is in the sidebar via Clerk UserButton */}
      </div>
    </header>
  );
}
