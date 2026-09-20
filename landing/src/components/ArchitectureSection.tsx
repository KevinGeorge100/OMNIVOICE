import { Activity, PhoneForwarded, BrainCircuit, Waves, Database, CheckCheck } from "lucide-react";

export default function ArchitectureSection() {
  const steps = [
    {
      num: "01",
      icon: PhoneForwarded,
      title: "Carrier Ingress & Audio Streaming",
      tech: "Exotel / Twilio WebSockets",
      sla: "Stream Chunking",
      desc: "Incoming caller audio streams as chunked 8kHz/16kHz μ-law/linear PCM via full-duplex WebSocket.",
    },
    {
      num: "02",
      icon: Activity,
      title: "Neural VAD & Fast Interruption",
      tech: "Silero ONNX Engine",
      sla: "~18ms VAD · <50ms silence",
      desc: "Instant speech onset detection; silences current playback within 50ms when caller speaks.",
    },
    {
      num: "03",
      icon: Waves,
      title: "Streaming Regional ASR",
      tech: "Sarvam AI Indic STT",
      sla: "Target ~120ms",
      desc: "Sub-second streaming transcript tokens for Hindi, Tamil, Telugu, and 8 other Indian language codes.",
    },
    {
      num: "04",
      icon: Database,
      title: "Fast-Path Cache & FAISS Retrieval",
      tech: "In-Memory Vector Store",
      sla: "<2ms (in-process) · ~15ms FAISS",
      desc: "Approved FAQs bypass LLM inference completely. Complex queries fetch private enterprise vectors.",
    },
    {
      num: "05",
      icon: BrainCircuit,
      title: "Reasoning & Action Gating",
      tech: "Groq LPU (Llama 3.1 8B Instant)",
      sla: "TTFT ~180ms",
      desc: "Low-latency token generation with deterministic confirmation gating on operational writes.",
    },
    {
      num: "06",
      icon: CheckCheck,
      title: "Neural TTS & Carrier Egress",
      tech: "Sarvam Regional Synthesis",
      sla: "Streaming chunks",
      desc: "Streaming acoustic packets sent over bidirectional WebSocket back to the carrier gateway.",
    },
  ];

  return (
    <section id="architecture" className="py-24 relative">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--accent-subtle)] border border-[var(--accent)] text-xs font-mono font-semibold text-[var(--accent)] mb-4">
            <span>FULL-DUPLEX PIPELINE</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-[var(--foreground)] mb-4">
            How OmniVoice targets sub-500ms pipeline turnaround.
          </h2>
          <p className="text-base sm:text-lg text-[var(--muted-foreground)]">
            Every step is optimized for parallel execution, in-memory caching, and low-overhead audio dispatch.
          </p>
        </div>

        {/* 6-Phase Pipeline Architecture Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {steps.map((step) => {
            const Icon = step.icon;
            return (
              <div
                key={step.num}
                className="p-6 rounded-2xl bg-[var(--card)] border border-[var(--border)] hover:border-[var(--border-strong)] transition-all group relative flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-10 h-10 rounded-xl bg-[var(--accent-subtle)] border border-[var(--accent)]/30 flex items-center justify-center text-[var(--accent)]">
                      <Icon className="w-5 h-5" />
                    </div>
                    <span className="text-sm font-mono font-bold text-[var(--accent)]">
                      {step.num}
                    </span>
                  </div>

                  <div className="flex items-center justify-between gap-2 mb-2">
                    <h3 className="text-base font-bold text-[var(--foreground)] group-hover:text-[var(--accent)] transition-colors">
                      {step.title}
                    </h3>
                  </div>

                  <div className="text-[11px] font-mono font-semibold text-[var(--accent)] mb-3">
                    {step.tech} · {step.sla}
                  </div>

                  <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
                    {step.desc}
                  </p>
                </div>

                <div className="mt-6 pt-3 border-t border-[var(--border)] flex items-center justify-between text-[10px] font-mono text-[var(--muted)]">
                  <span>Pipeline Target</span>
                  <span className="font-semibold text-[var(--foreground)]">{step.sla}</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Architecture Summary Banner */}
        <div className="mt-12 p-6 rounded-2xl bg-gradient-to-r from-[var(--card)] via-[var(--surface-hover)] to-[var(--card)] border border-[var(--border-strong)] flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex flex-col">
            <span className="text-xs font-mono font-semibold text-[var(--accent)] uppercase tracking-wider">
              END-TO-END PERFORMANCE BUDGET
            </span>
            <h4 className="text-xl font-bold text-[var(--foreground)] mt-1">
              Architectural &lt;500ms pipeline target
            </h4>
            <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
              Designed for Exotel India audio streams and Twilio telephony connections.
            </p>
          </div>
          <a
            href="http://localhost:8000"
            target="_blank"
            rel="noopener noreferrer"
            className="px-5 py-2.5 rounded-xl font-semibold bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-xs whitespace-nowrap shadow-md shadow-[var(--accent-glow)] transition-all cursor-pointer"
          >
            Inspect Operations Console ↗
          </a>
        </div>
      </div>
    </section>
  );
}
