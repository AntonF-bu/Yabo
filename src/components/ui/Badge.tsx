import { tierColors } from "@/lib/constants";

interface BadgeProps {
  label: string;
  variant?: "default" | "tier" | "direction" | "custom";
  tier?: string;
  direction?: "long" | "short";
  bgColor?: string;
  textColor?: string;
  className?: string;
}

export default function Badge({
  label,
  variant = "default",
  tier,
  direction,
  bgColor,
  textColor,
  className = "",
}: BadgeProps) {
  if (variant === "tier" && tier) {
    const color = tierColors[tier] || "#A09A94";
    return (
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium uppercase tracking-wider ${className}`}
        style={{
          backgroundColor: `${color}18`,
          color: color,
        }}
      >
        {label}
      </span>
    );
  }

  if (variant === "direction" && direction) {
    const bg = direction === "long" ? "bg-green-light" : "bg-red-light";
    const text = direction === "long" ? "text-green" : "text-red";
    return (
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider ${bg} ${text} ${className}`}
      >
        {label}
      </span>
    );
  }

  if (variant === "custom" && bgColor && textColor) {
    return (
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium uppercase tracking-wider ${className}`}
        style={{ backgroundColor: bgColor, color: textColor }}
      >
        {label}
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium uppercase tracking-wider bg-surface-hover text-text-sec ${className}`}
    >
      {label}
    </span>
  );
}
