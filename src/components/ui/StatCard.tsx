import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface StatCardProps {
  label: string;
  value: string | number;
  trend?: "up" | "down" | "flat";
  trendValue?: string;
  mono?: boolean;
  className?: string;
}

export default function StatCard({
  label,
  value,
  trend,
  trendValue,
  mono = true,
  className = "",
}: StatCardProps) {
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <span className="text-xs text-text-tertiary uppercase tracking-wider">
        {label}
      </span>
      <span
        className={`text-xl font-semibold text-text-primary ${mono ? "font-mono" : ""}`}
      >
        {value}
      </span>
      {trend && trendValue && (
        <div className="flex items-center gap-1">
          {trend === "up" && (
            <TrendingUp className="w-3 h-3 text-gain" />
          )}
          {trend === "down" && (
            <TrendingDown className="w-3 h-3 text-loss" />
          )}
          {trend === "flat" && (
            <Minus className="w-3 h-3 text-text-tertiary" />
          )}
          <span
            className={`text-xs font-mono ${
              trend === "up"
                ? "text-gain"
                : trend === "down"
                  ? "text-loss"
                  : "text-text-tertiary"
            }`}
          >
            {trendValue}
          </span>
        </div>
      )}
    </div>
  );
}
