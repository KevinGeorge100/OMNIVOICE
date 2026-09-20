import { Zap, Globe2, Database, ShieldAlert, Cpu, Lock } from "lucide-react";

export default function FeatureGrid() {
  const features = [
    {
      icon: Zap,
      title: "Sub-500ms Full-Duplex Turnaround",
      tag: "REAL-TIME LATENCY",
      desc: "Neural VAD detects caller speech in under 20ms and halts carrier playback in less than 50ms. No robotic collisions or awkward delays.",
      stat: "<500ms",
      statLabel: "Mouth-to-Ear Target",
    },
    {
      icon: Globe2,
      title: "11 Indian Regional Languages",
      tag: "NATIVE ACOUSTICS",
      desc: "Built on high-fidelity regional acoustic models covering Hindi, Tamil, Telugu, Marathi, Bengali, Kannada, Malayalam, Odia, Gujarati, Punjabi, and English.",
      stat: "11",
      statLabel: "Languages Supported",
    },
    {
      icon: Database,
      title: "Fast-Path Cache Bypass (<2ms)",
      tag: "COMPUTE OPTIMIZATION",
      desc: "Approved FAQs bypass LLM inference entirely, retrieving answers in under 2ms. Cuts token usage and cloud inference costs by up to 65%.",
      stat: "<2ms",
      statLabel: "In-Memory Hit",
    },
    {
      icon: ShieldAlert,
      title: "Confirmation-Gated Action Writes",
      tag: "ZERO HALLUCINATIONS",
      desc: "Operational tools (address changes, appointment bookings, order cancellations) require an explicit caller confirmation phrase before commit.",
      stat: "100%",
      statLabel: "Audit Safety",
    },
    {
      icon: Cpu,
      title: "Carrier-Agnostic Webhook Gateway",
      tag: "SIP & PSTN",
      desc: "Bidirectional WebSocket streaming with Exotel and Twilio. Register phone lines you already own without buying dedicated new carrier numbers.",
      stat: "2",
      statLabel: "Major Carriers Integrated",
    },
    {
      icon: Lock,
      title: "Enterprise Tenant Isolation",
      tag: "COMPLIANCE",
      desc: "Encrypted per-tenant SQLite/PostgreSQL schemas and vector spaces. Private business documents are never shared across enterprise boundaries.",
      stat: "SOC2",
      statLabel: "Architecture Ready",
    },
  ];

  return (
    <section id="platform" className="py-24 relative">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--accent-subtle)] border border-[var(--accent)] text-xs font-mono font-semibold text-[var(--accent)] mb-4">
            <span>PLATFORM CAPABILITIES</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-[var(--foreground)] mb-4">
            Engineered for low latency, regional speech, and bulletproof safety.
          </h2>
          <p className="text-base sm:text-lg text-[var(--muted-foreground)]">
            Every layer of OmniVoice is tuned to eliminate the latency bottlenecks and hallucination risks of generic conversational AI.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((f, idx) => {
            const Icon = f.icon;
            return (
              <div
                key={idx}
                className="p-6 rounded-2xl bg-[var(--card)] border border-[var(--border)] hover:border-[var(--border-strong)] transition-all hover:-translate-y-1 group flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-10 h-10 rounded-xl bg-[var(--accent-subtle)] border border-[var(--accent)]/30 flex items-center justify-center text-[var(--accent)] group-hover:scale-110 transition-transform">
                      <Icon className="w-5 h-5" />
                    </div>
                    <span className="text-[10px] font-mono font-semibold tracking-wider px-2 py-0.5 rounded bg-[var(--surface-hover)] text-[var(--muted)] border border-[var(--border)]">
                      {f.tag}
                    </span>
                  </div>

                  <h3 className="text-lg font-bold text-[var(--foreground)] mb-2 group-hover:text-[var(--accent)] transition-colors">
                    {f.title}
                  </h3>
                  <p className="text-xs text-[var(--muted-foreground)] leading-relaxed mb-6">
                    {f.desc}
                  </p>
                </div>

                <div className="pt-4 border-t border-[var(--border)] flex items-center justify-between">
                  <span className="text-xs text-[var(--muted)] font-medium">{f.statLabel}</span>
                  <span className="text-base font-extrabold font-mono text-[var(--foreground)]">
                    {f.stat}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
