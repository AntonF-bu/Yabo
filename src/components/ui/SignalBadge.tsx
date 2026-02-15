interface SignalBadgeProps {
  score: number;
  size?: "sm" | "md" | "lg";
}

export default function SignalBadge({ score, size = "sm" }: SignalBadgeProps) {
  const getBg = (s: number) => {
    if (s >= 70) return "#22A06B";
    if (s >= 50) return "#E85D26";
    return "#DE350B";
  };

  const bg = getBg(score);
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

  return (
    <span
      className={`${dims} rounded-full inline-flex items-center justify-center font-mono font-bold text-white shrink-0`}
      style={{ backgroundColor: bg }}
    >
      <span className={textSize}>{score}</span>
    </span>
  );
}
