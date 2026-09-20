"use client";

import { useState } from "react";
import { Activity, PhoneForwarded, BrainCircuit, Waves, Database, CheckCheck, ChevronRight } from "lucide-react";

const PIPELINE_NODES = [
  {
    id: "pstn",
    num: "01",
    icon: PhoneForwarded,
    title: "Carrier Ingress",
    tech: "Exotel · Twilio",
    detail: "8kHz/16kHz PCM over WebSocket",
    slaLabel: "STREAM",
    sla: "Full-duplex",
  },
  {
    id: "vad",
    num: "02",
    icon: Activity,
    title: "Neural VAD",
    tech: "Silero ONNX",
    detail: "Speech onset and barge-in detection",
    slaLabel: "TARGET",
    sla: "~18ms",
  },
  {
    id: "asr",
    num: "03",
    icon: Waves,
    title: "Streaming ASR",
    tech: "Sarvam AI Indic STT",
    detail: "11 Indian language codes, chunked",
    slaLabel: "TARGET",
    sla: "~120ms",
  },
  {
    id: "rag",
    num: "04",
    icon: Database,
    title: "Knowledge & Cache",
    tech: "FAISS · In-Process",
    detail: "FAQ fast-path bypass or vector retrieval",
    slaLabel: "LOCAL BENCHMARK",
    sla: "<2ms / ~15ms",
  },
  {
    id: "llm",
    num: "05",
    icon: BrainCircuit,
    title: "Reasoning & Gating",
    tech: "Groq Llama 3.1 8B",
    detail: "Confirmation gated on all write actions",
    slaLabel: "TARGET",
    sla: "~180ms TTFT",
  },
  {
    id: "tts",
    num: "06",
    icon: CheckCheck,
    title: "TTS & Egress",
    tech: "Sarvam Regional Synthesis",
    detail: "Streaming audio back to carrier WebSocket",
    slaLabel: "DESIGN BUDGET",
    sla: "<500ms total",
  },
];

