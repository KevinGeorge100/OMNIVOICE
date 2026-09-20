"use client";

import { useState } from "react";
import { Copy, Check, ExternalLink, Terminal } from "lucide-react";

type TabKey = "python" | "curl" | "javascript";

const CODE_TABS: Record<TabKey, { label: string; lang: string; code: string }> = {
  python: {
    label: "Python",
    lang: "python",
    code: `import httpx

API_BASE = "http://localhost:8000/api"
HEADERS = {"Authorization": "Bearer <your-token>"}

# 1. Create or fetch tenant
tenant_res = httpx.post(
    f"{API_BASE}/tenants",
    headers=HEADERS,
    json={"name": "Acme Corp", "language_code": "hi-IN"},
)
tenant = tenant_res.json()
tenant_id = tenant["id"]

# 2. Ingest approved FAQ (<2ms in-process fast-path cache hit)
httpx.post(
    f"{API_BASE}/tenants/{tenant_id}/faqs",
    headers=HEADERS,
    json={
        "question": "What are your support hours?",
        "answer": "Our support team is available Monday to Saturday, 9 AM to 7 PM IST.",
    },
)

# 3. Register a phone line (Exotel or Twilio)
line_res = httpx.post(
    f"{API_BASE}/tenants/{tenant_id}/lines",
    headers=HEADERS,
    json={
        "provider": "exotel",
        "phone_number": "+918045XXXXXX",
        "language_code": "hi-IN",
    },
)
line = line_res.json()
print(f"Line registered: {line['id']}")
print(f"Connect Exotel to: /ws/exotel/{line['id']}/<stream-secret>")`,
  },
  curl: {
    label: "curl",
    lang: "bash",
    code: `# 1. Create tenant
curl -X POST "http://localhost:8000/api/tenants" \\
  -H "Authorization: Bearer <your-token>" \\
  -H "Content-Type: application/json" \\
  -d '{"name":"Acme Corp","language_code":"hi-IN"}'

# 2. Add Approved FAQ (<2ms In-Process Cache)
curl -X POST "http://localhost:8000/api/tenants/TENANT_ID/faqs" \\
  -H "Authorization: Bearer <your-token>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "question": "What are your support hours?",
    "answer": "Monday to Saturday, 9 AM to 7 PM IST."
  }'

# 3. Register a phone line
curl -X POST "http://localhost:8000/api/tenants/TENANT_ID/lines" \\
  -H "Authorization: Bearer <your-token>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "provider": "twilio",
    "phone_number": "+1415XXXXXXX",
    "language_code": "en-IN"
  }'

# 4. List active calls
curl "http://localhost:8000/api/tenants/TENANT_ID/calls" \\
  -H "Authorization: Bearer <your-token>"`,
  },
  javascript: {
    label: "JavaScript",
    lang: "javascript",
    code: `const API_BASE = "http://localhost:8000/api";
const HEADERS = {
  "Authorization": "Bearer <your-token>",
  "Content-Type": "application/json",
};

// 1. Create tenant
const tenantRes = await fetch(\`\${API_BASE}/tenants\`, {
  method: "POST",
  headers: HEADERS,
  body: JSON.stringify({ name: "Acme Corp", language_code: "hi-IN" }),
});
const { id: tenantId } = await tenantRes.json();

// 2. Ingest approved FAQ (<2ms in-process fast-path)
await fetch(\`\${API_BASE}/tenants/\${tenantId}/faqs\`, {
  method: "POST",
  headers: HEADERS,
  body: JSON.stringify({
    question: "What are your support hours?",
    answer: "Monday to Saturday, 9 AM to 7 PM IST.",
  }),
});

// 3. Register phone line
const lineRes = await fetch(\`\${API_BASE}/tenants/\${tenantId}/lines\`, {
  method: "POST",
  headers: HEADERS,
  body: JSON.stringify({
    provider: "exotel",
    phone_number: "+918045XXXXXX",
    language_code: "hi-IN",
  }),
});
const line = await lineRes.json();
console.log("Line registered:", line.id);`,
  },
};

