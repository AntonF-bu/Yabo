interface AccentLineProps {
  className?: string;
}

export default function AccentLine({ className = "" }: AccentLineProps) {
  return (
    <div
      className={`h-0.5 w-full ${className}`}
      style={{
        background: "linear-gradient(90deg, transparent, #00BFA6, transparent)",
      }}
    />
  );
}
