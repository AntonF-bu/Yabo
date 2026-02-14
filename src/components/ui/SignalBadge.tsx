interface SignalBadgeProps {
  score: number;
  label?: string;
  size?: "sm" | "md";
}

export default function SignalBadge({
  score,
  label = "Signal",
  size = "sm",
}: SignalBadgeProps) {
  const getColor = (s: number) => {
    if (s >= 70) return { bg: "#E3FCEF", text: "#22A06B", ring: "#22A06B" };
    if (s >= 50) return { bg: "#FEF0EB", text: "#E85D26", ring: "#E85D26" };
    return { bg: "#FFEBE6", text: "#DE350B", ring: "#DE350B" };
  };

  const color = getColor(score);
  const isSm = size === "sm";

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full font-mono font-medium
        ${isSm ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm"}`}
      style={{
        backgroundColor: color.bg,
        color: color.text,
        boxShadow: `inset 0 0 0 1px ${color.ring}30`,
      }}
    >
      <span className="opacity-70">{label}</span>
      <span className="font-semibold">{score}</span>
    </span>
  );
}
