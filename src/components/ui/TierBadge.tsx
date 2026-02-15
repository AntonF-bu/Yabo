import { tierColors } from "@/lib/constants";

interface TierBadgeProps {
  tier: string;
  className?: string;
}

export default function TierBadge({ tier, className = "" }: TierBadgeProps) {
  const color = tierColors[tier] || "#9B9B9B";

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider ${className}`}
      style={{
        backgroundColor: `${color}18`,
        color: color,
      }}
    >
      {tier}
    </span>
  );
}
