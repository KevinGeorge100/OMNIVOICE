import { CheckCircle2, Clock, ArrowRight } from "lucide-react";

const PILOT_FEATURES = [
  "1 connected phone line (Exotel or Twilio)",
  "Direct local or self-hosted server deployment",
  "11 Indian regional language codes (Sarvam AI)",
  "Approved FAQ in-memory fast-path (<2ms in-process)",
  "Deterministic write confirmation gating",
  "OpenAPI Swagger & Operations Console",
];

const SCALE_FEATURES = [
  "Multi-line support (planned)",
  "Cloud container deployment (planned)",
  "PostgreSQL persistent storage (planned)",
  "Usage metering & quota enforcement (planned)",
  "OpenTelemetry observability (planned)",
];

const ENTERPRISE_FEATURES = [
  "Dedicated infrastructure (planned)",
  "Custom language model tuning (planned)",
  "SLA framework (roadmap — not yet measured)",
  "Role-based access control (planned)",
  "Private VPC deployment (roadmap)",
];

export default function PricingSection() {
  return (
    <section id="pricing" className="py-24 bg-[var(--section-alt)]">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">

        {/* Header */}
        <div className="max-w-2xl mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--accent-subtle)] border border-[var(--accent)]/30 text-[11px] font-mono font-semibold text-[var(--accent)] mb-5 uppercase tracking-wider">
            Pricing
          </div>
          <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-[var(--foreground)] leading-[1.08] mb-4">
            Start with a pilot.
          </h2>
          <p className="text-lg text-[var(--muted-foreground)] leading-relaxed">
            Indicative commercial model — pricing enforcement is not yet implemented. Contact us to discuss pilot deployment.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 items-start">

          {/* ── PILOT ── */}
          <div className="relative bg-[var(--card)] border-2 border-[var(--accent)] rounded-2xl p-7 shadow-sm shadow-[var(--accent-glow)] flex flex-col">
            {/* Recommended badge */}
            <div className="absolute -top-3 left-6">
              <span className="px-3 py-1 rounded-full text-[11px] font-mono font-semibold bg-[var(--accent)] text-white">
                Recommended Starting Point
              </span>
            </div>

            <div className="mt-3 mb-6">
              <h3 className="text-xl font-bold text-[var(--foreground)] mb-1">Pilot</h3>
              <div className="flex items-baseline gap-1.5 mb-1">
                <span className="text-4xl font-extrabold font-mono text-[var(--accent)]">₹6–10</span>
                <span className="text-sm text-[var(--muted-foreground)] font-medium">/min</span>
              </div>
              <p className="text-xs text-[var(--muted-foreground)] font-mono">
                Indicative · Local deployment
              </p>
            </div>

            <ul className="space-y-2.5 flex-1 mb-8">
              {PILOT_FEATURES.map((f, i) => (
                <li key={i} className="flex items-start gap-2.5 text-sm">
                  <CheckCircle2 className="w-4 h-4 text-[var(--accent)] shrink-0 mt-0.5" />
                  <span className="text-[var(--foreground)]">{f}</span>
                </li>
              ))}
            </ul>

            <a
              href="http://localhost:8000"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 w-full py-3 rounded-xl text-sm font-semibold bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2"
            >
              Launch Console
              <ArrowRight className="w-4 h-4" />
            </a>
          </div>

          {/* ── SCALE ── */}
          <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-7 flex flex-col">
            <div className="mb-6">
              <div className="flex items-center gap-2 mb-2">
                <h3 className="text-xl font-bold text-[var(--foreground)]">Scale</h3>
                <span className="px-2 py-0.5 rounded-md text-[10px] font-mono font-semibold bg-amber-100 text-amber-700 border border-amber-200">
                  Roadmap
                </span>
              </div>
              <div className="flex items-baseline gap-1.5 mb-1">
                <span className="text-4xl font-extrabold font-mono text-[var(--foreground)]">Custom</span>
              </div>
              <p className="text-xs text-[var(--muted-foreground)] font-mono">
                Planned · Not yet available
              </p>
            </div>

            <ul className="space-y-2.5 flex-1 mb-8">
              {SCALE_FEATURES.map((f, i) => (
                <li key={i} className="flex items-start gap-2.5 text-sm">
                  <Clock className="w-4 h-4 text-[var(--muted)] shrink-0 mt-0.5" />
                  <span className="text-[var(--muted-foreground)]">{f}</span>
                </li>
              ))}
            </ul>

            <button
              disabled
              className="w-full py-3 rounded-xl text-sm font-semibold bg-[var(--card-hover)] text-[var(--muted)] border border-[var(--border)] cursor-not-allowed"
            >
              Planned — Contact Us
            </button>
          </div>

          {/* ── ENTERPRISE ── */}
          <div className="bg-[var(--foreground)] border border-[var(--foreground)] rounded-2xl p-7 flex flex-col">
            <div className="mb-6">
              <div className="flex items-center gap-2 mb-2">
                <h3 className="text-xl font-bold text-white">Enterprise</h3>
                <span className="px-2 py-0.5 rounded-md text-[10px] font-mono font-semibold bg-white/10 text-white/60 border border-white/15">
                  Roadmap
                </span>
              </div>
              <div className="flex items-baseline gap-1.5 mb-1">
                <span className="text-4xl font-extrabold font-mono text-white">Custom</span>
              </div>
              <p className="text-xs text-white/50 font-mono">
                Target · Roadmap items only
              </p>
            </div>

            <ul className="space-y-2.5 flex-1 mb-8">
              {ENTERPRISE_FEATURES.map((f, i) => (
                <li key={i} className="flex items-start gap-2.5 text-sm">
                  <Clock className="w-4 h-4 text-white/30 shrink-0 mt-0.5" />
                  <span className="text-white/60">{f}</span>
                </li>
              ))}
            </ul>

            <button
              disabled
              className="w-full py-3 rounded-xl text-sm font-semibold bg-white/5 text-white/40 border border-white/10 cursor-not-allowed"
            >
              Discuss Requirements
            </button>
          </div>
        </div>

        <p className="mt-8 text-xs text-[var(--muted)] text-center leading-relaxed max-w-xl mx-auto">
          All prices are indicative estimates. No billing or quota enforcement is currently implemented.
          Features marked Roadmap or Planned are not yet available and represent development targets only.
        </p>
      </div>
    </section>
  );
}
