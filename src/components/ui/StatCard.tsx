import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface StatCardProps {
  label: string;
  value: string | number;
  trend?: "up" | "down" | "flat";
  trendValue?: string;
  className?: string;
}

export default function StatCard({
  label,
  value,
  trend,
  trendValue,
  className = "",
}: StatCardProps) {
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <span className="text-[11px] text-text-ter uppercase tracking-[2px] font-mono font-medium">
        {label}
      </span>
      <span className="text-xl font-semibold text-text font-mono">
        {value}
      </span>
      {trend && trendValue && (
        <div className="flex items-center gap-1">
          {trend === "up" && (
            <TrendingUp className="w-3 h-3 text-green" />
          )}
          {trend === "down" && (
            <TrendingDown className="w-3 h-3 text-red" />
          )}
          {trend === "flat" && (
            <Minus className="w-3 h-3 text-text-ter" />
          )}
          <span
            className={`text-xs font-mono ${
              trend === "up"
                ? "text-green"
                : trend === "down"
                  ? "text-red"
                  : "text-text-ter"
            }`}
          >
            {trendValue}
          </span>
        </div>
      )}
    </div>
  );
}
