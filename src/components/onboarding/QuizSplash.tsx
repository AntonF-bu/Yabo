"use client";

import LiveDot from "@/components/ui/LiveDot";

interface QuizSplashProps {
  onBegin: () => void;
}

export default function QuizSplash({ onBegin }: QuizSplashProps) {
  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-6">
      <div className="max-w-lg text-center animate-fade-in">
        <div className="flex items-center justify-center gap-2 mb-8">
          <LiveDot />
          <p className="text-[11px] font-mono font-medium tracking-[4px] text-teal uppercase">
            THE PROVING GROUND
          </p>
        </div>

        <h1 className="font-display italic text-5xl sm:text-[56px] text-text leading-[1.1]">
          Let&apos;s see what you&apos;ve got.
        </h1>

        <p className="mt-6 text-base text-text-sec font-body leading-relaxed">
          60 seconds. 5 questions. Your Trading DNA awaits.
        </p>

        <button
          onClick={onBegin}
          className="mt-10 px-10 py-4 rounded-full bg-teal text-bg font-semibold text-sm font-body hover:shadow-[0_0_24px_rgba(0,191,166,0.3)] transition-all"
        >
          Begin
        </button>
      </div>
    </div>
  );
}
