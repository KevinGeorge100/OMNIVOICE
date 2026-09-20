"use client";

import { useState } from "react";
import { TrendingDown } from "lucide-react";

const BPO_RATE = 22; // ₹/min BPO benchmark
const OMNI_LOW = 6;   // ₹/min indicative
const OMNI_HIGH = 10; // ₹/min indicative
const COGS_LOW = 1.60;
const COGS_HIGH = 1.80;

function formatINR(n: number): string {
  if (n >= 10_00_000) return `₹${(n / 10_00_000).toFixed(1)}L`;
  if (n >= 1_000)     return `₹${(n / 1_000).toFixed(1)}K`;
  return `₹${n.toFixed(0)}`;
}

export default function RoiCalculator() {
  const [calls, setCalls] = useState(5000);
  const [avgDuration, setAvgDuration] = useState(4); // minutes

  const totalMinutes = calls * avgDuration;
  const bpoCost = totalMinutes * BPO_RATE;
  const omniLow  = totalMinutes * OMNI_LOW;
  const omniHigh = totalMinutes * OMNI_HIGH;
  const omniMid  = (omniLow + omniHigh) / 2;
  const savingsLow  = bpoCost - omniHigh;
  const savingsMid  = bpoCost - omniMid;
  const cogsMid     = totalMinutes * ((COGS_LOW + COGS_HIGH) / 2);
  const omniBar     = Math.round((omniMid / bpoCost) * 100);

  return (
    <section id="roi" className="py-24 bg-[var(--background)]">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">

        {/* Header */}
        <div className="max-w-2xl mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--accent-subtle)] border border-[var(--accent)]/30 text-[11px] font-mono font-semibold text-[var(--accent)] mb-5 uppercase tracking-wider">
            Unit Economics
          </div>
          <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-[var(--foreground)] leading-[1.08] mb-4">
            Compare the cost of every call.
          </h2>
          <p className="text-lg text-[var(--muted-foreground)] leading-relaxed">
            Adjust your call volume to see how OmniVoice compares to traditional BPO delivery.
            All figures are indicative estimates only.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

          {/* ── LEFT: Sliders ── */}
          <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-7 flex flex-col gap-7">
            {/* Calls per month */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <label htmlFor="roi-calls" className="text-sm font-semibold text-[var(--foreground)]">
                  Calls per month
                </label>
                <span className="text-sm font-bold font-mono text-[var(--accent)]">
                  {calls.toLocaleString("en-IN")}
                </span>
              </div>
              <input
                id="roi-calls"
                type="range"
                min={500}
                max={100000}
                step={500}
                value={calls}
                onChange={e => setCalls(Number(e.target.value))}
                className="w-full h-2 rounded-full bg-[var(--border)] appearance-none cursor-pointer accent-[var(--accent)]"
              />
              <div className="flex justify-between text-[11px] font-mono text-[var(--muted)] mt-1">
                <span>500</span><span>100,000</span>
              </div>
            </div>

            {/* Avg duration */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <label htmlFor="roi-duration" className="text-sm font-semibold text-[var(--foreground)]">
                  Average call duration
                </label>
                <span className="text-sm font-bold font-mono text-[var(--accent)]">
                  {avgDuration} min
                </span>
              </div>
              <input
                id="roi-duration"
                type="range"
                min={1}
                max={15}
                step={1}
                value={avgDuration}
                onChange={e => setAvgDuration(Number(e.target.value))}
                className="w-full h-2 rounded-full bg-[var(--border)] appearance-none cursor-pointer accent-[var(--accent)]"
              />
              <div className="flex justify-between text-[11px] font-mono text-[var(--muted)] mt-1">
                <span>1 min</span><span>15 min</span>
              </div>
            </div>

            {/* Totals */}
            <div className="pt-5 border-t border-[var(--border)] grid grid-cols-2 gap-4">
              <div>
                <span className="text-[11px] font-mono text-[var(--muted)] block mb-1">Total minutes / month</span>
                <span className="text-xl font-bold font-mono text-[var(--foreground)]">
                  {totalMinutes.toLocaleString("en-IN")}
                </span>
              </div>
              <div>
                <span className="text-[11px] font-mono text-[var(--muted)] block mb-1">Est. monthly savings</span>
                <span className="text-xl font-bold font-mono text-[var(--accent)]">
                  {formatINR(savingsLow)} – {formatINR(savingsMid)}
                </span>
              </div>
            </div>
          </div>

          {/* ── RIGHT: Visual comparison ── */}
          <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-7 flex flex-col gap-5">

            {/* BPO bar */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <div>
                  <span className="text-sm font-semibold text-[var(--foreground)]">Traditional BPO</span>
                  <span className="ml-2 text-[11px] font-mono text-[var(--muted)]">~₹{BPO_RATE}/min est.</span>
                </div>
                <span className="text-base font-bold font-mono text-[var(--foreground)]">{formatINR(bpoCost)}/mo</span>
              </div>
              <div className="w-full h-8 rounded-lg bg-slate-100 border border-slate-200 overflow-hidden">
                <div className="h-full w-full bg-slate-400/50 rounded-lg" />
              </div>
            </div>

            {/* OmniVoice bar */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <div>
                  <span className="text-sm font-semibold text-[var(--foreground)]">OmniVoice</span>
                  <span className="ml-2 text-[11px] font-mono text-[var(--muted)]">₹{OMNI_LOW}–{OMNI_HIGH}/min indicative</span>
                </div>
                <span className="text-base font-bold font-mono text-[var(--accent)]">
                  {formatINR(omniLow)}–{formatINR(omniHigh)}/mo
                </span>
              </div>
              <div className="w-full h-8 rounded-lg bg-emerald-50 border border-emerald-200 overflow-hidden">
                <div
                  className="h-full bg-[var(--accent)] rounded-lg transition-all duration-500"
                  style={{ width: `${omniBar}%` }}
                />
              </div>
            </div>

            {/* Savings callout */}
            <div className="mt-2 p-4 rounded-xl bg-[var(--accent-subtle)] border border-[var(--accent)]/20 flex items-center gap-3">
              <TrendingDown className="w-5 h-5 text-[var(--accent)] shrink-0" />
              <div>
                <span className="text-sm font-bold text-[var(--foreground)] block">
                  Est. {formatINR(savingsLow * 12)} – {formatINR(savingsMid * 12)} annual savings
                </span>
                <span className="text-xs text-[var(--muted-foreground)]">
                  Based on {calls.toLocaleString("en-IN")} calls/month · {avgDuration} min avg · indicative figures
                </span>
              </div>
            </div>

            {/* COGS reference */}
            <div className="pt-4 border-t border-[var(--border)] space-y-1.5">
              <div className="flex justify-between text-xs">
                <span className="text-[var(--muted-foreground)]">Estimated pipeline COGS</span>
                <span className="font-mono font-semibold text-[var(--foreground)]">₹{COGS_LOW}–{COGS_HIGH}/min</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-[var(--muted-foreground)]">Indicative selling range</span>
                <span className="font-mono font-semibold text-[var(--foreground)]">₹{OMNI_LOW}–{OMNI_HIGH}/min</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-[var(--muted-foreground)]">Est. infra COGS this volume</span>
                <span className="font-mono font-semibold text-[var(--accent)]">{formatINR(cogsMid)}/mo</span>
              </div>
            </div>
          </div>
        </div>

        <p className="mt-6 text-xs text-[var(--muted)] text-center leading-relaxed max-w-2xl mx-auto">
          Indicative estimates only. Actual costs depend on deployment configuration, carrier rates, Sarvam AI / Groq API usage tiers, and call patterns.
          BPO benchmark based on publicly available industry estimates for India outbound CX delivery (~₹18–25/min range).
        </p>
      </div>
    </section>
  );
}
