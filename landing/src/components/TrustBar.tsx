export default function TrustBar() {
  const partners = [
    { name: "Exotel", role: "PSTN Carrier (India)", url: "https://exotel.com" },
    { name: "Twilio", role: "PSTN Carrier (Global)", url: "https://twilio.com" },
    { name: "Sarvam AI", role: "Indic STT · TTS · 11 codes", url: "https://sarvam.ai" },
    { name: "Groq LPU", role: "LLM Inference · TTFT ~180ms", url: "https://groq.com" },
    { name: "Silero ONNX", role: "Neural VAD · ~18ms", url: "https://github.com/snakers4/silero-vad" },
    { name: "FAISS", role: "In-Process Vector Search", url: "https://faiss.ai" },
  ];

  return (
    <div className="bg-[var(--card)] border-y border-[var(--border)]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5">
        <div className="flex flex-col sm:flex-row sm:items-center gap-4 sm:gap-0">
          {/* Label */}
          <div className="shrink-0 sm:pr-8 sm:border-r sm:border-[var(--border)]">
            <span className="text-[11px] font-mono font-semibold tracking-widest uppercase text-[var(--muted)]">
              Infrastructure Stack
            </span>
          </div>

          {/* Partners */}
          <div className="sm:pl-8 flex-1 flex flex-wrap items-center gap-x-7 gap-y-3">
            {partners.map((p, i) => (
              <div key={i} className="flex flex-col">
                <span className="text-sm font-semibold text-[var(--foreground)] leading-none">
                  {p.name}
                </span>
                <span className="text-[11px] text-[var(--muted-foreground)] mt-0.5 leading-none font-mono">
                  {p.role}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