const TAB_KEYS: TabKey[] = ["python", "curl", "javascript"];

export default function CodeShowcase() {
  const [activeTab, setActiveTab] = useState<TabKey>("python");
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(CODE_TABS[activeTab].code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard not available
    }
  };

  return (
    <section id="developers" className="py-24 bg-[#0c1a2e] bg-ink-grid relative overflow-hidden radial-ink-glow">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="flex flex-col xl:flex-row xl:items-start gap-12 xl:gap-16">

          {/* ── LEFT: Heading + CTAs ── */}
          <div className="xl:w-[36%] xl:pt-8">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-[11px] font-mono font-semibold text-emerald-400 mb-5 uppercase tracking-wider">
              REST API
            </div>
            <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-white leading-[1.08] mb-5">
              Integrate in minutes.
            </h2>
            <p className="text-lg text-white/60 leading-relaxed mb-8">
              OmniVoice exposes a clean REST API. Provision tenants, register phone lines, and upload knowledge — then point your carrier to the WebSocket endpoint.
            </p>

            <div className="space-y-3 mb-10">
              {[
                "Full OpenAPI / Swagger documentation",
                "Tenant + line + FAQ management APIs",
                "Real-time call events via WebSocket",
                "Operations Console for live monitoring",
              ].map((item, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span className="w-1 h-1 rounded-full bg-emerald-400 shrink-0" />
                  <span className="text-sm text-white/70">{item}</span>
                </div>
              ))}
            </div>

            <div className="flex flex-col sm:flex-row xl:flex-col gap-3">
              <a
                href="http://localhost:8000/docs"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 px-5 py-3 rounded-xl text-sm font-semibold bg-emerald-500 hover:bg-emerald-600 text-white transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface-ink)]"
              >
                <ExternalLink className="w-4 h-4" />
                OpenAPI Reference ↗
              </a>
              <a
                href="http://localhost:8000"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 px-5 py-3 rounded-xl text-sm font-semibold bg-white/5 hover:bg-white/10 text-white border border-white/10 hover:border-white/20 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30"
              >
                <Terminal className="w-4 h-4" />
                Operations Console ↗
              </a>
            </div>
          </div>

          {/* ── RIGHT: Code block ── */}
          <div className="flex-1 min-w-0">
            <div className="rounded-2xl border border-white/10 overflow-hidden bg-[#132134]">
              {/* Tab bar */}
              <div className="flex items-center justify-between px-4 py-3 border-b border-white/8 bg-white/3">
                <div className="flex items-center gap-1">
                  {TAB_KEYS.map((key) => (
                    <button
                      key={key}
                      onClick={() => setActiveTab(key)}
                      className={`px-3.5 py-1.5 rounded-md text-xs font-mono font-semibold transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 ${
                        activeTab === key
                          ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                          : "text-white/40 hover:text-white/70 hover:bg-white/5"
                      }`}
                    >
                      {CODE_TABS[key].label}
                    </button>
                  ))}
                </div>
                <button
                  onClick={handleCopy}
                  aria-label="Copy code to clipboard"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-mono text-white/40 hover:text-white/80 hover:bg-white/5 transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
                >
                  {copied ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="text-emerald-400">Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      Copy
                    </>
                  )}
                </button>
              </div>

              {/* Code content */}
              <div className="overflow-x-auto">
                <pre className="p-5 text-sm leading-relaxed font-mono text-white/80 whitespace-pre">
                  <code>{CODE_TABS[activeTab].code}</code>
                </pre>
              </div>
            </div>

            {/* API base URL hint */}
            <p className="mt-3 text-xs font-mono text-white/30 text-center">
              API_BASE · http://localhost:8000/api · OpenAPI at /docs
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
