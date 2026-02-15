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
        ${hover ? "transition-all duration-200 hover:-translate-y-0.5 hover:border-border-accent hover:shadow-[0_4px_24px_rgba(0,0,0,0.3)]" : ""}
        ${onClick ? "cursor-pointer" : ""}
        ${className}
      `}
    >
      {children}
    </div>
  );
}
