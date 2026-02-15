import Link from "next/link";
import { trendingTickers } from "@/lib/mock-data";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-dark">
      {/* Nav */}
      <nav className="sticky top-0 z-50 bg-dark/90 backdrop-blur-sm border-b border-dark-border">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-accent flex items-center justify-center">
              <span className="text-xs font-bold text-white">Y</span>
            </div>
            <span className="text-base font-bold text-white">Yabo</span>
          </div>
          <div className="flex items-center gap-4">
            <Link
              href="/dashboard"
              className="text-sm text-white/60 hover:text-white transition-colors"
            >
              Log In
            </Link>
            <Link
              href="/dashboard"
              className="px-4 py-2 rounded-lg bg-accent text-white text-sm font-semibold hover:bg-accent-dark transition-colors"
            >
              Start Trading →
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-24 pb-20 px-6">
        <div className="max-w-3xl mx-auto text-center">
          <p className="text-[11px] font-semibold tracking-[4px] text-accent uppercase animate-fade-up">
            THE MERITOCRACY OF TRADING
          </p>
          <h1 className="mt-6 font-serif italic text-5xl sm:text-6xl md:text-7xl text-white leading-[1.1] animate-fade-up-delay-1">
            Prove you can trade.
            <br />
            Get capital to prove it bigger.
          </h1>
          <p className="mt-6 text-base text-white/40 max-w-xl mx-auto leading-relaxed animate-fade-up-delay-2">
            Yabo gives every trader $100K in simulated capital, AI that maps
            your behavioral edge, and a path to managing real capital. No
            gatekeepers. No pedigree. Just performance.
          </p>

          <div className="mt-10 flex items-center justify-center gap-4 animate-fade-up-delay-3">
            <Link
              href="/dashboard"
              className="px-7 py-3.5 rounded-full bg-accent text-white font-semibold text-sm hover:bg-accent-dark transition-colors shadow-lg shadow-accent/20"
            >
              Claim Your $100K →
            </Link>
            <button className="px-7 py-3.5 rounded-full border border-white/20 text-white text-sm font-medium hover:border-white/40 transition-colors">
              Watch Demo
            </button>
          </div>

          {/* Stats */}
          <div className="mt-16 grid grid-cols-4 gap-8 animate-fade-up-delay-4">
            {[
              { value: "12,400+", label: "Active Traders" },
              { value: "$2.4B", label: "Sim Volume" },
              { value: "847", label: "Funded Traders" },
              { value: "71%", label: "Signal Accuracy" },
            ].map((stat) => (
              <div key={stat.label} className="text-center">
                <p className="font-mono text-2xl font-bold text-white">
                  {stat.value}
                </p>
                <p className="text-xs text-white/40 mt-1">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Trending */}
      <section className="pb-20 px-6">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-center text-xs font-semibold tracking-[3px] text-white/30 uppercase mb-8">
            Trending Now
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {trendingTickers.slice(0, 5).map((t) => {
              const isPositive = t.change >= 0;
              const signalBg =
                t.signal >= 70
                  ? "#22A06B"
                  : t.signal >= 50
                    ? "#E85D26"
                    : "#DE350B";
              return (
                <div
                  key={t.ticker}
                  className="bg-dark-surface border border-dark-border rounded-xl p-4 hover:border-white/20 transition-colors cursor-pointer"
                >
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-mono text-sm font-bold text-white">
                      {t.ticker}
                    </span>
                    <span
                      className={`font-mono text-xs font-semibold ${isPositive ? "text-gain" : "text-loss"}`}
                    >
                      {isPositive ? "+" : ""}
                      {t.change.toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span
                      className="w-6 h-6 rounded-full inline-flex items-center justify-center text-[10px] font-bold text-white"
                      style={{ backgroundColor: signalBg }}
                    >
                      {t.signal}
                    </span>
                    <span className="text-[10px] text-white/30">
                      {t.theses} theses
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>
    </main>
  );
}
