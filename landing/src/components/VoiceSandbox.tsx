"use client";

import { useState } from "react";
import { Volume2, CheckCircle2, ShieldCheck, ShoppingBag, Stethoscope, Landmark, RefreshCw } from "lucide-react";

interface Scenario {
  id: string;
  title: string;
  industry: string;
  icon: typeof ShoppingBag;
  callerTurn: string;
  agentTurn: string;
  actionRequired: boolean;
  confirmationPhrase?: string;
  waterfall: { step: string; ms: string; hit?: boolean }[];
}

const SCENARIOS: Scenario[] = [
  {
    id: "delivery",
    title: "Quick Commerce & Delivery",
    industry: "E-Commerce",
    icon: ShoppingBag,
    callerTurn: "Bhaiya mera order kahan pahuncha hai? Kya delivery address change kar sakte ho?",
    agentTurn: "Aapka order 12 minute mein deliver ho jayega. Address change karne ke liye kripya bolein: 'Haan, naya address confirm karein'.",
    actionRequired: true,
    confirmationPhrase: "Haan, naya address confirm karein",
    waterfall: [
      { step: "Silero VAD", ms: "19ms" },
      { step: "Sarvam Streaming ASR", ms: "112ms" },
      { step: "Grounded Delivery Check", ms: "12ms" },
      { step: "Groq Llama 3.1 TTFT", ms: "172ms" },
      { step: "Hindi Regional TTS", ms: "110ms" },
      { step: "Pipeline Budget Total", ms: "425ms", hit: true },
    ],
  },
  {
    id: "clinic",
    title: "Healthcare Clinic Booking",
    industry: "HealthTech",
    icon: Stethoscope,
    callerTurn: "Dr. Sharma ke paas kal shaam 6 baje ka appointment mil sakta hai?",
    agentTurn: "Haan, kal shaam 6:00 PM ka slot available hai. Booking confirm karne ke liye bole: 'Haan, doctor appointment confirm karein'.",
    actionRequired: true,
    confirmationPhrase: "Haan, doctor appointment confirm karein",
    waterfall: [
      { step: "Silero VAD", ms: "18ms" },
      { step: "Sarvam Streaming ASR", ms: "108ms" },
      { step: "FAISS Slot Lookup", ms: "4ms", hit: true },
      { step: "Groq Llama 3.1 TTFT", ms: "165ms" },
      { step: "Hindi Regional TTS", ms: "114ms" },
      { step: "Pipeline Budget Total", ms: "409ms", hit: true },
    ],
  },
  {
    id: "banking",
    title: "Banking Security & Balance",
    industry: "FinTech",
    icon: Landmark,
    callerTurn: "Mera account balance kitna hai aur kya last transaction credit hua?",
    agentTurn: "Aapke savings account ka current balance ₹24,800 hai. Kal ₹5,000 credit hua tha. Kya aapko mini-statement SMS par chahiye?",
    actionRequired: false,
    waterfall: [
      { step: "Silero VAD", ms: "17ms" },
      { step: "Sarvam Streaming ASR", ms: "115ms" },
      { step: "FAQ Fast-Path (in-process)", ms: "<2ms", hit: true },
      { step: "Groq Token Bypass", ms: "0ms (Bypassed)", hit: true },
      { step: "Direct Audio Cache TTS", ms: "98ms" },
      { step: "Pipeline Budget Total", ms: "232ms", hit: true },
    ],
  },
  {
    id: "renewal",
    title: "Subscription Renewal & Payment",
    industry: "SaaS & InsurTech",
    icon: RefreshCw,
    callerTurn: "Mera policy renewal date kab hai? UPI link bhej do.",
    agentTurn: "Aapki policy kal expire ho rahi hai. Premium ₹1,499 hai. Maine aapke WhatsApp par instant UPI payment link bhej diya hai.",
    actionRequired: true,
    confirmationPhrase: "Haan, payment link bhejo",
    waterfall: [
      { step: "Silero VAD", ms: "18ms" },
      { step: "Sarvam Streaming ASR", ms: "110ms" },
      { step: "CRM Policy Tool Check", ms: "14ms" },
      { step: "Groq Llama 3.1 TTFT", ms: "170ms" },
      { step: "Regional TTS", ms: "112ms" },
      { step: "Pipeline Budget Total", ms: "424ms", hit: true },
    ],
  },
];

