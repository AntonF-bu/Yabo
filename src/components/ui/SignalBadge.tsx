interface SignalBadgeProps {
  score: number;
  size?: "sm" | "md" | "lg";
}

export default function SignalBadge({ score, size = "sm" }: SignalBadgeProps) {
  const getColor = (s: number) => {
    if (s >= 70) return "#4A8C6A";
    if (s >= 50) return "#9A7B5B";
    return "#C45A4A";
  };

  const color = getColor(score);
  const dims =
    size === "lg"
      ? "w-10 h-10"
      : size === "md"
        ? "w-8 h-8"
        : "w-6 h-6";
  const textSize =
    size === "lg"
      ? "text-sm"
      : size === "md"
        ? "text-xs"
        : "text-[10px]";
  const borderWidth = size === "lg" ? "2px" : "1.5px";

  return (
    <span
      className={`${dims} rounded-full inline-flex items-center justify-center font-mono font-semibold shrink-0`}
      style={{
        border: `${borderWidth} solid ${color}`,
        color: color,
        backgroundColor: "transparent",
      }}
    >
      <span className={textSize}>{score}</span>
    </span>
  );
}
