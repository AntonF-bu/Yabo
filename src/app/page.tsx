import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-text-primary flex flex-col items-center justify-center px-6">
      <div className="max-w-2xl mx-auto text-center animate-fade-up">
        <h1 className="font-serif italic text-5xl sm:text-6xl md:text-7xl text-white leading-tight">
          The Proving Ground
        </h1>

        <p className="mt-6 text-lg sm:text-xl text-white/60 font-medium animate-fade-up-delay-1">
          America&apos;s Got Talent for Stock Trading
        </p>

        <p className="mt-4 text-sm sm:text-base text-white/40 max-w-md mx-auto animate-fade-up-delay-2">
          Prove your skill. Earn your seat. Manage real capital.
        </p>

        <div className="mt-10 animate-fade-up-delay-3">
          <Link
            href="/dashboard"
            className="inline-flex items-center px-8 py-3.5 rounded-xl
              bg-accent text-white font-semibold text-base
              hover:bg-accent-dark transition-colors duration-200
              shadow-lg shadow-accent/25"
          >
            Let&apos;s See What You&apos;ve Got
          </Link>
        </div>
      </div>

      <div className="absolute bottom-8 text-white/20 text-xs tracking-widest uppercase">
        Yabo
      </div>
    </main>
  );
}
