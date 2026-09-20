"use client";

import { useState, useEffect, useCallback } from "react";

type ScenarioKey = "banking" | "healthcare" | "ecommerce" | "logistics";

interface Turn {
  role: "caller" | "agent" | "event";
  text: string;
  event?: string;
  ms?: string;
}

interface PipelineEvent {
  label: string;
  ms: string;
  type: "normal" | "hit" | "gate";
}

interface Scenario {
  label: string;
  industry: string;
  turns: Turn[];
  waterfall: PipelineEvent[];
}

const SCENARIOS: Record<ScenarioKey, Scenario> = {
  banking: {
    label: "Banking",
    industry: "BFSI · Account Enquiry",
    turns: [
      { role: "caller", text: "Mera savings account ka balance kitna hai?" },
      { role: "event", text: "SPEECH DETECTED", ms: "+0ms" },
      { role: "event", text: "STT PARTIAL: \"Mera savings…\"", ms: "+89ms" },
      { role: "event", text: "STT FINAL · FAISS RETRIEVAL", ms: "+148ms" },
      { role: "event", text: "LLM STREAM START", ms: "+312ms" },
      { role: "agent", text: "Aapke savings account mein abhi ₹18,450 hain. Kya aap pichle 3 transactions dekhna chahte hain?" },
      { role: "event", text: "TTS START · STREAMING AUDIO", ms: "+418ms" },
    ],
    waterfall: [
      { label: "Silero VAD", ms: "17ms", type: "normal" },
      { label: "Sarvam Streaming ASR", ms: "112ms", type: "normal" },
      { label: "FAISS Retrieval", ms: "~15ms", type: "normal" },
      { label: "Groq Llama 3.1 TTFT", ms: "172ms", type: "normal" },
      { label: "Sarvam TTS chunk 1", ms: "102ms", type: "hit" },
      { label: "Pipeline budget total", ms: "<500ms target", type: "hit" },
    ],
  },
  healthcare: {
    label: "Healthcare",
    industry: "Healthcare · Appointment",
    turns: [
      { role: "caller", text: "Kal subah 10 baje ka doctor appointment book kar sakte hain?" },
      { role: "event", text: "SPEECH DETECTED", ms: "+0ms" },
      { role: "event", text: "STT FINAL · ACTION STAGED", ms: "+220ms" },
      { role: "event", text: "CONFIRMATION REQUIRED", ms: "+380ms" },
      { role: "agent", text: "Maine 10:00 AM ka slot secure kar liya hai. Confirm karne ke liye 'Haan, confirm karein' kahein." },
      { role: "event", text: "TTS START · AWAITING CONFIRM", ms: "+460ms" },
    ],
    waterfall: [
      { label: "Silero VAD", ms: "19ms", type: "normal" },
      { label: "Sarvam Streaming ASR", ms: "118ms", type: "normal" },
      { label: "Groq LLM (action)", ms: "182ms", type: "normal" },
      { label: "Confirmation gate", ms: "Blocking write", type: "gate" },
      { label: "Sarvam TTS chunk 1", ms: "108ms", type: "normal" },
    ],
  },
  ecommerce: {
    label: "E-commerce",
    industry: "E-commerce · Tracking",
    turns: [
      { role: "caller", text: "My parcel status please?" },
      { role: "event", text: "SPEECH DETECTED", ms: "+0ms" },
      { role: "event", text: "STT FINAL · FAQ HIT", ms: "+112ms" },
      { role: "event", text: "FAST-PATH CACHE HIT (<2ms in-process)", ms: "+114ms" },
      { role: "agent", text: "Your parcel ORD-9182 is out for delivery and will arrive by 4:30 PM today. Would you like to change the delivery address?" },
      { role: "event", text: "TTS START (LLM BYPASSED)", ms: "+228ms" },
    ],
    waterfall: [
      { label: "Silero VAD", ms: "16ms", type: "normal" },
      { label: "Sarvam ASR", ms: "109ms", type: "normal" },
      { label: "FAQ fast-path (in-process)", ms: "<2ms", type: "hit" },
      { label: "LLM BYPASSED", ms: "0ms saved", type: "hit" },
      { label: "Sarvam TTS chunk 1", ms: "96ms", type: "hit" },
      { label: "Pipeline budget total", ms: "<250ms target", type: "hit" },
    ],
  },
  logistics: {
    label: "Logistics",
    industry: "Logistics · Dispatch",
    turns: [
      { role: "caller", text: "Shipment reroute karein — Mumbai se Pune." },
      { role: "event", text: "SPEECH DETECTED", ms: "+0ms" },
      { role: "event", text: "STT FINAL · ACTION STAGED", ms: "+198ms" },
      { role: "event", text: "BARGE-IN DETECTED — halting playback", ms: "+390ms" },
      { role: "event", text: "CONFIRMATION REQUIRED", ms: "+440ms" },
      { role: "agent", text: "Shipment SHP-4421 ko Mumbai se Pune reroute kar raha hoon. Confirm karne ke liye 'Haan, reroute karein' kahein." },
    ],
    waterfall: [
      { label: "Silero VAD", ms: "18ms", type: "normal" },
      { label: "Sarvam ASR", ms: "115ms", type: "normal" },
      { label: "Groq LLM (reroute)", ms: "176ms", type: "normal" },
      { label: "Barge-in halt", ms: "<50ms design", type: "gate" },
      { label: "Confirmation gate", ms: "Blocking write", type: "gate" },
    ],
  },
};

