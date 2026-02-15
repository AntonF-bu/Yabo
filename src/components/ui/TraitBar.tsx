import { TrendingUp, TrendingDown, ArrowRight } from "lucide-react";

interface TraitBarProps {
  name: string;
  score: number;
  percentile: number;
  trend: "up" | "down" | "flat";
}

export default function TraitBar({ name, score, percentile, trend }: TraitBarProps) {
  const getBarColor = (s: number) => {
    if (s >= 70) return "#22A06B";
    if (s >= 50) return "#E85D26";
    return "#DE350B";
  };

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-text-primary w-40 shrink-0">{name}</span>
      <div className="flex-1 h-2 rounded-full bg-border-light overflow-hidden">
        <div
          className="h-full rounded-full animate-bar-fill"
          style={{
            width: `${score}%`,
            backgroundColor: getBarColor(score),
          }}
        />
      </div>
      <span className="font-mono text-sm font-semibold text-text-primary w-8 text-right">
        {score}
      </span>
      <span className="font-mono text-xs text-text-tertiary w-8">
        p{percentile}
      </span>
      <div className="w-4 shrink-0">
        {trend === "up" && <TrendingUp className="w-3.5 h-3.5 text-gain" />}
        {trend === "down" && <TrendingDown className="w-3.5 h-3.5 text-loss" />}
        {trend === "flat" && <ArrowRight className="w-3.5 h-3.5 text-text-tertiary" />}
      </div>
    </div>
  );
}
