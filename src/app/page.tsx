import Link from "next/link";
import { trendingTickers } from "@/lib/mock-data";
import AccentLine from "@/components/ui/AccentLine";
import LiveDot from "@/components/ui/LiveDot";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-bg">
      {/* Top accent line */}
      <AccentLine />

      {/* Nav */}
      <nav className="sticky top-0 z-50 bg-bg/90 backdrop-blur-sm border-b border-border">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="font-display italic text-[28px] text-teal">Y</span>
            <span className="text-base font-bold text-text font-body">yabo</span>
            <span className="px-2 py-0.5 rounded bg-teal-light text-teal text-[9px] font-mono font-bold uppercase tracking-wider">
              BETA
            </span>
          </div>
          <div className="flex items-center gap-6">
            <Link href="#how" className="text-sm text-text-sec hover:text-text transition-colors font-body hidden sm:block">
              How It Works
            </Link>
            <Link href="/dashboard" className="text-sm text-text-sec hover:text-text transition-colors font-body hidden sm:block">
              Leaderboard
            </Link>
            <Link
              href="/dashboard"
              className="text-sm text-text-sec hover:text-text transition-colors font-body"
            >
              Log In
            </Link>
            <Link
              href="/dashboard"
              className="px-4 py-2 rounded-lg border border-teal text-teal text-sm font-semibold font-body hover:bg-teal-light transition-colors"
            >
              Start Trading
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-28 pb-24 px-6 relative">
        {/* Subtle teal radial glow */}
        <div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] opacity-[0.06] pointer-events-none"
          style={{ background: "radial-gradient(ellipse, #00BFA6, transparent 70%)" }}
        />
        <div className="max-w-3xl mx-auto text-center relative">
          <div className="flex items-center justify-center gap-2 animate-fade-up">
            <LiveDot />
            <p className="text-[11px] font-mono font-medium tracking-[4px] text-teal uppercase">
              THE PROVING GROUND
            </p>
          </div>
          <h1 className="mt-8 font-display italic text-5xl sm:text-6xl md:text-[68px] text-text leading-[1.1] animate-fade-up-delay-1">
            Prove you can trade.
            <br />
            <span className="text-teal">Get funded to do it for real.</span>
          </h1>
          <p className="mt-6 text-[17px] text-text-sec max-w-[500px] mx-auto leading-relaxed animate-fade-up-delay-2 font-body">
            Yabo gives every trader $100K in simulated capital, AI that maps
            your behavioral edge, and a path to managing real capital. No
            gatekeepers. No pedigree. Just performance.
          </p>

          <div className="mt-10 flex items-center justify-center gap-4 animate-fade-up-delay-3">
            <Link
              href="/dashboard"
              className="px-7 py-3.5 rounded-full bg-teal text-bg font-semibold text-sm font-body hover:shadow-[0_0_24px_rgba(0,191,166,0.3)] transition-all"
            >
              Claim Your $100K
            </Link>
            <button className="px-7 py-3.5 rounded-full border border-border-hover text-text-sec text-sm font-medium font-body hover:border-text-ter transition-colors">
              Watch Demo
            </button>
          </div>

          {/* Stats */}
          <div className="mt-20 grid grid-cols-2 md:grid-cols-4 gap-8 animate-fade-up-delay-4">
            {[
              { value: "12,400+", label: "Active Traders" },
              { value: "$2.4B", label: "Sim Volume" },
              { value: "847", label: "Funded" },
              { value: "71%", label: "Signal Accuracy" },
            ].map((stat) => (
              <div key={stat.label} className="text-center">
                <p className="font-mono text-[30px] font-semibold text-text">
                  {stat.value}
                </p>
                <p className="text-[10px] font-mono uppercase tracking-[2px] text-text-muted mt-1">
                  {stat.label}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Dashboard Preview Card */}
      <section className="pb-24 px-6">
        <div className="max-w-[900px] mx-auto">
          <div
            className="bg-surface rounded-2xl border border-border p-6"
            style={{ boxShadow: "0 24px 80px rgba(0,0,0,0.3), 0 0 0 1px rgba(0,191,166,0.05)" }}
          >
            <div className="flex items-center gap-4 mb-6 border-b border-border pb-4">
              {["Portfolio", "The Room", "Mirror", "Leaderboard"].map((tab, i) => (
                <span
                  key={tab}
                  className={`text-xs font-mono font-medium px-3 py-1.5 rounded-lg ${
                    i === 0 ? "bg-teal-light text-teal" : "text-text-ter"
                  }`}
                >
                  {tab}
                </span>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-6">
              <div>
                <p className="text-[10px] font-mono text-text-ter uppercase tracking-[2px]">Portfolio Value</p>
                <p className="font-mono text-[36px] font-bold text-text mt-1">$127,432</p>
                <p className="font-mono text-sm text-green mt-1">+$27,432 (27.4%)</p>
              </div>
              <div className="flex items-end justify-end">
                <svg width="200" height="60" className="overflow-visible">
                  <polyline
                    points="0,50 20,48 40,42 60,45 80,38 100,35 120,30 140,28 160,22 180,18 200,12"
                    fill="none"
                    stroke="#00BFA6"
                    strokeWidth={2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3 mt-6">
              {[
                { ticker: "NVDA", pnl: "+18.2%", value: "$42,180" },
                { ticker: "AMZN", pnl: "+12.7%", value: "$31,400" },
                { ticker: "COST", pnl: "+8.4%", value: "$24,500" },
              ].map((pos) => (
                <div key={pos.ticker} className="bg-bg rounded-lg p-3 border border-border">
                  <span className="font-mono text-sm font-bold text-text">{pos.ticker}</span>
                  <p className="font-mono text-xs text-green mt-1">{pos.pnl}</p>
                  <p className="font-mono text-xs text-text-ter mt-0.5">{pos.value}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how" className="pb-24 px-6">
        <div className="max-w-3xl mx-auto">
          <p className="text-[11px] font-mono font-medium tracking-[4px] text-teal uppercase mb-4">
            THE PATH
          </p>
          <h2 className="font-display italic text-[32px] text-text mb-12">
            Four stages. One destination.
          </h2>

          <div className="space-y-0">
            {[
              { num: "01", name: "Simulate", desc: "Start with $100K in simulated capital. Trade real markets with zero risk. Every decision is tracked." },
              { num: "02", name: "Prove", desc: "Our AI maps your behavioral edge across 8 dimensions. Win rate, timing, conviction. No hiding." },
              { num: "03", name: "Compete", desc: "Climb the leaderboard. Earn rep from the community. The best rise to the top." },
              { num: "04", name: "Fund", desc: "Top performers get funded with real capital. This is where it gets real.", last: true },
            ].map((step) => (
              <div
                key={step.num}
                className={`flex items-start gap-8 py-6 border-b border-border group cursor-pointer
                  transition-all duration-200 hover:pl-2 hover:bg-teal-muted`}
              >
                <span className={`font-mono text-lg font-medium shrink-0 ${step.last ? "text-teal" : "text-text-muted"}`}>
                  {step.num}
                </span>
                <div>
                  <h3 className={`font-display italic text-xl ${step.last ? "text-teal" : "text-text"}`}>
                    {step.name}
                  </h3>
                  <p className="text-sm text-text-sec mt-1 leading-relaxed font-body">
                    {step.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="pb-24 px-6">
        <div className="max-w-2xl mx-auto text-center">
          <AccentLine className="mb-16" />
          <h2 className="font-display italic text-[32px] text-text">
            The market doesn&apos;t care who you know.
          </h2>
          <p className="text-base text-text-sec mt-3 font-body">
            Neither do we. Show us what you&apos;ve got.
          </p>
          <Link
            href="/dashboard"
            className="inline-block mt-8 px-8 py-4 rounded-full bg-teal text-bg font-semibold text-sm font-body hover:shadow-[0_0_24px_rgba(0,191,166,0.3)] transition-all"
          >
            Start Trading
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-6 px-6">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <p className="text-[10px] font-mono text-text-muted">
            Simulated trading only. Past simulated performance does not guarantee future results.
          </p>
          <p className="text-[10px] font-mono text-text-muted">
            yabo 2026
          </p>
        </div>
      </footer>
    </main>
  );
}
