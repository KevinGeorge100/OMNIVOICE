import { Globe2, Waves, ShieldAlert, CheckCircle2, Zap, Lock } from "lucide-react";

const PILLARS = [
  {
    icon: Globe2,
    tag: "INDIC SPEECH",
    title: "Indian-language speech pipeline",
    headline: "11 language codes. Real carrier streams.",
    desc: "Integrated with Sarvam AI's regional speech models — covering Hindi, Tamil, Telugu, Marathi, Bengali, Kannada, Malayalam, Odia, Gujarati, Punjabi, and English (India). Audio arrives as raw 8kHz/16kHz PCM over WebSocket; no transcoding middlayer.",
    bullets: [
      { label: "Silero ONNX VAD", detail: "Speech onset detection ~18ms design target" },
      { label: "Streaming Sarvam ASR", detail: "Chunked partial transcripts ~120ms target" },
      { label: "Sarvam TTS synthesis", detail: "Regional acoustic output streamed back to carrier" },
      { label: "Carrier-native protocols", detail: "Exotel WebSocket stream · Twilio TwiML webhook" },
    ],
    stat: "11",
    statLabel: "Regional language codes",
    accentStat: true,
  },
  {
    icon: Waves,
    tag: "FULL-DUPLEX",
    title: "Full-duplex conversation & interruption",
    headline: "Natural turn-taking. Real barge-in.",
    desc: "OmniVoice's FlexDuo engine maintains a bidirectional audio state machine across the call. When the caller speaks while the agent is responding, VAD halts playback within ~50ms — enabling genuinely interruptible conversations over real PSTN lines.",
    bullets: [
      { label: "Full-duplex WebSocket", detail: "Simultaneous read/write on carrier stream" },
      { label: "Barge-in halt design", detail: "~50ms playback clear on speech onset" },
      { label: "Silence-based EOS", detail: "End-of-speech detection for natural turn handoff" },
      { label: "Backchannel filtering", detail: "Prevents 'hmm', 'ok' from triggering turn switch" },
    ],
    stat: "<50ms",
    statLabel: "Barge-in halt design target",
    accentStat: false,
  },
  {
    icon: ShieldAlert,
    tag: "SAFE ACTIONS",
    title: "Safe enterprise actions & grounding",
    headline: "Zero hallucinated writes. Every time.",
    desc: "Operational tool calls — appointment bookings, address changes, order cancellations — require an explicit caller confirmation phrase before any write is committed. Approved FAQs bypass LLM inference via an in-process cache, cutting token costs and eliminating fabrication risk for known answers.",
    bullets: [
      { label: "Confirmation-gated writes", detail: "Caller must say explicit phrase before commit" },
      { label: "FAISS vector grounding", detail: "Private enterprise documents retrieved per-tenant" },
      { label: "FAQ fast-path cache", detail: "<2ms in-process lookups bypass LLM entirely" },
      { label: "Tenant data isolation", detail: "Scoped per-tenant DB records and vector spaces" },
    ],
    stat: "100%",
    statLabel: "Write confirmation coverage",
    accentStat: true,
  },
];

export default function FeatureGrid() {
  return (
    <section id="platform" className="py-24 bg-[var(--section-alt)]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

        {/* Section header */}
        <div className="max-w-2xl mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--accent-subtle)] border border-[var(--accent)]/30 text-[11px] font-mono font-semibold text-[var(--accent)] mb-5 tracking-wider uppercase">
            Platform Capabilities
          </div>
          <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-[var(--foreground)] leading-[1.08] mb-4">
            Three things OmniVoice does that generic AI doesn&apos;t.
          </h2>
          <p className="text-lg text-[var(--muted-foreground)] leading-relaxed">
            Each pillar is a core differentiator — not a checkbox feature. Real telephony, real interruption, real safety.
          </p>
        </div>

        {/* 3 Pillars */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {PILLARS.map((pillar, idx) => {
            const Icon = pillar.icon;
            return (
              <div
                key={idx}
                className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-8 flex flex-col hover:border-[var(--border-strong)] hover:shadow-sm transition-all duration-200 group"
              >
                {/* Tag + Icon */}
                <div className="flex items-center justify-between mb-6">
                  <div className="w-11 h-11 rounded-xl bg-[var(--accent-subtle)] border border-[var(--accent)]/25 flex items-center justify-center text-[var(--accent)] group-hover:scale-105 transition-transform">
                    <Icon className="w-5 h-5" />
                  </div>
                  <span className="text-[10px] font-mono font-semibold tracking-wider text-[var(--muted)] uppercase">
                    {pillar.tag}
                  </span>
                </div>

                {/* Title + headline */}
                <h3 className="text-xl sm:text-2xl font-bold text-[var(--foreground)] mb-2 leading-snug">
                  {pillar.title}
                </h3>
                <p className="text-sm font-semibold text-[var(--accent)] mb-4">
                  {pillar.headline}
                </p>

                {/* Description */}
                <p className="text-base text-[var(--muted-foreground)] leading-relaxed mb-6">
                  {pillar.desc}
                </p>

                {/* Bullet details */}
                <ul className="space-y-2.5 mb-8 flex-1">
                  {pillar.bullets.map((b, bi) => (
                    <li key={bi} className="flex items-start gap-2.5">
                      <CheckCircle2 className="w-4 h-4 text-[var(--accent)] shrink-0 mt-0.5" />
                      <span className="text-sm text-[var(--foreground)]">
                        <span className="font-semibold">{b.label}</span>
                        {" — "}
                        <span className="text-[var(--muted-foreground)]">{b.detail}</span>
                      </span>
                    </li>
                  ))}
                </ul>

                {/* Stat */}
                <div className="pt-5 border-t border-[var(--border)] flex items-center justify-between">
                  <span className="text-xs text-[var(--muted-foreground)] font-medium">{pillar.statLabel}</span>
                  <span className={`text-2xl font-extrabold font-mono tracking-tight ${
                    pillar.accentStat ? "text-[var(--accent)]" : "text-[var(--foreground)]"
                  }`}>
                    {pillar.stat}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Bottom badge row */}
        <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
          {[
            { icon: Zap, text: "<500ms pipeline design target" },
            { icon: Globe2, text: "Sarvam AI · 11 Indic codes" },
            { icon: Lock, text: "Per-tenant data isolation" },
            { icon: ShieldAlert, text: "Zero hallucinated writes" },
          ].map((badge, i) => {
            const BadgeIcon = badge.icon;
            return (
              <div key={i} className="flex items-center gap-2 px-4 py-2 rounded-full bg-[var(--card)] border border-[var(--border)] text-sm text-[var(--muted-foreground)]">
                <BadgeIcon className="w-3.5 h-3.5 text-[var(--accent)]" />
                <span>{badge.text}</span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
