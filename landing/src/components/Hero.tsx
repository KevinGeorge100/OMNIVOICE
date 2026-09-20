"use client";

import { useState, useRef, useEffect } from "react";
import {
  Play, Pause, PhoneCall, ShieldCheck, Zap, ArrowRight,
  Volume2, Mic, Cpu, Radio,
} from "lucide-react";

interface VoiceDemo {
  lang: string;
  langCode: string;
  native: string;
  callerText: string;
  agentText: string;
  frequencies: number[];
  pipelineTarget: string;
}

const VOICE_DEMOS: VoiceDemo[] = [
  {
    lang: "Hindi",
    langCode: "hi-IN",
    native: "हिंदी",
    callerText: "कल सुबह 10 बजे का डॉक्टर अपॉइंटमेंट बुक कर सकते हैं?",
    agentText: "जी हाँ, मैंने सुबह 10:00 बजे का स्लॉट सुरक्षित कर लिया है। कृपया पुष्टि करने के लिए 'हाँ, पुष्टि करें' कहें।",
    frequencies: [220, 260, 330, 392, 440],
    pipelineTarget: "<500ms",
  },
  {
    lang: "Tamil",
    langCode: "ta-IN",
    native: "தமிழ்",
    callerText: "என் பார்சல் எப்போது டெலிவரி செய்யப்படும்?",
    agentText: "உங்கள் பார்சல் இன்று மாலை 4:30 மணிக்குள் வந்து சேரும். டெலிவரி முகவரியை மாற்ற வேண்டுமா?",
    frequencies: [240, 290, 360, 420, 480],
    pipelineTarget: "<500ms",
  },
  {
    lang: "Telugu",
    langCode: "te-IN",
    native: "తెలుగు",
    callerText: "నా ఖాతా బ్యాలెన్స్ ఎంత ఉంది?",
    agentText: "మీ పొదుపు ఖాతాలో ప్రస్తుత బ్యాలెన్స్ ₹18,450 ఉంది. మీకు చివరి 3 లావాదేవీల వివరాలు కావాలా?",
    frequencies: [210, 250, 315, 380, 430],
    pipelineTarget: "<500ms",
  },
  {
    lang: "English (India)",
    langCode: "en-IN",
    native: "English",
    callerText: "Can you re-route my flight booking to Bangalore tomorrow?",
    agentText: "I've found an open seat on 6E-241 departing at 09:15 AM. To confirm the reschedule, please say: 'Yes, reschedule flight'.",
    frequencies: [250, 300, 375, 450, 500],
    pipelineTarget: "<500ms",
  },
  {
    lang: "Kannada",
    langCode: "kn-IN",
    native: "ಕನ್ನಡ",
    callerText: "ನನ್ನ ಆರ್ಡರ್ ಸ್ಥಿತಿ ಏನು?",
    agentText: "ನಿಮ್ಮ ಆರ್ಡರ್ ಸಾಗಣೆಯಲ್ಲಿದೆ ಮತ್ತು ನಾಳೆ ಮಧ್ಯಾಹ್ನ ತಲುಪಲಿದೆ.",
    frequencies: [230, 275, 345, 410, 460],
    pipelineTarget: "<500ms",
  },
];