export default function ArchitectureSection() {
  const [activeNode, setActiveNode] = useState<string | null>(null);

  return (
    <section id="architecture" className="py-24 bg-[var(--background)]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

        {/* Header */}
        <div className="max-w-2xl mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--accent-subtle)] border border-[var(--accent)]/30 text-[11px] font-mono font-semibold text-[var(--accent)] mb-5 uppercase tracking-wider">
            Full-Duplex Pipeline
          </div>
          <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-[var(--foreground)] leading-[1.08] mb-4">
            How a call flows through OmniVoice.
          </h2>
          <p className="text-lg text-[var(--muted-foreground)] leading-relaxed">
            Six stages in series, each optimized for low overhead. Latency figures are design targets and local benchmarks — not certified PSTN measurements.
          </p>
        </div>

        {/* Desktop pipeline — horizontal */}
        <div className="hidden lg:block">
          {/* Pipeline row */}
          <div className="relative flex items-stretch gap-0">
            {PIPELINE_NODES.map((node, i) => {
              const Icon = node.icon;
              const isActive = activeNode === node.id;
              const isLast = i === PIPELINE_NODES.length - 1;
              return (
                <div key={node.id} className="flex items-center flex-1">
                  {/* Node card */}
                  <button
                    onClick={() => setActiveNode(isActive ? null : node.id)}
                    aria-expanded={isActive}
                    aria-label={`Pipeline step ${node.num}: ${node.title}`}
                    className={`flex-1 p-5 rounded-xl border text-left transition-all duration-200 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] ${
                      isActive
                        ? "bg-[var(--accent-subtle)] border-[var(--accent)]/50 shadow-sm"
                        : "bg-[var(--card)] border-[var(--border)] hover:border-[var(--border-strong)] hover:bg-[var(--card-hover)]"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className={`w-9 h-9 rounded-lg flex items-center justify-center transition-colors ${
                        isActive ? "bg-[var(--accent)] text-white" : "bg-[var(--accent-subtle)] text-[var(--accent)]"
                      }`}>
                        <Icon className="w-4 h-4" />
                      </div>
                      <span className="text-[10px] font-mono font-bold text-[var(--muted)]">{node.num}</span>
                    </div>
                    <h3 className="text-sm font-bold text-[var(--foreground)] mb-1 leading-tight">{node.title}</h3>
                    <p className="text-[11px] font-mono text-[var(--accent)] font-semibold mb-2">{node.tech}</p>
                    <div className={`text-[10px] font-mono px-1.5 py-0.5 rounded inline-flex items-center gap-1 ${
                      isActive
                        ? "bg-[var(--accent)]/15 text-[var(--accent)] border border-[var(--accent)]/25"
                        : "bg-[var(--card-hover)] text-[var(--muted)] border border-[var(--border)]"
                    }`}>
                      <span className="font-semibold">{node.slaLabel}</span> {node.sla}
                    </div>
                  </button>

                  {/* Connector */}
                  {!isLast && (
                    <div className="relative flex items-center shrink-0 mx-1 w-8">
                      <div className="w-full h-[1px] bg-[var(--border-strong)]" />
                      <ChevronRight className="w-3.5 h-3.5 text-[var(--border-strong)] absolute right-0 -translate-y-0" />
                      {/* Animated packet */}
                      <span
                        className="packet-dot absolute w-1.5 h-1.5 rounded-full bg-[var(--accent)] left-0"
                        aria-hidden="true"
                        style={{ animationDelay: `${i * 0.4}s` }}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Expanded detail panel */}
          {activeNode && (() => {
            const node = PIPELINE_NODES.find(n => n.id === activeNode);
            if (!node) return null;
            return (
              <div className="mt-4 p-5 rounded-xl bg-[var(--card)] border border-[var(--accent)]/30 animate-slide-up">
                <p className="text-sm text-[var(--foreground)] font-medium">{node.detail}</p>
                <p className="text-xs text-[var(--muted-foreground)] mt-1 font-mono">
                  {node.slaLabel}: <span className="text-[var(--accent)] font-semibold">{node.sla}</span>
                </p>
              </div>
            );
          })()}
        </div>

        {/* Mobile / tablet — vertical stacked list */}
        <div className="lg:hidden space-y-2">
          {PIPELINE_NODES.map((node, i) => {
            const Icon = node.icon;
            const isLast = i === PIPELINE_NODES.length - 1;
            return (
              <div key={node.id}>
                <div className="flex items-start gap-4 p-4 rounded-xl bg-[var(--card)] border border-[var(--border)]">
                  <div className="flex flex-col items-center shrink-0">
                    <div className="w-9 h-9 rounded-lg bg-[var(--accent-subtle)] flex items-center justify-center text-[var(--accent)]">
                      <Icon className="w-4 h-4" />
                    </div>
                    {!isLast && <div className="w-px flex-1 min-h-4 bg-[var(--border)] mt-2" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <h3 className="text-sm font-bold text-[var(--foreground)]">{node.title}</h3>
                      <span className="text-[10px] font-mono text-[var(--muted)] shrink-0">{node.num}</span>
                    </div>
                    <p className="text-xs font-mono text-[var(--accent)] font-semibold mb-1">{node.tech}</p>
                    <p className="text-xs text-[var(--muted-foreground)]">{node.detail}</p>
                    <span className="inline-flex mt-2 text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--card-hover)] text-[var(--muted)] border border-[var(--border)]">
                      {node.slaLabel}: {node.sla}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Summary banner */}
        <div className="mt-10 p-6 rounded-2xl bg-[var(--card)] border border-[var(--border-strong)] flex flex-col sm:flex-row items-center justify-between gap-5">
          <div>
            <span className="text-[10px] font-mono font-semibold text-[var(--accent)] uppercase tracking-widest block mb-1">
              End-to-End Performance Budget
            </span>
            <h4 className="text-xl font-bold text-[var(--foreground)]">
              Architectural &lt;500ms pipeline design target
            </h4>
            <p className="text-sm text-[var(--muted-foreground)] mt-1">
              All latency figures are design targets or local benchmarks — not certified PSTN measurements.
              Real-world PSTN timings will vary with carrier, network, and infrastructure conditions.
            </p>
          </div>
          <a
            href="http://localhost:8000"
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 px-5 py-2.5 rounded-xl font-semibold text-sm bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white shadow-sm transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2"
          >
            Inspect Operations Console ↗
          </a>
        </div>
      </div>
    </section>
  );
}
