import { Check, ArrowRight } from "lucide-react";

export default function PricingSection() {
  const plans = [
    {
      name: "Developer Pilot",
      tagline: "For local testing, prototypes, and initial carrier integrations.",
      price: "₹0",
      period: "open developer access",
      minuteRate: "Provider pass-through (COGS ~₹1.60–₹1.80/min)",
      popular: false,
      features: [
        "1 Connected phone line (Exotel / Twilio)",
        "Direct local or self-hosted server deployment",
        "11 Indian regional language codes (Sarvam AI)",
        "Approved FAQ in-memory fast-path (<2ms in-process)",
        "Deterministic write confirmation gating",
        "OpenAPI Swagger & Operations Console",
      ],
      cta: "Launch Operations Console",
      href: "http://localhost:8000",
    },
    {
      name: "Production Scale",
      tagline: "Indicative tier for growing businesses scaling call operations.",
      price: "₹9,999",
      period: "indicative monthly",
      minuteRate: "Target commercial rate: ₹6–₹10 / minute",
      popular: true,
      features: [
        "Target concurrency: 15 phone lines (Roadmap)",
        "Groq LPU Llama 3.1 8B Instant inference",
        "Unlimited tenant FAQs & business documents",
        "Sub-500ms pipeline budget target",
        "Full-duplex real-time transcript streaming",
        "Audit-logged tool execution safety gates",
        "Target SLA: 99.9% uptime (Roadmap)",
        "Email & developer support",
      ],
      cta: "Launch Operations Console",
      href: "http://localhost:8000",
    },
    {
      name: "Enterprise Dedicated",
      tagline: "Planned deployment options for high-volume contact centers.",
      price: "Custom",
      period: "enterprise roadmap",
      minuteRate: "Volume commercial agreements",
      popular: false,
      features: [
        "Multi-worker high-concurrency architecture",
        "Dedicated carrier audio stream endpoints",
        "Custom regional acoustic tuning & brand voice",
        "Private VPC / on-prem deployment (Roadmap)",
        "Tenant data isolation & zero-retention audio mode",
        "Bearer authentication & SSRF protection",
        "Dedicated enterprise engineering SLA",
      ],
      cta: "Explore Enterprise Roadmap",
      href: "#contact",
    },
  ];

  return (
    <section id="pricing" className="py-24 bg-[var(--card)]/40 border-t border-[var(--border)] relative">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--accent-subtle)] border border-[var(--accent)] text-xs font-mono font-semibold text-[var(--accent)] mb-4">
            <span>INDICATIVE COMMERCIAL TIERS</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-[var(--foreground)] mb-4">
            Indicative plans &amp; production roadmap.
          </h2>
          <p className="text-base sm:text-lg text-[var(--muted-foreground)]">
            Transparent commercial economics. Baseline pipeline COGS modeled at ₹1.60–₹1.80/min with target commercial pricing around ₹6–₹10/min.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-stretch">
          {plans.map((p) => (
            <div
              key={p.name}
              className={`p-8 rounded-3xl border flex flex-col justify-between transition-all relative ${
                p.popular
                  ? "bg-[var(--card)] border-[var(--accent)] shadow-2xl shadow-[var(--accent-glow)] scale-105 z-10"
                  : "bg-[var(--card)] border-[var(--border)] hover:border-[var(--border-strong)]"
              }`}
            >
              {p.popular && (
                <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-[var(--accent)] text-white font-mono text-[10px] font-bold uppercase tracking-wider shadow-md">
                  MOST POPULAR FOR TEAMS
                </div>
              )}

              <div>
                <h3 className="text-xl font-bold text-[var(--foreground)]">{p.name}</h3>
                <p className="text-xs text-[var(--muted-foreground)] mt-1 mb-6">{p.tagline}</p>

                <div className="pb-6 mb-6 border-b border-[var(--border)]">
                  <div className="flex items-baseline gap-1">
                    <span className="text-4xl font-extrabold font-mono text-[var(--foreground)] tracking-tight">
                      {p.price}
                    </span>
                    <span className="text-xs text-[var(--muted)] font-mono">/ {p.period}</span>
                  </div>
                  <div className="text-xs font-semibold text-[var(--accent)] font-mono mt-2">
                    Usage rate: {p.minuteRate}
                  </div>
                </div>

                <ul className="space-y-3 mb-8">
                  {p.features.map((f, idx) => (
                    <li key={idx} className="flex items-start gap-2.5 text-xs text-[var(--foreground)]">
                      <Check className="w-4 h-4 text-[var(--accent)] shrink-0 mt-0.5" />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <a
                href={p.href}
                className={`w-full py-3 rounded-xl text-xs font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer ${
                  p.popular
                    ? "bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white shadow-md shadow-[var(--accent-glow)]"
                    : "bg-[var(--surface-hover)] hover:bg-[var(--border)] text-[var(--foreground)] border border-[var(--border)]"
                }`}
              >
                <span>{p.cta}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </a>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