export default function Hero() {
  const [activeDemo, setActiveDemo] = useState(VOICE_DEMOS[0]);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackPhase, setPlaybackPhase] = useState<"idle" | "caller" | "processing" | "agent">("idle");
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const animFrameRef = useRef<number | null>(null);

  const playAudioDemo = () => {
    if (isPlaying) { stopAudioDemo(); return; }
    try {
      const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new AudioContextClass();
      audioContextRef.current = ctx;
      setIsPlaying(true);
      setPlaybackPhase("caller");

      const now = ctx.currentTime;
      const callerOsc = ctx.createOscillator();
      const callerGain = ctx.createGain();
      callerOsc.type = "sine";
      callerOsc.frequency.setValueAtTime(activeDemo.frequencies[0], now);
      callerOsc.frequency.exponentialRampToValueAtTime(activeDemo.frequencies[1], now + 0.8);
      callerGain.gain.setValueAtTime(0.01, now);
      callerGain.gain.linearRampToValueAtTime(0.1, now + 0.1);
      callerGain.gain.exponentialRampToValueAtTime(0.001, now + 1.2);
      callerOsc.connect(callerGain);
      callerGain.connect(ctx.destination);
      callerOsc.start(now);
      callerOsc.stop(now + 1.2);

      setTimeout(() => setPlaybackPhase("processing"), 1200);

      setTimeout(() => {
        setPlaybackPhase("agent");
        const agentNow = ctx.currentTime;
        activeDemo.frequencies.forEach((freq, idx) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = "triangle";
          osc.frequency.setValueAtTime(freq, agentNow + idx * 0.28);
          gain.gain.setValueAtTime(0.01, agentNow + idx * 0.28);
          gain.gain.linearRampToValueAtTime(0.12, agentNow + idx * 0.28 + 0.05);
          gain.gain.exponentialRampToValueAtTime(0.001, agentNow + idx * 0.28 + 0.26);
          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start(agentNow + idx * 0.28);
          osc.stop(agentNow + idx * 0.28 + 0.28);
        });
      }, 1600);

      setTimeout(() => { setIsPlaying(false); setPlaybackPhase("idle"); }, 3400);
    } catch {
      setIsPlaying(false);
      setPlaybackPhase("idle");
    }
  };

  const stopAudioDemo = () => {
    audioContextRef.current?.close().catch(() => {});
    audioContextRef.current = null;
    setIsPlaying(false);
    setPlaybackPhase("idle");
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    let phase = 0;

    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const { width, height } = canvas;
      const centerY = height / 2;
      const numBars = 52;
      const barW = 2.5;
      const gap = (width - numBars * barW) / (numBars - 1);

      for (let i = 0; i < numBars; i++) {
        const x = i * (barW + gap);
        let bh = 3;
        if (isPlaying && playbackPhase !== "processing") {
          const intensity = playbackPhase === "agent" ? 1.5 : 0.9;
          bh = Math.abs(Math.sin(i * 0.35 + phase) * Math.cos(i * 0.15 - phase * 0.8) * height * 0.38 * intensity + Math.random() * 7 + 8);
        } else {
          bh = Math.abs(Math.sin(i * 0.22 + phase * 0.25) * 5 + 6);
        }
        bh = Math.max(2, Math.min(height * 0.88, bh));

        if (isPlaying) {
          ctx.fillStyle = playbackPhase === "agent"
            ? "rgba(5, 150, 105, 0.82)"
            : playbackPhase === "processing"
            ? "rgba(251, 191, 36, 0.6)"
            : "rgba(56, 189, 248, 0.82)";
        } else {
          ctx.fillStyle = "rgba(148, 163, 184, 0.28)";
        }
        ctx.fillRect(x, centerY - bh / 2, barW, bh);
      }
      phase += isPlaying ? 0.13 : 0.018;
      animFrameRef.current = requestAnimationFrame(render);
    };

    render();
    return () => { if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current); };
  }, [isPlaying, playbackPhase]);

  const phaseLabel = {
    idle: "Waiting for caller…",
    caller: "Caller speaking — carrier audio ingress",
    processing: "VAD → ASR → Knowledge → LLM…",
    agent: "OmniVoice streaming response",
  }[playbackPhase];

  return (
    <section className="relative pt-28 pb-16 md:pt-36 md:pb-20 overflow-hidden bg-grid-pattern radial-glow">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">

        {/* Editorial Split Layout */}
        <div className="flex flex-col lg:flex-row items-start gap-12 xl:gap-16">

          {/* ─── LEFT COLUMN: Headline + CTAs ─── */}
          <div className="flex-none lg:w-[42%] xl:w-[40%] flex flex-col justify-center pt-4 lg:pt-8">

            {/* Eyebrow */}
            <div className="inline-flex items-center gap-2 mb-6">
              <span className="flex h-1.5 w-1.5 rounded-full bg-[var(--accent)] animate-pulse" />
              <span className="text-[11px] font-mono font-semibold tracking-widest uppercase text-[var(--accent)]">
                Voice AI Infrastructure · Indian Telephony
              </span>
            </div>

            {/* Headline */}
            <h1 className="text-5xl sm:text-6xl lg:text-[64px] xl:text-[72px] font-extrabold tracking-tight text-[var(--foreground)] leading-[1.05] mb-6">
              Voice AI that speaks{" "}
              <span className="text-[var(--accent)]">Indian languages</span>{" "}
              on real phone lines.
            </h1>

            {/* Supporting paragraph */}
            <p className="text-lg text-[var(--muted-foreground)] leading-relaxed max-w-[480px] mb-8">
              Connect enterprise knowledge directly to{" "}
              <strong className="text-[var(--foreground)] font-semibold">Exotel</strong> and{" "}
              <strong className="text-[var(--foreground)] font-semibold">Twilio</strong>.
              Full-duplex speech, streaming neural VAD, and grounded replies — designed for a sub-500ms pipeline.
            </p>

            {/* CTAs */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 mb-8">
              <a
                href="http://localhost:8000"
                target="_blank"
                rel="noopener noreferrer"
                id="hero-cta-console"
                className="flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl text-base font-semibold bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white shadow-md shadow-[var(--accent-glow)] transition-all hover:scale-[1.02] active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2"
              >
                <PhoneCall className="w-4 h-4" />
                Launch Operations Console
                <ArrowRight className="w-4 h-4" />
              </a>
              <a
                href="#sandbox"
                id="hero-cta-sandbox"
                className="flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl text-base font-semibold bg-[var(--card)] hover:bg-[var(--card-hover)] border border-[var(--border)] hover:border-[var(--border-strong)] text-[var(--foreground)] transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2"
              >
                <Volume2 className="w-4 h-4 text-[var(--accent)]" />
                Explore Voice Simulation
              </a>
            </div>

            {/* Evidence strip */}
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-[var(--muted-foreground)]">
              <span className="flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-amber-500" />
                <span>&lt;500ms pipeline target</span>
              </span>
              <span className="text-[var(--border-strong)]">·</span>
              <span className="flex items-center gap-1.5">
                <Radio className="w-3.5 h-3.5 text-[var(--accent)]" />
                <span>11 language codes</span>
              </span>
              <span className="text-[var(--border-strong)]">·</span>
              <span className="flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-[var(--accent)]" />
                <span>Confirmation-gated writes</span>
              </span>
              <span className="text-[var(--border-strong)]">·</span>
              <span className="flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-sky-500" />
                <span>Groq LPU · Sarvam AI · Silero</span>
              </span>
            </div>
          </div>

          {/* ─── RIGHT COLUMN: Realtime Call Visualization ─── */}
          <div className="flex-1 w-full lg:min-w-0">
            <div className="bg-[var(--card)] border border-[var(--border-strong)] rounded-2xl overflow-hidden shadow-xl shadow-black/5">

              {/* Panel header */}
              <div className="flex items-center justify-between px-5 py-3.5 border-b border-[var(--border)] bg-[var(--card-hover)]/50">
                <div className="flex items-center gap-2.5">
                  <div className="flex gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-red-400/70" />
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-400/70" />
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-400/70" />
                  </div>
                  <span className="text-xs font-mono text-[var(--muted-foreground)] ml-1">omnivoice — live call</span>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-600 border border-amber-500/25 font-semibold">
                  BROWSER SIMULATION
                </span>
              </div>

              {/* Language selector */}
              <div className="flex items-center gap-1.5 px-5 py-3 border-b border-[var(--border)] flex-wrap">
                <span className="text-[11px] font-mono text-[var(--muted)] mr-1">LANGUAGE:</span>
                {VOICE_DEMOS.map((demo) => (
                  <button
                    key={demo.langCode}
                    onClick={() => { stopAudioDemo(); setActiveDemo(demo); }}
                    className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] ${
                      activeDemo.langCode === demo.langCode
                        ? "bg-[var(--accent)] text-white font-semibold"
                        : "bg-[var(--card-hover)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] border border-[var(--border)]"
                    }`}
                  >
                    {demo.native}
                  </button>
                ))}
              </div>

              {/* Waveform + play */}
              <div className="px-5 pt-4 pb-2">
                <div className="w-full h-20 mb-3">
                  <canvas ref={canvasRef} width={640} height={80} className="w-full h-full" aria-label="Voice waveform visualization" />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono text-[var(--muted-foreground)] truncate max-w-[65%]">{phaseLabel}</span>
                  <button
                    onClick={playAudioDemo}
                    aria-label={isPlaying ? "Stop simulation" : `Play ${activeDemo.lang} voice simulation`}
                    className={`flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold font-mono tracking-wide transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 ${
                      isPlaying
                        ? "bg-amber-500 text-white hover:bg-amber-600 focus-visible:ring-amber-500"
                        : "bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] focus-visible:ring-[var(--accent)]"
                    }`}
                  >
                    {isPlaying ? <Pause className="w-3 h-3 fill-current" /> : <Play className="w-3 h-3 fill-current" />}
                    {isPlaying ? "Stop" : `Simulate ${activeDemo.lang}`}
                  </button>
                </div>
              </div>

              {/* Conversation trace */}
              <div className="px-5 pb-4 space-y-2 pt-2 border-t border-[var(--border)] mt-2">
                {/* Caller */}
                <div className={`p-3.5 rounded-xl border transition-all duration-300 ${
                  playbackPhase === "caller"
                    ? "bg-sky-50 border-sky-200 dark:bg-sky-950/20 dark:border-sky-800/40"
                    : "bg-[var(--card)] border-[var(--border)]"
                }`}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <Mic className="w-3 h-3 text-sky-500" />
                    <span className="text-[10px] font-mono font-semibold text-sky-500 tracking-wider uppercase">
                      Caller · Carrier audio ingress
                    </span>
                  </div>
                  <p className="text-sm text-[var(--foreground)] font-medium leading-snug">
                    "{activeDemo.callerText}"
                  </p>
                </div>

                {/* Processing indicator */}
                {playbackPhase === "processing" && (
                  <div className="px-3 py-2 rounded-lg bg-amber-50 border border-amber-200/60 dark:bg-amber-950/10 dark:border-amber-800/30">
                    <div className="flex items-center gap-2">
                      <span className="flex gap-0.5">
                        {[0, 1, 2].map((i) => (
                          <span
                            key={i}
                            className="w-1 h-1 rounded-full bg-amber-500"
                            style={{ animation: `pulse 0.8s ${i * 0.15}s ease-in-out infinite` }}
                          />
                        ))}
                      </span>
                      <span className="text-[10px] font-mono text-amber-600">VAD → STT → FAISS/LLM → TTS</span>
                    </div>
                  </div>
                )}

                {/* Agent */}
                <div className={`p-3.5 rounded-xl border transition-all duration-300 ${
                  playbackPhase === "agent"
                    ? "bg-emerald-50 border-emerald-200 dark:bg-emerald-950/20 dark:border-emerald-800/40"
                    : "bg-[var(--card)] border-[var(--border)]"
                }`}>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <Radio className="w-3 h-3 text-[var(--accent)]" />
                      <span className="text-[10px] font-mono font-semibold text-[var(--accent)] tracking-wider uppercase">
                        OmniVoice Agent · Streaming synthesis
                      </span>
                    </div>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--accent-subtle)] text-[var(--accent)] border border-[var(--accent)]/20">
                      Target: {activeDemo.pipelineTarget}
                    </span>
                  </div>
                  <p className="text-sm text-[var(--foreground)] font-medium leading-snug mb-3">
                    "{activeDemo.agentText}"
                  </p>
                  {/* Latency chips */}
                  <div className="flex flex-wrap gap-1.5 pt-2.5 border-t border-[var(--border)]">
                    {[
                      { label: "Silero VAD", val: "~18ms", accent: false },
                      { label: "Sarvam ASR", val: "~110ms", accent: false },
                      { label: "FAQ fast-path", val: "<2ms (local)", accent: true },
                      { label: "Groq TTFT", val: "~175ms", accent: false },
                      { label: "Sarvam TTS", val: "~113ms", accent: false },
                    ].map((chip) => (
                      <span
                        key={chip.label}
                        className={`px-2 py-0.5 rounded text-[10px] font-mono font-medium ${
                          chip.accent
                            ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/25"
                            : "bg-[var(--card-hover)] text-[var(--muted-foreground)] border border-[var(--border)]"
                        }`}
                      >
                        {chip.label} · {chip.val}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Bottom footnote */}
              <div className="px-5 py-2.5 border-t border-[var(--border)] bg-[var(--card-hover)]/40 flex items-center justify-between text-[10px] font-mono text-[var(--muted)]">
                <span className="flex items-center gap-1.5">
                  <ShieldCheck className="w-3 h-3 text-[var(--accent)]" />
                  Deterministic write confirmation · Zero hallucinated writes
                </span>
                <span className="hidden sm:block">Not measured PSTN data — browser prototype only</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
