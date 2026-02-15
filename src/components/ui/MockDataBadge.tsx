"use client";

import { FlaskConical } from "lucide-react";

export default function MockDataBadge({ label = "Preview data" }: { label?: string }) {
  return (
    <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-text-muted/40 border border-border">
      <FlaskConical className="w-3 h-3 text-text-ter" />
      <span className="font-mono text-[10px] text-text-ter uppercase tracking-[1px]">
        {label}
      </span>
    </div>
  );
}
