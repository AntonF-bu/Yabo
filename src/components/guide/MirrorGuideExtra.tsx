"use client";

import { mirrorAnalysisList } from "@/lib/guide-content";

export default function MirrorGuideExtra() {
  return (
    <div>
      <p className="text-xs font-semibold text-text-ter uppercase tracking-wider font-body mb-2">
        What the AI analyzes
      </p>
      <div className="space-y-1.5">
        {mirrorAnalysisList.map((item) => (
          <div key={item} className="flex items-start gap-2.5">
            <span className="w-1.5 h-1.5 rounded-full bg-teal mt-1.5 shrink-0" />
            <p className="text-[13px] text-text-sec font-body">{item}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
