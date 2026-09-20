"use client";

import { useState } from "react";
import { Calculator, TrendingUp, DollarSign, CheckCircle } from "lucide-react";

export default function RoiCalculator() {
  const [dailyMinutes, setDailyMinutes] = useState<number>(5000);

  const BPO_RATE = 14.0; // ₹14 per minute for traditional human agent
  const OMNIVOICE_RATE = 1.8; // ₹1.80 per minute for OmniVoice

  const monthlyMinutes = dailyMinutes * 30;
  const monthlyBpoCost = monthlyMinutes * BPO_RATE;
  const monthlyOmniCost = monthlyMinutes * OMNIVOICE_RATE;
  const monthlySavings = monthlyBpoCost - monthlyOmniCost;
  const annualSavings = monthlySavings * 12;
  const savingsPercent = Math.round((monthlySavings / monthlyBpoCost) * 100);

  const formatLakhs = (val: number) => {
    if (val >= 10000000) {
      return `₹${(val / 10000000).toFixed(2)} Cr`;
    }
    if (val >= 100000) {
      return `₹${(val / 100000).toFixed(2)} L`;
    }
    return `₹${val.toLocaleString("en-IN")}`;
  };

  return (
    <section id="roi" className="py-24 relative">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--accent-subtle)] border border-[var(--accent)] text-xs font-mono font-semibold text-[var(--accent)] mb-4">
            <Calculator className="w-3.5 h-3.5" />
            <span>UNIT ECONOMICS ESTIMATOR</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-[var(--foreground)] mb-4">
            Cut your contact center telephony bills by 85%+.
          </h2>
          <p className="text-base sm:text-lg text-[var(--muted-foreground)]">
            Traditional voice BPOs in India charge ₹12–₹16/minute. Estimated OmniVoice pipeline COGS is ₹1.60–₹1.80/minute with target commercial pricing around ₹6–₹10/minute.
          </p>
        </div>

        <div className="max-w-4xl mx-auto glass-panel rounded-3xl p-6 sm:p-10 border border-[var(--border-strong)] shadow-2xl">
          {/* Slider Input */}
          <div className="mb-10">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
              <label htmlFor="daily-minutes-slider" className="text-sm font-bold text-[var(--foreground)] flex items-center gap-2">
                <span>Daily Call Volume</span>
                <span className="text-xs font-normal text-[var(--muted)]">(Inbound + Outbound)</span>
              </label>
              <div className="text-xl font-extrabold font-mono text-[var(--accent)]">
                {dailyMinutes.toLocaleString("en-IN")} minutes / day
              </div>
            </div>

            <input
              id="daily-minutes-slider"
              type="range"
              min={500}
              max={25000}
              step={500}
              value={dailyMinutes}
              onChange={(e) => setDailyMinutes(Number(e.target.value))}
              aria-label="Daily call volume in minutes"
              className="w-full h-2.5 bg-[var(--surface-hover)] rounded-lg appearance-none cursor-pointer accent-[var(--accent)]"
            />
            <div className="flex justify-between text-[11px] font-mono text-[var(--muted)] mt-2">
              <span>500 mins/day</span>
              <span>10,000 mins/day</span>
              <span>25,000 mins/day</span>
            </div>
          </div>

          {/* Comparison Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            {/* Traditional BPO */}
            <div className="p-6 rounded-2xl bg-[var(--card)] border border-[var(--border)] flex flex-col justify-between">
              <div>
                <span className="text-xs font-mono font-semibold text-rose-400">TRADITIONAL BPO</span>
                <h3 className="text-base font-bold text-[var(--foreground)] mt-1">Human Call Center</h3>
                <p className="text-xs text-[var(--muted)] mt-1">₹14.00 / minute avg rate</p>
              </div>
              <div className="mt-6 pt-4 border-t border-[var(--border)]">
                <div className="text-2xl font-extrabold font-mono text-[var(--foreground)]">
                  {formatLakhs(monthlyBpoCost)}
                </div>
                <span className="text-[11px] text-[var(--muted)] font-mono">per month</span>
              </div>
            </div>

            {/* OmniVoice AI */}
            <div className="p-6 rounded-2xl bg-[var(--accent-subtle)] border border-[var(--accent)] flex flex-col justify-between shadow-lg shadow-[var(--accent-glow)]">
              <div>
                <span className="text-xs font-mono font-semibold text-[var(--accent)]">OMNIVOICE BASELINE</span>
                <h3 className="text-base font-bold text-[var(--foreground)] mt-1">Estimated Pipeline COGS</h3>
                <p className="text-xs text-[var(--muted)] mt-1">₹1.80 / minute model baseline</p>
              </div>
              <div className="mt-6 pt-4 border-t border-[var(--accent)]/30">
                <div className="text-2xl font-extrabold font-mono text-[var(--accent)]">
                  {formatLakhs(monthlyOmniCost)}
                </div>
                <span className="text-[11px] text-[var(--muted)] font-mono">per month (est. COGS)</span>
              </div>
            </div>

            {/* Net Savings */}
            <div className="p-6 rounded-2xl bg-gradient-to-br from-emerald-950/40 via-[var(--card)] to-[var(--card)] border border-emerald-500/40 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-semibold text-emerald-400">ESTIMATED EFFICIENCY</span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-300">
                    {savingsPercent}% DELTA
                  </span>
                </div>
                <h3 className="text-base font-bold text-[var(--foreground)] mt-1">Potential Capital Delta</h3>
                <p className="text-xs text-[var(--muted)] mt-1">{formatLakhs(annualSavings)} estimated per year</p>
              </div>
              <div className="mt-6 pt-4 border-t border-emerald-500/30">
                <div className="text-2xl font-extrabold font-mono text-emerald-400">
                  {formatLakhs(monthlySavings)}
                </div>
                <span className="text-[11px] text-[var(--muted)] font-mono">estimated monthly delta</span>
              </div>
            </div>
          </div>

          {/* Value Props Checklist */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-6 border-t border-[var(--border)] text-xs text-[var(--muted-foreground)]">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-[var(--accent)] shrink-0" />
              <span>Zero setup or recruitment delays</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-[var(--accent)] shrink-0" />
              <span>Elastic software concurrency</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-[var(--accent)] shrink-0" />
              <span>24/7 coverage with zero agent turnover</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
