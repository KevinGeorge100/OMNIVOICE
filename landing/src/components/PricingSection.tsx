import { Check, ArrowRight } from "lucide-react";

export default function PricingSection() {
  const plans = [
    {
      name: "Developer Pilot",
      tagline: "For testing, prototypes, and initial integrations.",
      price: "₹0",
      period: "free forever",
      minuteRate: "₹2.20 / minute",
      popular: false,
      features: [
        "1 Connected phone line (Exotel / Twilio)",
        "1,000 Free pilot voice minutes",
        "11 Indian regional languages",
        "Up to 25 business knowledge documents",
        "Preflight write confirmation gating",
        "Community & Discord support",
      ],
      cta: "Start Free Pilot",
      href: "http://localhost:8000",
    },
    {
      name: "Production Scale",
      tagline: "For growing businesses modernizing call operations.",
      price: "₹9,999",
      period: "per month",
      minuteRate: "₹1.60 / minute",
      popular: true,
      features: [
        "Up to 15 Concurrent phone lines",
        "Priority Groq LPU inference queue",
        "Unlimited private business documents",
        "Sub-500ms guaranteed mouth-to-ear target",
        "Full-duplex real-time transcript streaming",
        "CRM & webhook tool execution audit trail",
        "99.9% Telephony uptime SLA",
        "Email & Slack developer support",
      ],
      cta: "Launch Production Line",
      href: "http://localhost:8000",
    },
    {
      name: "Enterprise Dedicated",
      tagline: "For high-volume contact centers and custom deployments.",
      price: "Custom",
      period: "annual commitment",
      minuteRate: "From ₹1.20 / minute",
      popular: false,
      features: [
        "Unlimited concurrent carrier phone lines",
        "Dedicated Exotel / Twilio SIP trunks",
        "Custom regional acoustic tuning & brand voice",
        "On-Premise or Private VPC deployment",
        "SOC2 Type II & HIPAA compliance pack",
        "Zero-retention ephemeral audio mode",
        "24/7 Dedicated engineering pager duty",
      ],
      cta: "Talk to Enterprise Engineering",
      href: "#contact",
    },
  ];

  return (
    <section id="pricing" className="py-24 bg-[var(--card)]/40 border-t border-[var(--border)] relative">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--accent-subtle)] border border-[var(--accent)] text-xs font-mono font-semibold text-[var(--accent)] mb-4">
            <span>TRANSPARENT PRICING</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-[var(--foreground)] mb-4">
            Predictable plans. Zero hidden carrier markups.
          </h2>
          <p className="text-base sm:text-lg text-[var(--muted-foreground)]">
            Pay only for what you speak. Scale from your first pilot phone line to thousands of concurrent calls.
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
