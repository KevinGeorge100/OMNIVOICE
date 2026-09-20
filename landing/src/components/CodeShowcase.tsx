"use client";

import { useState } from "react";
import { Copy, Check, Terminal, Code2 } from "lucide-react";

export default function CodeShowcase() {
  const [activeTab, setActiveTab] = useState<"python" | "typescript" | "curl">("python");
  const [copied, setCopied] = useState(false);

  const snippets = {
    python: `from omnivoice import Client

# Initialize enterprise client
client = Client(token="omni_live_sec_992a8b")

# 1. Create regional enterprise agent
tenant = client.tenants.create(
    name="Swiggy Delivery Ops",
    language="hi-IN",
    greeting="नमस्ते! स्विगी सपोर्ट में आपका स्वागत है।",
    confirmation_phrases=["हाँ, पुष्टि करें"]
)

# 2. Ingest private business FAQ (bypasses LLM tokens)
tenant.faqs.add(
    question="ऑर्डर कैंसिल कैसे करें?",
    answer="आप ऐप के 'Help' सेक्शन में जाकर 60 सेकंड के भीतर कैंसिल कर सकते हैं।",
    approved=True  # Instant <2ms cache playback
)

# 3. Connect existing Exotel or Twilio phone line
line = tenant.lines.connect(
    provider="exotel",
    number="+918045681234"
)

print(f"Agent live on {line.number}! Webhook: {line.webhook_url}")`,

    typescript: `import { OmniVoice } from "@omnivoice/sdk";

// Initialize client with enterprise credentials
const omni = new OmniVoice({ apiKey: process.env.OMNIVOICE_API_KEY });

async function main() {
  // 1. Create workspace with regional speech models
  const enterprise = await omni.tenants.create({
    name: "Apollo Clinic Telephony",
    language: "ta-IN", // Tamil native acoustic model
    greeting: "வணக்கம்! அப்பல்லோ கிளினிக் உங்களை வரவேற்கிறது.",
    confirmationPhrases: ["ஆம், உறுதிப்படுத்துங்கள்"]
  });

  // 2. Upload doctor schedule document
  await enterprise.documents.upload({
    file: "./doctor_schedules.pdf",
    semanticIndexing: true
  });

  // 3. Connect carrier phone line
  const line = await enterprise.lines.connect({
    provider: "twilio",
    number: "+12025550199"
  });

  console.log(\`Voice line ready! Routing audio to \${line.webhookUrl}\`);
}

main();`,

    curl: `curl -X POST "https://api.omnivoice.ai/v1/tenants" \\
  -H "Authorization: Bearer $OMNI_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "Tata Capital Customer Care",
    "language": "te-IN",
    "greeting": "నమస్కారం! టాటా క్యాపిటల్ సపోర్ట్‌కి స్వాగతం.",
    "confirmation_phrases": ["అవును, కన్ఫర్మ్ చేయండి"]
  }'`,
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(snippets[activeTab]);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section id="developers" className="py-24 bg-[var(--card)]/50 border-t border-[var(--border)] relative">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--accent-subtle)] border border-[var(--accent)] text-xs font-mono font-semibold text-[var(--accent)] mb-4">
            <Terminal className="w-3.5 h-3.5" />
            <span>DEVELOPER FIRST</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-[var(--foreground)] mb-4">
            Deploy in minutes. Integrate in 10 lines of code.
          </h2>
          <p className="text-base sm:text-lg text-[var(--muted-foreground)]">
            Simple, idiomatic SDKs for Python, Node.js, and standard REST/WebSocket endpoints.
          </p>
        </div>

        <div className="max-w-4xl mx-auto rounded-2xl overflow-hidden border border-[var(--border-strong)] bg-[#090d14] text-slate-100 shadow-2xl">
          {/* Editor Header */}
          <div className="px-4 py-3 bg-[#0d131f] border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-full bg-rose-500/80" />
                <div className="w-3 h-3 rounded-full bg-amber-500/80" />
                <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
              </div>
              <div className="h-4 w-px bg-slate-800" />
              <div className="flex items-center gap-1">
                {(["python", "typescript", "curl"] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-3 py-1 rounded-md text-xs font-mono transition-all cursor-pointer ${
                      activeTab === tab
                        ? "bg-slate-800 text-emerald-400 font-semibold"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {tab === "python" ? "main.py" : tab === "typescript" ? "index.ts" : "deploy.sh"}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-3 py-1 rounded-md bg-slate-800/80 hover:bg-slate-800 text-xs font-mono text-slate-300 transition-all cursor-pointer"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? "Copied!" : "Copy Code"}</span>
            </button>
          </div>

          {/* Code Block */}
          <div className="p-6 overflow-x-auto text-xs font-mono leading-relaxed text-slate-300">
            <pre className="selection:bg-emerald-500/30">
              <code>{snippets[activeTab]}</code>
            </pre>
          </div>

          {/* Footer Bar */}
          <div className="px-6 py-3 bg-[#0d131f] border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-400">
            <div className="flex items-center gap-2">
              <Code2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Full documentation &amp; interactive OpenAPI Swagger available at /docs</span>
            </div>
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="text-emerald-400 hover:underline"
            >
              Open API Spec ↗
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
