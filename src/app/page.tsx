import Link from "next/link";
import { SignedIn, SignedOut, UserButton } from "@clerk/nextjs";
import AccentLine from "@/components/ui/AccentLine";
import LandingGuide from "@/components/guide/LandingGuide";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-bg">
      <LandingGuide />
      {/* Top accent line */}
      <AccentLine />

      {/* Nav */}
      <nav className="sticky top-0 z-50 bg-bg/90 backdrop-blur-sm border-b border-border">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="font-display text-[22px] font-semibold text-text">Yabo</span>
            <span className="px-2 py-0.5 rounded-full border border-border text-[9px] font-body font-medium uppercase tracking-wider text-text-ter">
              BETA
            </span>
          </div>
          <div className="flex items-center gap-6">
            <Link href="#how" className="text-[13px] text-text-sec hover:text-text transition-colors font-body hidden sm:block">
              How It Works
            </Link>
            <Link href="/dashboard" className="text-[13px] text-text-sec hover:text-text transition-colors font-body hidden sm:block">
              Leaderboard
            </Link>
            <SignedOut>
              <Link
                href="/sign-in"
                className="text-[13px] text-text-sec hover:text-text transition-colors font-body"
              >
                Log In
              </Link>
              <Link
                href="/sign-up"
                className="px-5 py-2.5 rounded-[10px] bg-text text-bg text-sm font-semibold font-body hover:-translate-y-0.5 transition-all"
              >
                Start Trading
              </Link>
            </SignedOut>
            <SignedIn>
              <Link
                href="/dashboard"
                className="px-5 py-2.5 rounded-[10px] bg-text text-bg text-sm font-semibold font-body hover:-translate-y-0.5 transition-all"
              >
                Dashboard
              </Link>
              <UserButton afterSignOutUrl="/" />
            </SignedIn>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-28 pb-24 px-6 relative">
        <div className="max-w-3xl mx-auto text-center relative">
          <h1 className="font-display text-5xl sm:text-6xl md:text-[68px] text-text leading-[1.1] animate-fade-up tracking-[-0.5px]" style={{ fontWeight: 400 }}>
            Prove you can trade.
            <br />
            Get funded to do it for{" "}
            <span className="italic text-teal">real</span>.
          </h1>
          <p className="mt-6 text-[17px] text-text-sec max-w-[520px] mx-auto leading-relaxed animate-fade-up-delay-1 font-body">
            Yabo gives every trader $100K in simulated capital, AI that maps
            your behavioral edge, and a path to managing real capital. No
            gatekeepers. No pedigree. Just performance.
          </p>

          <div className="mt-10 flex items-center justify-center gap-4 animate-fade-up-delay-2">
            <SignedOut>
              <Link
                href="/onboarding"
                className="px-8 py-3.5 rounded-[10px] bg-text text-bg font-semibold text-sm font-body hover:-translate-y-0.5 transition-all"
              >
                Claim Your $100K
              </Link>
              <Link
                href="#how"
                className="text-sm text-text-sec font-body border-b border-text-muted hover:text-text hover:border-text transition-colors"
              >
                How It Works
              </Link>
            </SignedOut>
            <SignedIn>
              <Link
                href="/dashboard"
                className="px-8 py-3.5 rounded-[10px] bg-text text-bg font-semibold text-sm font-body hover:-translate-y-0.5 transition-all"
              >
                Go to Dashboard
              </Link>
            </SignedIn>
          </div>

          {/* Stats */}
          <div className="mt-20 grid grid-cols-2 md:grid-cols-4 gap-8 animate-fade-up-delay-3">
            {[
              { value: "12,400+", label: "Active Traders" },
              { value: "$2.4B", label: "Sim Volume" },
              { value: "847", label: "Funded" },
              { value: "71%", label: "Signal Accuracy" },
            ].map((stat, i) => (
              <div key={stat.label} className={`text-center ${i > 0 ? "border-l border-border" : ""}`}>
                <p className="font-display text-[36px] font-medium text-text tracking-[-0.5px]">
                  {stat.value}
                </p>
                <p className="text-[11px] font-body font-medium uppercase tracking-[2px] text-text-ter mt-1">
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
            className="bg-surface rounded-[14px] border border-border p-6"
          >
            <div className="flex items-center gap-4 mb-6 border-b border-border pb-4">
              {["Portfolio", "The Room", "Mirror", "Leaderboard"].map((tab, i) => (
                <span
                  key={tab}
                  className={`text-xs font-body font-medium px-4 py-2 rounded-lg ${
                    i === 0 ? "bg-text text-bg" : "text-text-ter bg-surface"
                  }`}
                >
                  {tab}
                </span>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-6">
              <div>
                <p className="text-[11px] font-body font-medium text-text-ter uppercase tracking-[2px]">Portfolio Value</p>
                <p className="font-display text-[36px] font-medium text-text mt-1 tracking-[-0.5px]">$127,432</p>
                <p className="font-mono text-sm text-green mt-1">+$27,432 (27.4%)</p>
              </div>
              <div className="flex items-end justify-end">
                <svg width="200" height="60" className="overflow-visible">
                  <polyline
                    points="0,50 20,48 40,42 60,45 80,38 100,35 120,30 140,28 160,22 180,18 200,12"
                    fill="none"
                    stroke="#4A8C6A"
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
          <p className="text-[11px] font-body font-semibold tracking-[3px] text-teal uppercase mb-4">
            THE PATH
          </p>
          <h2 className="font-display text-[32px] text-text mb-12" style={{ fontWeight: 500 }}>
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
                className={`flex items-start gap-8 py-6 border-b border-border group
                  transition-all duration-200 hover:pl-2`}
                style={step.last ? {} : {}}
              >
                <span className={`font-display text-xl font-medium shrink-0 ${step.last ? "text-teal" : "text-text-muted"}`}>
                  {step.num}
                </span>
                <div>
                  <h3 className={`font-display text-xl ${step.last ? "text-teal" : "text-text"}`} style={{ fontWeight: 500 }}>
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
          <h2 className="font-display text-[32px] text-text" style={{ fontWeight: 400 }}>
            The market doesn&apos;t care who you know.
          </h2>
          <p className="text-base text-text-sec mt-3 font-body">
            Neither do we. Show us what you&apos;ve got.
          </p>
          <Link
            href="/onboarding"
            className="inline-block mt-8 px-8 py-3.5 rounded-[10px] bg-text text-bg font-semibold text-sm font-body hover:-translate-y-0.5 transition-all"
          >
            Start Trading
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-6 px-6">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <p className="text-xs font-body text-text-ter">
            Simulated trading only. Past simulated performance does not guarantee future results.
          </p>
          <p className="text-xs font-body text-text-ter">
            Yabo 2026
          </p>
        </div>
      </footer>
    </main>
  );
}