const SCENARIO_KEYS: ScenarioKey[] = ["banking", "healthcare", "ecommerce", "logistics"];

export default function VoiceSandbox() {
  const [activeKey, setActiveKey] = useState<ScenarioKey>("banking");
  const [visibleTurns, setVisibleTurns] = useState<Turn[]>([]);
  const [running, setRunning] = useState(false);
  const scenario = SCENARIOS[activeKey];

  const runScenario = useCallback(() => {
    if (running) return;
    setRunning(true);
    setVisibleTurns([]);
    scenario.turns.forEach((turn, i) => {
      setTimeout(() => {
        setVisibleTurns(prev => [...prev, turn]);
        if (i === scenario.turns.length - 1) setRunning(false);
      }, i * 700);
    });
  }, [running, scenario]);

  // Reset on scenario change
  useEffect(() => {
    setVisibleTurns([]);
    setRunning(false);
  }, [activeKey]);

  return (
    <section id="sandbox" className="py-24 bg-[var(--card)] border-y border-[var(--border)]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-6 mb-10">
          <div className="max-w-xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--accent-subtle)] border border-[var(--accent)]/30 text-[11px] font-mono font-semibold text-[var(--accent)] mb-5 uppercase tracking-wider">
              Live Call Experience
            </div>
            <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-[var(--foreground)] leading-[1.08] mb-3">
              Watch a call unfold — stage by stage.
            </h2>
            <p className="text-base text-[var(--muted-foreground)] leading-relaxed">
              Select an industry scenario and run the simulation to see how OmniVoice routes caller speech through VAD, ASR, knowledge retrieval, LLM reasoning, and TTS synthesis.
            </p>
          </div>
          <span className="shrink-0 self-start sm:self-end px-3 py-1 rounded-md bg-amber-50 border border-amber-200 text-amber-700 text-xs font-mono font-semibold">
            Browser Simulation — Web Audio API prototype
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.6fr_1fr] gap-5">

          {/* ── LEFT: Scenario selector ── */}
          <div className="flex flex-col gap-2">
            <p className="text-[11px] font-mono font-semibold text-[var(--muted)] uppercase tracking-wider mb-1">Select Scenario</p>
            {SCENARIO_KEYS.map((key) => (
              <button
                key={key}
                onClick={() => setActiveKey(key)}
                aria-pressed={activeKey === key}
                className={`text-left px-4 py-3.5 rounded-xl border transition-all duration-150 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] ${
                  activeKey === key
                    ? "bg-[var(--accent-subtle)] border-[var(--accent)]/50 text-[var(--foreground)]"
                    : "bg-[var(--card)] border-[var(--border)] text-[var(--muted-foreground)] hover:border-[var(--border-strong)] hover:text-[var(--foreground)]"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold">{SCENARIOS[key].label}</span>
                  {activeKey === key && (
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)]" />
                  )}
                </div>
                <span className="text-[11px] font-mono text-[var(--muted)]">{SCENARIOS[key].industry}</span>
              </button>
            ))}

            <button
              onClick={runScenario}
              disabled={running}
              aria-label="Run voice simulation"
              className={`mt-3 w-full py-3 rounded-xl text-sm font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 ${
                running
                  ? "bg-[var(--card-hover)] text-[var(--muted)] border border-[var(--border)] cursor-not-allowed"
                  : "bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white cursor-pointer"
              }`}
            >
              {running ? "Simulating…" : "▶  Run Simulation"}
            </button>
          </div>

          {/* ── CENTER: Conversation transcript ── */}
          <div className="bg-[var(--background)] rounded-2xl border border-[var(--border)] overflow-hidden flex flex-col">
            <div className="px-4 py-3 border-b border-[var(--border)] bg-[var(--card)] flex items-center justify-between">
              <span className="text-xs font-mono font-semibold text-[var(--muted-foreground)]">
                {scenario.industry}
              </span>
              <span className="flex items-center gap-1.5 text-[10px] font-mono text-emerald-600">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                LIVE CALL
              </span>
            </div>

            <div className="flex-1 p-4 space-y-2.5 min-h-[320px]">
              {visibleTurns.length === 0 && (
                <div className="flex items-center justify-center h-full text-sm text-[var(--muted)] font-mono">
                  Press Run to start simulation →
                </div>
              )}
              {visibleTurns.map((turn, i) => {
                if (turn.role === "event") {
                  return (
                    <div key={i} className="flex items-center gap-2 animate-slide-up">
                      <div className="w-px h-4 bg-[var(--border)] ml-3 shrink-0" />
                      <span className="text-[10px] font-mono text-[var(--muted)] flex items-center gap-2">
                        <span className="text-amber-500 font-semibold">{turn.text}</span>
                        {turn.ms && <span className="text-[var(--muted)]">{turn.ms}</span>}
                      </span>
                    </div>
                  );
                }
                if (turn.role === "caller") {
                  return (
                    <div key={i} className="flex items-start gap-3 animate-slide-up">
                      <div className="w-6 h-6 rounded-full bg-sky-100 border border-sky-200 flex items-center justify-center text-[9px] font-bold text-sky-600 shrink-0 mt-0.5">C</div>
                      <div className="flex-1 bg-sky-50 border border-sky-200/60 rounded-xl rounded-tl-sm px-3.5 py-2.5">
                        <p className="text-sm text-[var(--foreground)] font-medium leading-snug">{turn.text}</p>
                      </div>
                    </div>
                  );
                }
                return (
                  <div key={i} className="flex items-start gap-3 flex-row-reverse animate-slide-up">
                    <div className="w-6 h-6 rounded-full bg-emerald-100 border border-emerald-200 flex items-center justify-center text-[9px] font-bold text-emerald-700 shrink-0 mt-0.5">A</div>
                    <div className="flex-1 bg-emerald-50 border border-emerald-200/60 rounded-xl rounded-tr-sm px-3.5 py-2.5">
                      <p className="text-sm text-[var(--foreground)] font-medium leading-snug">{turn.text}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ── RIGHT: Pipeline waterfall ── */}
          <div className="flex flex-col gap-2">
            <p className="text-[11px] font-mono font-semibold text-[var(--muted)] uppercase tracking-wider mb-1">Pipeline Trace</p>
            <div className="flex-1 bg-[var(--background)] rounded-2xl border border-[var(--border)] p-4 space-y-1.5">
              {scenario.waterfall.map((step, i) => (
                <div
                  key={i}
                  className={`px-3 py-2.5 rounded-lg border flex items-center justify-between text-xs font-mono transition-all ${
                    step.type === "hit"
                      ? "bg-emerald-50 border-emerald-200/60 text-emerald-700"
                      : step.type === "gate"
                      ? "bg-amber-50 border-amber-200/60 text-amber-700"
                      : "bg-[var(--card)] border-[var(--border)] text-[var(--muted-foreground)]"
                  }`}
                >
                  <span className="font-medium truncate pr-2">{step.label}</span>
                  <span className="shrink-0 font-semibold tabular-nums">{step.ms}</span>
                </div>
              ))}
            </div>
            <p className="text-[10px] font-mono text-[var(--muted)] leading-relaxed mt-1">
              All timings are design targets or local benchmarks — not PSTN measurements.
            </p>
          </div>

        </div>
      </div>
    </section>
  );
}
