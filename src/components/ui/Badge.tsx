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
  let bg = "bg-background";
  let text = "text-text-secondary";

  if (variant === "tier" && tier) {
    const color = tierColors[tier] || "#9B9B9B";
    return (
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${className}`}
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
    bg = direction === "long" ? "bg-gain-light" : "bg-loss-light";
    text = direction === "long" ? "text-gain" : "text-loss";
  }

  if (variant === "custom" && bgColor && textColor) {
    return (
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${className}`}
        style={{ backgroundColor: bgColor, color: textColor }}
      >
        {label}
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${bg} ${text} ${className}`}
    >
      {label}
    </span>
  );
}
