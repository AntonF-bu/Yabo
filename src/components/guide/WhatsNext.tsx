"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { whatsNextPhases } from "@/lib/guide-content";

export default function WhatsNext() {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="mt-4">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-[13px] font-semibold text-teal font-body hover:text-teal/80 transition-colors"
      >
        {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        What&apos;s Coming Next
      </button>

      {expanded && (
        <div className="mt-4 space-y-3">
          {whatsNextPhases.map((phase) => (
            <div
              key={phase.title}
              className="bg-surface rounded-xl border border-border p-4"
            >
              <h5 className="font-display text-base text-text">
                {phase.title}
              </h5>
              <p className="text-xs text-teal font-body mt-0.5">{phase.timeline}</p>
              <ul className="mt-3 space-y-1.5">
                {phase.items.map((item) => (
                  <li key={item} className="text-[13px] text-text-sec font-body flex items-start gap-2">
                    <span className="text-text-ter mt-1 shrink-0">&ndash;</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
          <p className="text-[11px] text-text-ter italic font-body">
            Source: Pitch Deck, &quot;Phased Roadmap&quot; slide
          </p>
        </div>
      )}
    </div>
  );
}