export default function VoiceSandbox() {
  const [activeScenario, setActiveScenario] = useState(SCENARIOS[0]);
  const [playing, setPlaying] = useState(false);

  const simulatePlay = () => {
    setPlaying(true);
    try {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new AudioCtx();
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(330, now);
      osc.frequency.exponentialRampToValueAtTime(440, now + 0.4);
      gain.gain.setValueAtTime(0.08, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.8);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.8);
    } catch {}
    setTimeout(() => setPlaying(false), 2000);
  };

  const Icon = activeScenario.icon;

  return (
    <section id="voices" className="py-24 bg-[var(--card)]/40 border-t border-[var(--border)] relative">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--accent-subtle)] border border-[var(--accent)] text-xs font-mono font-semibold text-[var(--accent)] mb-4">
            <span>SIMULATED INDUSTRY WORKFLOWS</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-[var(--foreground)] mb-4">
            Modeled on Indian enterprise call workflows.
          </h2>
          <p className="text-base sm:text-lg text-[var(--muted-foreground)]">
            Explore how OmniVoice models multi-turn conversations with fast-path cache hits and explicit safety confirmation gates in a browser prototype.
          </p>
        </div>

        {/* Scenario Switcher Tabs */}
        <div className="flex items-center justify-center gap-2 flex-wrap mb-10">
          {SCENARIOS.map((s) => {
            const TabIcon = s.icon;
            const isSelected = s.id === activeScenario.id;
            return (
              <button
                key={s.id}
                onClick={() => setActiveScenario(s)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  isSelected
                    ? "bg-[var(--accent)] text-white shadow-md shadow-[var(--accent-glow)] scale-105"
                    : "bg-[var(--card)] text-[var(--muted-foreground)] border border-[var(--border)] hover:text-[var(--foreground)] hover:border-[var(--border-strong)]"
                }`}
              >
                <TabIcon className="w-4 h-4" />
                <span>{s.title}</span>
              </button>
            );
          })}
        </div>

        {/* Interactive Scenario Card */}
        <div className="max-w-4xl mx-auto glass-panel rounded-2xl p-6 sm:p-8 border border-[var(--border-strong)] shadow-xl">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-[var(--border)]">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-[var(--accent-subtle)] border border-[var(--accent)] flex items-center justify-center text-[var(--accent)]">
                <Icon className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-[var(--foreground)]">{activeScenario.title}</h3>
                <span className="text-xs font-mono text-[var(--muted)]">Industry: {activeScenario.industry}</span>
              </div>
            </div>

            <button
              onClick={simulatePlay}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-mono font-semibold transition-all cursor-pointer ${
                playing
                  ? "bg-amber-500 text-white animate-pulse"
                  : "bg-[var(--card)] hover:bg-[var(--surface-hover)] border border-[var(--border-strong)] text-[var(--foreground)]"
              }`}
            >
              <Volume2 className="w-4 h-4 text-[var(--accent)]" />
              <span>{playing ? "Playing Synthesis Audio..." : "Simulate Voice Turn"}</span>
            </button>
          </div>

          {/* Conversation Turns */}
          <div className="space-y-4 py-6">
            <div className="p-4 rounded-xl bg-[var(--card)] border border-[var(--border)]">
              <div className="text-[10px] font-mono font-semibold text-sky-400 mb-1">
                CALLER TURN (SIMULATED AUDIO)
              </div>
              <p className="text-sm font-medium text-[var(--foreground)]">“{activeScenario.callerTurn}”</p>
            </div>

            <div className="p-4 rounded-xl bg-[var(--accent-subtle)]/40 border border-[var(--accent)]/30">
              <div className="flex items-center justify-between text-[10px] font-mono font-semibold text-[var(--accent)] mb-1">
                <span>OMNIVOICE AGENT (FULL-DUPLEX RESPONSE)</span>
                <span className="flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> Grounded In Knowledge
                </span>
              </div>
              <p className="text-sm font-medium text-[var(--foreground)] mb-3">“{activeScenario.agentTurn}”</p>

              {activeScenario.actionRequired && (
                <div className="p-2.5 rounded-lg bg-[var(--card)] border border-amber-500/30 text-xs text-amber-300 font-mono flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-amber-400 shrink-0" />
                  <span>
                    Explicit confirmation phrase required: <strong>“{activeScenario.confirmationPhrase}”</strong>
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Latency Waterfall Breakdown */}
          <div className="pt-4 border-t border-[var(--border)]">
            <div className="text-xs font-mono text-[var(--muted)] mb-3 flex items-center justify-between">
              <span>LATENCY BUDGET BREAKDOWN (PIPELINE TARGET)</span>
              <span className="text-[var(--accent)] font-semibold">Pipeline Target &lt;500ms</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
              {activeScenario.waterfall.map((w, i) => (
                <div
                  key={i}
                  className={`p-2.5 rounded-lg border text-center font-mono ${
                    w.hit
                      ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-400 font-semibold"
                      : "bg-[var(--card)] border-[var(--border)] text-[var(--muted-foreground)]"
                  }`}
                >
                  <div className="text-[10px] truncate">{w.step}</div>
                  <div className="text-xs font-bold mt-1 text-[var(--foreground)]">{w.ms}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
