"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

const FAQS = [
  {
    q: "What carriers does OmniVoice support?",
    a: "OmniVoice currently integrates with Exotel (India) and Twilio (global). Exotel uses a bidirectional WebSocket audio stream; Twilio uses a TwiML webhook that redirects to the OmniVoice media WebSocket. Register any phone line you already own — no new number procurement required.",
  },
  {
    q: "Which Indian languages are supported?",
    a: "OmniVoice integrates with Sarvam AI's speech models, which support 11 Indian regional language codes: Hindi (hi-IN), Tamil (ta-IN), Telugu (te-IN), Marathi (mr-IN), Bengali (bn-IN), Kannada (kn-IN), Malayalam (ml-IN), Odia (or-IN), Gujarati (gu-IN), Punjabi (pa-IN), and English (en-IN).",
  },
  {
    q: "How is the sub-500ms turnaround target achieved?",
    a: "We design each pipeline stage for low-latency parallel execution: Silero ONNX neural VAD detects speech boundaries in under 20ms, Sarvam AI produces chunked streaming transcripts targeting ~120ms, approved FAQ in-process cache lookups complete in under 2ms locally, and Groq LPU generates tokens with ~180ms TTFT. Streaming audio synthesis commences while downstream tokens are still generating. These are design targets and local benchmarks — real PSTN timings will vary with carrier and network conditions.",
  },
  {
    q: "How does the fast-path cache cut LLM costs?",
    a: "In real contact centers, over 60% of caller questions are repetitive (store hours, return policies, order tracking steps). Approved FAQ answers in OmniVoice are indexed in an in-process in-memory cache. When a question matches, the answer is returned locally in under 2ms without calling Groq or paying per-token inference charges.",
  },
  {
    q: "Is caller write data safe? Can the AI make unauthorized changes?",
    a: "All operational tool calls — appointment bookings, address changes, order cancellations — require an explicit caller confirmation phrase before any write is committed. The system stages the action and waits for the caller to verbally confirm using a deterministic phrase check. No write occurs without confirmation.",
  },
  {
    q: "What does 'full-duplex' mean in this context?",
    a: "OmniVoice maintains simultaneous read and write on the carrier WebSocket — meaning caller audio is processed while agent audio is streaming. Barge-in (caller interrupting the agent) triggers an immediate halt of outgoing playback via Silero VAD, targeting less than 50ms silence-to-halt latency. This enables natural conversation rather than rigid turn-based interaction.",
  },
  {
    q: "What is the pricing model?",
    a: "OmniVoice's current pricing is indicative only — billing enforcement is not yet implemented. The estimated pipeline infrastructure COGS is approximately ₹1.60–1.80 per minute. Indicative commercial selling ranges from ₹6–10 per minute depending on volume and features. These figures will change as the product matures toward production. Contact us to discuss pilot deployment terms.",
  },
];

export default function FaqSection() {
  const [openIdx, setOpenIdx] = useState<number | null>(null);

  return (
    <section id="faq" className="py-24 bg-[var(--background)]">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">

        {/* Header */}
        <div className="mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--accent-subtle)] border border-[var(--accent)]/30 text-[11px] font-mono font-semibold text-[var(--accent)] mb-5 uppercase tracking-wider">
            FAQ
          </div>
          <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-[var(--foreground)] leading-[1.08]">
            Common questions.
          </h2>
        </div>

        {/* Accordion */}
        <div className="divide-y divide-[var(--border)]">
          {FAQS.map((faq, i) => {
            const isOpen = openIdx === i;
            return (
              <div key={i}>
                <button
                  onClick={() => setOpenIdx(isOpen ? null : i)}
                  aria-expanded={isOpen}
                  aria-controls={`faq-answer-${i}`}
                  id={`faq-trigger-${i}`}
                  className="w-full flex items-center justify-between gap-4 py-5 text-left group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-inset rounded-sm"
                >
                  <span className={`text-base font-semibold leading-snug transition-colors ${
                    isOpen ? "text-[var(--accent)]" : "text-[var(--foreground)] group-hover:text-[var(--accent)]"
                  }`}>
                    {faq.q}
                  </span>
                  <ChevronDown
                    className={`w-5 h-5 shrink-0 text-[var(--muted)] transition-transform duration-200 ${
                      isOpen ? "rotate-180 text-[var(--accent)]" : ""
                    }`}
                  />
                </button>
                <div
                  id={`faq-answer-${i}`}
                  role="region"
                  aria-labelledby={`faq-trigger-${i}`}
                  hidden={!isOpen}
                  className="overflow-hidden"
                >
                  <p className="pb-6 text-base text-[var(--muted-foreground)] leading-relaxed max-w-[65ch]">
                    {faq.a}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
