import { ArrowRight, ExternalLink } from "lucide-react";

const FOOTER_LINKS = {
  Product: [
    { label: "Platform Capabilities", href: "#platform" },
    { label: "Architecture Pipeline", href: "#architecture" },
    { label: "Voice Simulation", href: "#sandbox" },
    { label: "Unit Economics", href: "#roi" },
  ],
  Developers: [
    { label: "OpenAPI Reference", href: "http://localhost:8000/docs" },
    { label: "Operations Console", href: "http://localhost:8000" },
    { label: "REST API", href: "#developers" },
    { label: "FAQ", href: "#faq" },
  ],
  Platform: [
    { label: "Exotel Integration", href: "#architecture" },
    { label: "Twilio Integration", href: "#architecture" },
    { label: "Sarvam AI Speech", href: "#platform" },
    { label: "Groq LPU Inference", href: "#platform" },
  ],
  Company: [
    { label: "GitHub", href: "https://github.com/KevinGeorge100/OMNIVOICE" },
    { label: "Pricing", href: "#pricing" },
  ],
};

export default function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <>
      {/* Dark CTA section */}
      <section className="bg-[var(--surface-ink)] py-20 border-t border-white/5">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <p className="text-[11px] font-mono font-semibold tracking-widest uppercase text-emerald-400 mb-4">
            Ready to deploy
          </p>
          <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-white leading-[1.08] mb-6">
            Deploy OmniVoice on your phone lines.
          </h2>
          <p className="text-lg text-white/55 leading-relaxed max-w-xl mx-auto mb-10">
            Get started with the Operations Console, connect your carrier,
            and configure your first knowledge base — no SaaS lock-in required.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <a
              href="http://localhost:8000"
              target="_blank"
              rel="noopener noreferrer"
              id="footer-cta-primary"
              className="flex items-center gap-2 px-7 py-3.5 rounded-xl text-base font-semibold bg-emerald-500 hover:bg-emerald-600 text-white transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface-ink)]"
            >
              Launch Operations Console
              <ArrowRight className="w-4 h-4" />
            </a>
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noopener noreferrer"
              id="footer-cta-docs"
              className="flex items-center gap-2 px-7 py-3.5 rounded-xl text-base font-semibold bg-white/5 hover:bg-white/10 text-white border border-white/10 hover:border-white/20 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30"
            >
              Read API Docs
            </a>
          </div>
        </div>
      </section>

      {/* Footer proper */}
      <footer className="bg-[#0f172a] border-t border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-14">

          {/* Top: brand + links */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-8 mb-12">
            {/* Brand */}
            <div className="col-span-2 md:col-span-1">
              <a href="#" aria-label="OmniVoice home" className="flex items-center gap-2 mb-4 group">
                <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 text-xs font-mono font-bold">
                  ◖◗
                </div>
                <span className="font-bold text-sm text-white">
                  omni<span className="text-emerald-400">voice</span>
                </span>
              </a>
              <p className="text-sm text-white/40 leading-relaxed max-w-[200px]">
                Enterprise voice AI for Indian telephony infrastructure.
              </p>
              <div className="mt-4 flex items-center gap-3">
                <a
                  href="https://github.com/KevinGeorge100/OMNIVOICE"
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="GitHub repository"
                  className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-white/40 hover:text-white/80 hover:bg-white/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              </div>
            </div>

            {/* Link columns */}
            {Object.entries(FOOTER_LINKS).map(([group, links]) => (
              <div key={group}>
                <h3 className="text-[11px] font-mono font-semibold tracking-widest uppercase text-white/35 mb-4">
                  {group}
                </h3>
                <ul className="space-y-2.5">
                  {links.map((link, i) => (
                    <li key={i}>
                      <a
                        href={link.href}
                        className="text-sm text-white/50 hover:text-white/85 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-emerald-400 rounded"
                      >
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          {/* Bottom bar */}
          <div className="pt-8 border-t border-white/5 flex flex-col sm:flex-row items-center justify-between gap-3">
            <p className="text-xs text-white/25 font-mono">
              © {currentYear} OmniVoice Technologies. All rights reserved.
            </p>
            <div className="flex items-center gap-5">
              <span className="text-xs text-white/20 font-mono">
                v0.1.0 · Local deployment build
              </span>
              <span className="text-xs text-white/20 font-mono">
                Indicative product — not production-certified
              </span>
            </div>
          </div>
        </div>
      </footer>
    </>
  );
}
