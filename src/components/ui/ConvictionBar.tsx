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
    if (v >= 80) return "linear-gradient(90deg, #00BFA6, #00BFA6)";
    if (v >= 60) return "linear-gradient(90deg, #FFB020, #00BFA6)";
    return "linear-gradient(90deg, #FF6B6B, #FFB020)";
  };

  return (
    <div className="flex items-center gap-2">
      {showLabel && (
        <span className="text-xs text-text-ter whitespace-nowrap font-body">
          Conviction
        </span>
      )}
      <div
        className={`flex-1 rounded-full bg-text-muted overflow-hidden ${height === "sm" ? "h-1.5" : "h-2.5"}`}
      >
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${pct}%`,
            background: getGradient(value),
          }}
        />
      </div>
      <span className="font-mono text-xs text-text-sec font-medium">
        {value}
      </span>
    </div>
  );
}
