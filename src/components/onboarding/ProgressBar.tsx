"use client";

interface ProgressBarProps {
  current: number;
  total: number;
}

export default function ProgressBar({ current, total }: ProgressBarProps) {
  const pct = (current / total) * 100;

  return (
    <div className="fixed top-0 left-0 right-0 z-50">
      <div className="h-1 bg-border w-full">
        <div
          className="h-full bg-teal transition-all duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="absolute top-3 right-6">
        <span className="text-[11px] font-mono text-text-ter">
          {current} of {total}
        </span>
      </div>
    </div>
  );
}
