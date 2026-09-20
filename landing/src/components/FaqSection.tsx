"use client";

import { useState } from "react";
import { ChevronDown, HelpCircle } from "lucide-react";

interface FaqItem {
  q: string;
  a: string;
}

const FAQS: FaqItem[] = [
  {
    q: "How does OmniVoice connect to our existing phone numbers?",
    a: "OmniVoice integrates with your existing Exotel Virtual Number or Twilio phone number. When an incoming call arrives, your carrier forwards the bidirectional audio stream to your unique OmniVoice WebSocket endpoint configured via the Operations Console.",
  },
  {
    q: "How is the sub-500ms turnaround target achieved in the pipeline?",
    a: "We design each pipeline stage for low-latency parallel execution: Silero ONNX neural VAD detects speech boundaries in under 20ms, Sarvam AI produces chunked streaming transcripts in ~120ms, approved FAQ in-process cache lookups complete in under 2ms locally, and Groq LPU generates tokens with ~180ms TTFT. Streaming audio synthesis commences while downstream tokens are still generating.",
  },
  {
    q: "What happens if a customer speaks Hinglish or switches languages mid-call?",
    a: "Our Sarvam AI acoustic integration supports Indian regional language codes with code-mixing capabilities. The pipeline processes regional speech and generates grounded responses according to your tenant's configured language and prompt instructions.",
  },
  {
    q: "How does the confirmation gate prevent unauthorized database modifications?",
    a: "Tools are strictly categorized into 'Read' (speculative, run early) and 'Write' (mutations like booking an appointment or changing an address). When a write is staged, OmniVoice requires the caller to speak an exact business confirmation phrase before committing the HTTPS webhook.",
  },
  {
    q: "What are the planned enterprise deployment options for private VPC or on-premise infrastructure?",
    a: "Self-hosting the OmniVoice FastAPI service with in-memory FAISS indexes is supported today in standard Docker environments. Dedicated private VPC deployments, multi-worker Kubernetes configurations, and air-gapped enterprise packages are planned items on our enterprise roadmap.",
  },
  {
    q: "How does the fast-path cache cut our LLM bills by 65%?",
    a: "In real contact centers, over 60% of caller questions are repetitive (e.g. store hours, return policies, order tracking steps). Approved FAQ answers in OmniVoice are indexed in an in-process in-memory cache. When a question matches, the answer is returned locally in under 2ms without calling Groq or paying per-token inference charges.",
  },
];

export default function FaqSection() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  const toggle = (idx: number) => {
    setOpenIndex(openIndex === idx ? null : idx);
  };

  return (
    <section className="py-24 relative">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--accent-subtle)] border border-[var(--accent)] text-xs font-mono font-semibold text-[var(--accent)] mb-4">
            <HelpCircle className="w-3.5 h-3.5" />
            <span>FREQUENTLY ASKED QUESTIONS</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-[var(--foreground)] mb-4">
            Everything you need to know about enterprise telephony AI.
          </h2>
          <p className="text-base text-[var(--muted-foreground)]">
            Got a specific carrier setup or security question? We have answers.
          </p>
        </div>

        <div className="space-y-4">
          {FAQS.map((faq, idx) => {
            const isOpen = openIndex === idx;
            return (
              <div
                key={idx}
                className="rounded-2xl bg-[var(--card)] border border-[var(--border)] overflow-hidden transition-all"
              >
                <button
                  onClick={() => toggle(idx)}
                  className="w-full p-6 text-left flex items-center justify-between gap-4 cursor-pointer hover:bg-[var(--surface-hover)] transition-colors"
                >
                  <span className="text-base font-bold text-[var(--foreground)]">{faq.q}</span>
                  <ChevronDown
                    className={`w-5 h-5 text-[var(--muted)] shrink-0 transition-transform duration-200 ${
                      isOpen ? "rotate-180 text-[var(--accent)]" : ""
                    }`}
                  />
                </button>
                {isOpen && (
                  <div className="px-6 pb-6 pt-1 text-xs sm:text-sm text-[var(--muted-foreground)] leading-relaxed border-t border-[var(--border)]/60">
                    {faq.a}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
