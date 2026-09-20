import { ArrowUpRight, PhoneCall, Terminal } from "lucide-react";

export default function Footer() {
  return (
    <footer className="border-t border-[var(--border)] bg-[#070a10] text-slate-300">
      {/* High-Conversion Bottom CTA */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="rounded-3xl p-8 sm:p-14 bg-gradient-to-br from-emerald-950/50 via-[#0d131f] to-[#0d131f] border border-emerald-500/30 text-center relative overflow-hidden shadow-2xl">
          <div className="relative z-10 max-w-2xl mx-auto">
            <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-xs font-mono font-semibold text-emerald-400 mb-6">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              DEPLOY ON REAL CARRIER TRUNKS
            </span>
            <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-white mb-4">
              Ready to automate your enterprise phone calls?
            </h2>
            <p className="text-sm sm:text-base text-slate-300 mb-8 leading-relaxed">
              Connect your first Exotel or Twilio line in under 5 minutes. Experience sub-500ms voice intelligence in 11 Indian languages.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <a
                href="http://localhost:8000"
                target="_blank"
                rel="noopener noreferrer"
                className="w-full sm:w-auto px-6 py-3.5 rounded-xl font-semibold bg-emerald-500 hover:bg-emerald-600 text-slate-950 flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/25 transition-all cursor-pointer"
              >
                <Terminal className="w-4 h-4" />
                <span>Launch Operations Console ↗</span>
              </a>
              <a
                href="http://localhost:8000/docs"
                target="_blank"
                rel="noopener noreferrer"
                className="w-full sm:w-auto px-6 py-3.5 rounded-xl font-semibold bg-slate-900 hover:bg-slate-800 border border-slate-700 text-white flex items-center justify-center gap-2 transition-all"
              >
                <span>Read API Reference</span>
                <ArrowUpRight className="w-4 h-4 text-slate-400" />
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* Footer Navigation Columns */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 border-t border-slate-800/80">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8">
          {/* Brand Col */}
          <div className="col-span-2">
            <div className="flex items-center gap-2.5 mb-4">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500 flex items-center justify-center text-emerald-400 font-mono font-bold text-sm tracking-tighter">
                ◖◗
              </div>
              <span className="font-bold text-lg tracking-tight text-white">
                omni<span className="text-emerald-400">voice</span>
              </span>
            </div>
            <p className="text-xs text-slate-400 max-w-sm leading-relaxed mb-6">
              The full-duplex voice AI telephony platform for enterprise customer calls. 11 Indian regional languages, sub-500ms turnaround, and safe write confirmation gating.
            </p>
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900 border border-slate-800 text-[11px] font-mono text-slate-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              <span>All Systems Operational (FastAPI v0.1.0)</span>
            </div>
          </div>

          {/* Column 1 */}
          <div>
            <h3 className="font-mono text-xs font-bold text-white uppercase tracking-wider mb-4">
              Platform
            </h3>
            <ul className="space-y-2.5 text-xs text-slate-400">
              <li><a href="#platform" className="hover:text-white transition-colors">Sub-500ms Engine</a></li>
              <li><a href="#voices" className="hover:text-white transition-colors">11 Regional Voices</a></li>
              <li><a href="#architecture" className="hover:text-white transition-colors">Architecture Pipeline</a></li>
              <li><a href="#roi" className="hover:text-white transition-colors">ROI Calculator</a></li>
              <li><a href="#pricing" className="hover:text-white transition-colors">Commercial Pricing</a></li>
            </ul>
          </div>

          {/* Column 2 */}
          <div>
            <h3 className="font-mono text-xs font-bold text-white uppercase tracking-wider mb-4">
              Developers
            </h3>
            <ul className="space-y-2.5 text-xs text-slate-400">
              <li><a href="http://localhost:8000/docs" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">OpenAPI Documentation ↗</a></li>
              <li><a href="http://localhost:8000" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Operations Console ↗</a></li>
              <li><a href="#developers" className="hover:text-white transition-colors">Python SDK</a></li>
              <li><a href="#developers" className="hover:text-white transition-colors">Node.js TypeScript</a></li>
              <li><a href="#developers" className="hover:text-white transition-colors">WebSocket Webhook Spec</a></li>
            </ul>
          </div>

          {/* Column 3 */}
          <div>
            <h3 className="font-mono text-xs font-bold text-white uppercase tracking-wider mb-4">
              Carriers &amp; Legal
            </h3>
            <ul className="space-y-2.5 text-xs text-slate-400">
              <li><a href="#platform" className="hover:text-white transition-colors">Exotel India Gateway</a></li>
              <li><a href="#platform" className="hover:text-white transition-colors">Twilio Global Voice</a></li>
              <li><a href="#" className="hover:text-white transition-colors">SOC2 Compliance</a></li>
              <li><a href="#" className="hover:text-white transition-colors">Privacy Policy</a></li>
              <li><a href="#" className="hover:text-white transition-colors">Terms of Service</a></li>
            </ul>
          </div>
        </div>

        <div className="mt-14 pt-6 border-t border-slate-800/80 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs font-mono text-slate-500">
          <div>© {new Date().getFullYear()} OmniVoice Technologies Inc. All rights reserved.</div>
          <div className="flex items-center gap-6">
            <span>Intelligence, on the line.</span>
            <span>Made for India &amp; Global Telephony</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
