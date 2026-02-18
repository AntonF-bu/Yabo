import Link from "next/link";
import AccentLine from "@/components/ui/AccentLine";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-bg">
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
            <Link
              href="/intake"
              className="px-5 py-2.5 rounded-[10px] bg-text text-bg text-sm font-semibold font-body hover:-translate-y-0.5 transition-all"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-28 pb-24 px-6 relative">
        <div className="max-w-3xl mx-auto text-center relative">
          <h1 className="font-display text-5xl sm:text-6xl md:text-[68px] text-text leading-[1.1] animate-fade-up tracking-[-0.5px]" style={{ fontWeight: 400 }}>
            Discover your
            <br />
            <span className="italic text-teal">Trading DNA</span>.
          </h1>
          <p className="mt-6 text-[17px] text-text-sec max-w-[520px] mx-auto leading-relaxed animate-fade-up-delay-1 font-body">
            Upload your brokerage history and our behavioral engine maps the
            patterns you can&apos;t see yourself. Eight dimensions. One honest
            profile. Zero judgment.
          </p>

          <div className="mt-10 flex items-center justify-center gap-4 animate-fade-up-delay-2">
            <Link
              href="/intake"
              className="px-8 py-3.5 rounded-[10px] bg-text text-bg font-semibold text-sm font-body hover:-translate-y-0.5 transition-all"
            >
              Upload Your Trades
            </Link>
            <Link
              href="#how"
              className="text-sm text-text-sec font-body border-b border-text-muted hover:text-text hover:border-text transition-colors"
            >
              How It Works
            </Link>
          </div>
        </div>
      </section>

      {/* What You Get */}
      <section className="pb-24 px-6">
        <div className="max-w-[900px] mx-auto">
          <div className="bg-surface rounded-[14px] border border-border p-8">
            <p className="text-[11px] font-body font-semibold tracking-[3px] text-teal uppercase mb-6">
              YOUR PROFILE INCLUDES
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-6">
              {[
                { label: "Behavioral Archetype", desc: "Your dominant trading personality distilled into a single profile." },
                { label: "8-Dimension Score", desc: "Active/Passive, Momentum/Value, Disciplined/Emotional, and more." },
                { label: "Deep Dive Analysis", desc: "Multi-paragraph narrative of your patterns, strengths, and blind spots." },
                { label: "Key Recommendation", desc: "One actionable insight to improve your edge immediately." },
              ].map((item) => (
                <div key={item.label}>
                  <h3 className="font-display text-base text-text mb-2" style={{ fontWeight: 500 }}>
                    {item.label}
                  </h3>
                  <p className="text-[13px] text-text-sec font-body leading-relaxed">
                    {item.desc}
                  </p>
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
            THE PROCESS
          </p>
          <h2 className="font-display text-[32px] text-text mb-12" style={{ fontWeight: 500 }}>
            Three steps. One profile.
          </h2>

          <div className="space-y-0">
            {[
              { num: "01", name: "Upload", desc: "Export your trade history from any brokerage. CSV or screenshots. We handle the parsing." },
              { num: "02", name: "Analyze", desc: "Our behavioral engine extracts 212 features from your trades. Timing, sizing, conviction, risk patterns." },
              { num: "03", name: "Discover", desc: "Get your Trading DNA profile: an honest, data-driven map of how you actually trade.", last: true },
            ].map((step) => (
              <div
                key={step.num}
                className={`flex items-start gap-8 py-6 border-b border-border group
                  transition-all duration-200 hover:pl-2`}
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
            Your trades tell a story.
          </h2>
          <p className="text-base text-text-sec mt-3 font-body">
            Let us read it for you.
          </p>
          <Link
            href="/intake"
            className="inline-block mt-8 px-8 py-3.5 rounded-[10px] bg-text text-bg font-semibold text-sm font-body hover:-translate-y-0.5 transition-all"
          >
            Discover Your Trading DNA
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-6 px-6">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <p className="text-xs font-body text-text-ter">
            Behavioral analysis only. Not financial advice. Past patterns do not guarantee future results.
          </p>
          <p className="text-xs font-body text-text-ter">
            Yabo 2026
          </p>
        </div>
      </footer>
    </main>
  );
}
