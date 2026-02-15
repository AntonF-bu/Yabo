interface LiveDotProps {
  className?: string;
}

export default function LiveDot({ className = "" }: LiveDotProps) {
  return (
    <span
      className={`inline-block w-1.5 h-1.5 rounded-full bg-teal animate-pulse-dot ${className}`}
    />
  );
}
