"use client";

interface CardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
  onClick?: () => void;
}

export default function Card({
  children,
  className = "",
  hover = true,
  onClick,
}: CardProps) {
  return (
    <div
      onClick={onClick}
      className={`
        bg-surface rounded-xl border border-border
        ${hover ? "transition-all duration-200 hover:shadow-sm hover:-translate-y-0.5 hover:border-text-tertiary/30" : ""}
        ${onClick ? "cursor-pointer" : ""}
        ${className}
      `}
    >
      {children}
    </div>
  );
}
