"use client";

import { useState } from "react";
import { Copy, Check, Terminal, Code2 } from "lucide-react";

export default function CodeShowcase() {
  const [activeTab, setActiveTab] = useState<"python" | "typescript" | "curl">("python");
  const [copied, setCopied] = useState(false);

  const snippets = {
    python: `import httpx

# OmniVoice REST API (FastAPI backend)
API_BASE = "http://localhost:8000/api"
HEADERS = {"Authorization": "Bearer YOUR_ADMIN_TOKEN"}

# 1. Create regional enterprise tenant
tenant_res = httpx.post(
    f"{API_BASE}/tenants",
    headers=HEADERS,
    json={
        "name": "Swiggy Delivery Ops",
        "language": "hi-IN",
        "greeting": "नमस्ते! स्विगी सपोर्ट में आपका स्वागत है।",
        "confirmation_phrases": ["हाँ, पुष्टि करें"]
    }
)
tenant = tenant_res.json()
tenant_id = tenant["id"]

# 2. Ingest approved FAQ (<2ms in-process fast-path cache hit)
httpx.post(
    f"{API_BASE}/tenants/{tenant_id}/faqs",
    headers=HEADERS,
    json={
        "question": "ऑर्डर कैंसिल कैसे करें?",
        "answer": "आप ऐप के 'Help' सेक्शन में जाकर 60 सेकंड के भीतर कैंसिल कर सकते हैं।",
        "is_active": True
    }
)

# 3. Connect existing Exotel or Twilio phone line
line_res = httpx.post(
    f"{API_BASE}/tenants/{tenant_id}/lines",
    headers=HEADERS,
    json={
        "line_id": "line_delhi_01",
        "carrier": "exotel",
        "phone_number": "+918045681234"
    }
)

print(f"Agent live on {line_res.json()['phone_number']}! Carrier: {line_res.json()['carrier']}")`,

    typescript: `// OmniVoice REST API Integration (FastAPI backend)
const API_BASE = "http://localhost:8000/api";
const HEADERS = {
  "Authorization": "Bearer YOUR_ADMIN_TOKEN",
  "Content-Type": "application/json"
};

async function setupOmniVoice() {
  // 1. Create workspace with regional speech models
  const tenantRes = await fetch(\`\${API_BASE}/tenants\`, {
    method: "POST",
    headers: HEADERS,
    body: JSON.stringify({
      name: "Apollo Clinic Telephony",
      language: "ta-IN", // Tamil Sarvam AI acoustic model
      greeting: "வணக்கம்! அப்பல்லோ கிளினிக் உங்களை வரவேற்கிறது.",
      confirmation_phrases: ["ஆம், உறுதிப்படுத்துங்கள்"]
    })
  });
  const tenant = await tenantRes.json();

  // 2. Connect carrier phone line
  const lineRes = await fetch(\`\${API_BASE}/tenants/\${tenant.id}/lines\`, {
    method: "POST",
    headers: HEADERS,
    body: JSON.stringify({
      line_id: "line_clinic_chennai",
      carrier: "twilio",
      phone_number: "+12025550199"
    })
  });
  const line = await lineRes.json();

  console.log(\`Voice line ready! Carrier: \${line.carrier}\`);
}

setupOmniVoice();`,

    curl: `# 1. Create Regional Enterprise Tenant
curl -X POST "http://localhost:8000/api/tenants" \\
  -H "Authorization: Bearer $OMNI_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "Tata Capital Customer Care",
    "language": "te-IN",
    "greeting": "నమస్కారం! టాటా క్యాపిటల్ సపోర్ట్‌కి స్వాగతం.",
    "confirmation_phrases": ["అవును, కన్ఫర్మ్ చేయండి"]
  }'

# 2. Add Approved FAQ (<2ms In-Process Cache)
curl -X POST "http://localhost:8000/api/tenants/TENANT_ID/faqs" \\
  -H "Authorization: Bearer $OMNI_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "question": "EMI date kab hai?",
    "answer": "Aapki agli EMI tarikh 5 tarikh hai.",
    "is_active": true
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
            Deploy in minutes. Integrate via clean REST APIs.
          </h2>
          <p className="text-base sm:text-lg text-[var(--muted-foreground)]">
            Standard REST endpoints and carrier WebSockets for Python, TypeScript, and cURL. Planned SDK packages on enterprise roadmap.
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
