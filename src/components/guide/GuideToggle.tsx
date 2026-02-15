"use client";

import { BookOpen } from "lucide-react";

interface GuideToggleProps {
  active: boolean;
  onToggle: () => void;
}

export default function GuideToggle({ active, onToggle }: GuideToggleProps) {
  return (
    <button
      onClick={onToggle}
      className={`
        fixed bottom-20 left-4 md:bottom-4 z-50
        flex items-center gap-2 px-3.5 py-2 rounded-full
        text-[11px] font-semibold uppercase tracking-wider font-body
        transition-all duration-200
        ${
          active
            ? "bg-teal/[0.08] border border-teal text-teal"
            : "bg-surface border border-border text-teal hover:bg-surface-hover"
        }
      `}
    >
      <BookOpen className="w-4 h-4" />
      Guide
    </button>
  );
}
