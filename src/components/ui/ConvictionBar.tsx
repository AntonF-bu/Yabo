interface ConvictionBarProps {
  value: number;
  max?: number;
  showLabel?: boolean;
  height?: "sm" | "md";
}

export default function ConvictionBar({
  value,
  max = 100,
  showLabel = true,
  height = "sm",
}: ConvictionBarProps) {
  const pct = Math.min((value / max) * 100, 100);

  const getGradient = (v: number) => {
    if (v >= 80) return "linear-gradient(90deg, #E85D26, #22A06B)";
    if (v >= 60) return "linear-gradient(90deg, #E85D26, #FF991F)";
    return "linear-gradient(90deg, #DE350B, #E85D26)";
  };

  return (
    <div className="flex items-center gap-2">
      {showLabel && (
        <span className="text-xs text-text-tertiary whitespace-nowrap">
          Conviction
        </span>
      )}
      <div
        className={`flex-1 rounded-full bg-border-light overflow-hidden ${height === "sm" ? "h-1.5" : "h-2.5"}`}
      >
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${pct}%`,
            background: getGradient(value),
          }}
        />
      </div>
      <span className="font-mono text-xs text-text-secondary font-medium">
        {value}
      </span>
    </div>
  );
}
