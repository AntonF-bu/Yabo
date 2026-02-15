"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { guideContent, GuideSection } from "@/lib/guide-content";

interface GuidePanelProps {
  section: string;
  children?: React.ReactNode;
}

export default function GuidePanel({ section, children }: GuidePanelProps) {
  const [dismissed, setDismissed] = useState(false);
  const content: GuideSection | undefined = guideContent[section];

  if (dismissed || !content) return null;

  return (
    <div className="mb-5 rounded-r-xl bg-bg border border-teal/60 border-l-[3px] border-l-teal p-5 pr-10 relative animate-fade-up">
      <button
        onClick={() => setDismissed(true)}
        className="absolute top-4 right-4 text-text-ter hover:text-text-sec transition-colors"
      >
        <X className="w-3.5 h-3.5" />
      </button>

      <p className="text-[10px] font-semibold uppercase tracking-[2px] text-teal font-body mb-2">
        GUIDE
      </p>
      <h4 className="font-display text-lg text-text mb-2">
        {content.title}
      </h4>
      <p className="text-sm text-text-sec leading-relaxed font-body">
        {content.body}
      </p>

      {children && <div className="mt-4">{children}</div>}

      <p className="text-[11px] text-text-ter italic font-body mt-4">
        {content.source}
      </p>
    </div>
  );
}
