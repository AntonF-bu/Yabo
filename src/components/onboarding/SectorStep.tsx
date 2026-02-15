"use client";

const sectors = [
  "Technology", "Healthcare", "Energy", "Financials",
  "Consumer", "Industrials", "Real Estate", "Crypto",
  "Semiconductors", "AI/ML", "Cannabis", "Clean Energy",
];

interface SectorStepProps {
  value: string[];
  onChange: (value: string[]) => void;
  onContinue: () => void;
}

export default function SectorStep({ value, onChange, onContinue }: SectorStepProps) {
  const toggle = (sector: string) => {
    if (value.includes(sector)) {
      onChange(value.filter((s) => s !== sector));
    } else {
      onChange([...value, sector]);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-6">
      <h2 className="font-display italic text-[32px] text-text text-center">
        What sectors do you follow?
      </h2>
      <p className="text-sm text-text-sec font-body text-center mt-2 mb-8">
        Pick as many as you want. This seeds your watchlist.
      </p>

      <div className="flex flex-wrap justify-center gap-2.5">
        {sectors.map((sector) => {
          const isSelected = value.includes(sector);
          return (
            <button
              key={sector}
              onClick={() => toggle(sector)}
              className={`px-4 py-2 rounded-lg text-sm font-medium font-body transition-all duration-200
                ${isSelected
                  ? "bg-teal-light border border-teal text-teal"
                  : "bg-surface border border-border text-text-sec hover:border-border-accent"
                }`}
            >
              {sector}
            </button>
          );
        })}
      </div>

      <div className="flex justify-center mt-10">
        <button
          onClick={onContinue}
          disabled={value.length === 0}
          className={`px-10 py-3.5 rounded-full text-sm font-semibold font-body transition-all
            ${value.length > 0
              ? "bg-teal text-bg hover:shadow-[0_0_24px_rgba(0,191,166,0.3)]"
              : "bg-border text-text-ter cursor-not-allowed"
            }`}
        >
          Continue
        </button>
      </div>
    </div>
  );
}
