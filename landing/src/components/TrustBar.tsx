export default function TrustBar() {
  const partners = [
    { name: "EXOTEL", role: "India Audio Stream & Telephony" },
    { name: "TWILIO", role: "Global Telephony Gateway" },
    { name: "SARVAM AI", role: "Indic Speech Models (11 Codes)" },
    { name: "GROQ LPU", role: "Ultra-Fast LLM TTFT" },
    { name: "SILERO ONNX", role: "Neural VAD (<20ms)" },
    { name: "FAISS VECTORS", role: "In-Process Cache (<2ms local)" },
  ];

  return (
    <section className="py-12 border-y border-[var(--border)] bg-[var(--card)]/50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <p className="text-center font-mono text-[11px] font-semibold text-[var(--muted)] uppercase tracking-widest mb-6">
          Enterprise Infrastructure &amp; Carrier Ecosystem
        </p>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-6 items-center">
          {partners.map((p) => (
            <div
              key={p.name}
              className="flex flex-col items-center justify-center p-3 rounded-lg bg-[var(--card)] border border-[var(--border)] hover:border-[var(--border-strong)] transition-all group"
            >
              <span className="font-mono text-xs font-bold tracking-wider text-[var(--foreground)] group-hover:text-[var(--accent)] transition-colors">
                {p.name}
              </span>
              <span className="text-[10px] text-[var(--muted)] text-center mt-1">
                {p.role}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
