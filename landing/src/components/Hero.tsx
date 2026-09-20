"use client";

import { useState, useRef, useEffect } from "react";
import { Play, Pause, PhoneCall, Sparkles, ShieldCheck, Zap, ArrowRight, Volume2 } from "lucide-react";

interface VoiceDemo {
  lang: string;
  langCode: string;
  native: string;
  callerAudio: string;
  agentAudio: string;
  callerText: string;
  agentText: string;
  frequencies: number[];
  p95: string;
}

const VOICE_DEMOS: VoiceDemo[] = [
  {
    lang: "Hindi",
    langCode: "hi-IN",
    native: "हिंदी",
    callerAudio: "कल सुबह 10 बजे का डॉक्टर अपॉइंटमेंट बुक कर सकते हैं?",
    agentAudio: "जी हाँ, मैंने सुबह 10:00 बजे का स्लॉट सुरक्षित कर लिया है। कृपया पुष्टि करने के लिए 'हाँ, पुष्टि करें' कहें।",
    callerText: "कल सुबह 10 बजे का डॉक्टर अपॉइंटमेंट बुक कर सकते हैं?",
    agentText: "जी हाँ, मैंने सुबह 10:00 बजे का स्लॉट सुरक्षित कर लिया है। कृपया पुष्टि करने के लिए 'हाँ, पुष्टि करें' कहें।",
    frequencies: [220, 260, 330, 392, 440],
    p95: "412ms",
  },
  {
    lang: "Tamil",
    langCode: "ta-IN",
    native: "தமிழ்",
    callerAudio: "என் பார்சல் எப்போது டெலிவரி செய்யப்படும்?",
    agentAudio: "உங்கள் பார்சல் இன்று மாலை 4:30 மணிக்குள் வந்து சேரும். டெலிவரி முகவரியை மாற்ற வேண்டுமா?",
    callerText: "என் பார்சல் எப்போது டெலிவரி செய்யப்படும்?",
    agentText: "உங்கள் பார்சல் இன்று மாலை 4:30 மணிக்குள் வந்து சேரும். டெலிவரி முகவரியை மாற்ற வேண்டுமா?",
    frequencies: [240, 290, 360, 420, 480],
    p95: "428ms",
  },
  {
    lang: "Telugu",
    langCode: "te-IN",
    native: "తెలుగు",
    callerAudio: "నా ఖాతా బ్యాలెన్స్ ఎంత ఉంది?",
    agentAudio: "మీ పొదుపు ఖాతాలో ప్రస్తుత బ్యాలెన్స్ ₹18,450 ఉంది. మీకు చివరి 3 లావాదేవీల వివరాలు కావాలా?",
    callerText: "నా ఖాతా బ్యాలెన్స్ ఎంత ఉంది?",
    agentText: "మీ పొదుపు ఖాతాలో ప్రస్తుత బ్యాలెన్స్ ₹18,450 ఉంది. మీకు చివరి 3 లావాదేవీల వివరాలు కావాలా?",
    frequencies: [210, 250, 315, 380, 430],
    p95: "435ms",
  },
  {
    lang: "English (India)",
    langCode: "en-IN",
    native: "English",
    callerAudio: "Can you re-route my flight booking to Bangalore tomorrow?",
    agentAudio: "I've found an open seat on 6E-241 departing at 09:15 AM. To confirm the reschedule, please say: 'Yes, reschedule flight'.",
    callerText: "Can you re-route my flight booking to Bangalore tomorrow?",
    agentText: "I've found an open seat on 6E-241 departing at 09:15 AM. To confirm the reschedule, please say: 'Yes, reschedule flight'.",
    frequencies: [250, 300, 375, 450, 500],
    p95: "395ms",
  },
  {
    lang: "Kannada",
    langCode: "kn-IN",
    native: "ಕನ್ನಡ",
    callerAudio: "ನನ್ನ ಆರ್ಡರ್ ಸ್ಥಿತಿ ಏನು?",
    agentAudio: "ನಿಮ್ಮ ಆರ್ಡರ್ ಸಾಗಣೆಯಲ್ಲಿದೆ ಮತ್ತು ನಾಳೆ ಮಧ್ಯಾಹ್ನ ತಲುಪಲಿದೆ.",
    callerText: "ನನ್ನ ಆರ್ಡರ್ ಸ್ಥಿತಿ ಏನು?",
    agentText: "ನಿಮ್ಮ ಆರ್ಡರ್ ಸಾಗಣೆಯಲ್ಲಿದೆ ಮತ್ತು ನಾಳೆ ಮಧ್ಯಾಹ್ನ ತಲುಪಲಿದೆ.",
    frequencies: [230, 275, 345, 410, 460],
    p95: "440ms",
  },
];

export default function Hero() {
  const [activeDemo, setActiveDemo] = useState(VOICE_DEMOS[0]);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackPhase, setPlaybackPhase] = useState<"idle" | "caller" | "agent">("idle");
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Play synthetic audio demo via Web Audio API
  const playAudioDemo = () => {
    if (isPlaying) {
      stopAudioDemo();
      return;
    }

    try {
      const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new AudioContextClass();
      audioContextRef.current = ctx;

      setIsPlaying(true);
      setPlaybackPhase("caller");

      // Play caller simulated phrase tone
      const now = ctx.currentTime;
      const callerOsc = ctx.createOscillator();
      const callerGain = ctx.createGain();
      callerOsc.type = "sine";
      callerOsc.frequency.setValueAtTime(activeDemo.frequencies[0], now);
      callerOsc.frequency.exponentialRampToValueAtTime(activeDemo.frequencies[1], now + 0.8);

      callerGain.gain.setValueAtTime(0.01, now);
      callerGain.gain.linearRampToValueAtTime(0.12, now + 0.1);
      callerGain.gain.exponentialRampToValueAtTime(0.001, now + 1.2);

      callerOsc.connect(callerGain);
      callerGain.connect(ctx.destination);
      callerOsc.start(now);
      callerOsc.stop(now + 1.2);

      // Phase change to agent response after 1.2s
      setTimeout(() => {
        setPlaybackPhase("agent");
        const agentNow = ctx.currentTime;

        // Play agent multi-tone sequence
        activeDemo.frequencies.forEach((freq, idx) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = "triangle";
          osc.frequency.setValueAtTime(freq, agentNow + idx * 0.3);

          gain.gain.setValueAtTime(0.01, agentNow + idx * 0.3);
          gain.gain.linearRampToValueAtTime(0.15, agentNow + idx * 0.3 + 0.05);
          gain.gain.exponentialRampToValueAtTime(0.001, agentNow + idx * 0.3 + 0.28);

          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start(agentNow + idx * 0.3);
          osc.stop(agentNow + idx * 0.3 + 0.3);
        });
      }, 1300);

      // Reset when done
      setTimeout(() => {
        setIsPlaying(false);
        setPlaybackPhase("idle");
      }, 3200);
    } catch {
      setIsPlaying(false);
      setPlaybackPhase("idle");
    }
  };

  const stopAudioDemo = () => {
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    setIsPlaying(false);
    setPlaybackPhase("idle");
  };

  // Canvas waveform visualizer
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let phase = 0;

    const renderWave = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const width = canvas.width;
      const height = canvas.height;
      const centerY = height / 2;

      const numBars = 48;
      const barWidth = 3;
      const gap = (width - numBars * barWidth) / (numBars - 1);

      for (let i = 0; i < numBars; i++) {
        const x = i * (barWidth + gap);
        let barHeight = 4;

        if (isPlaying) {
          const intensity = playbackPhase === "agent" ? 1.4 : 0.8;
          barHeight =
            Math.sin(i * 0.35 + phase) * Math.cos(i * 0.15 - phase * 0.8) * (height * 0.38) * intensity +
            Math.random() * 8 +
            10;
        } else {
          barHeight = Math.sin(i * 0.25 + phase * 0.3) * 6 + 8;
        }

        barHeight = Math.max(3, Math.min(height * 0.85, Math.abs(barHeight)));

        // Gradient
        const isAgent = playbackPhase === "agent";
        ctx.fillStyle = isPlaying
          ? isAgent
            ? "rgba(16, 185, 129, 0.85)"
            : "rgba(56, 189, 248, 0.85)"
          : "rgba(148, 163, 184, 0.35)";

        ctx.fillRect(x, centerY - barHeight / 2, barWidth, barHeight);
      }

      phase += isPlaying ? 0.12 : 0.02;
      animationFrameRef.current = requestAnimationFrame(renderWave);
    };

    renderWave();

    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    };
  }, [isPlaying, playbackPhase]);

  return (
    <section className="relative pt-32 pb-20 md:pt-40 md:pb-28 overflow-hidden bg-grid-pattern radial-glow">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="flex flex-col items-center text-center max-w-4xl mx-auto">
          {/* Announcement Pill */}
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[var(--card)] border border-[var(--border-strong)] text-xs font-mono text-[var(--muted-foreground)] mb-8 shadow-sm hover:border-[var(--accent)] transition-colors">
            <span className="flex h-2 w-2 rounded-full bg-[var(--accent)] animate-ping" />
            <span className="text-[var(--accent)] font-semibold">Sub-500ms Engine</span>
            <span>·</span>
            <span>11 Indian Regional Languages Ready</span>
            <ArrowRight className="w-3 h-3 text-[var(--muted)]" />
          </div>

          {/* Display Headline */}
          <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-[var(--foreground)] leading-[1.08] mb-6">
            Voice AI that speaks <span className="text-transparent bg-clip-text bg-gradient-to-r from-[var(--accent)] via-emerald-400 to-teal-300">Indian languages</span> on real phone lines.
          </h1>

          {/* Subheading */}
          <p className="text-base sm:text-xl text-[var(--muted-foreground)] max-w-2xl mb-10 leading-relaxed">
            Connect your enterprise knowledge and CRM tools directly to <strong>Exotel</strong> and <strong>Twilio</strong>. 
            Full-duplex speech, streaming neural VAD, and grounded replies with sub-500ms turnaround.
          </p>

          {/* CTAs */}
          <div className="flex flex-col sm:flex-row items-center gap-4 w-full sm:w-auto mb-16">
            <a
              href="http://localhost:8000"
              target="_blank"
              rel="noopener noreferrer"
              className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl font-semibold bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white shadow-lg shadow-[var(--accent-glow)] transition-all hover:scale-[1.02] cursor-pointer"
            >
              <PhoneCall className="w-4 h-4" />
              <span>Launch Operations Console ↗</span>
            </a>
            <a
              href="#sandbox"
              className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl font-semibold bg-[var(--card)] hover:bg-[var(--card-hover)] border border-[var(--border)] hover:border-[var(--border-strong)] text-[var(--foreground)] transition-all"
            >
              <Volume2 className="w-4 h-4 text-[var(--accent)]" />
              <span>Try Live Audio Demo</span>
            </a>
          </div>
        </div>

        {/* Interactive Live Audio & Waveform Widget */}
        <div className="max-w-4xl mx-auto glass-panel rounded-2xl p-6 sm:p-8 shadow-2xl border border-[var(--border-strong)] relative overflow-hidden">
          {/* Header row */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-[var(--border)]">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-[var(--accent-subtle)] border border-[var(--accent)] flex items-center justify-center text-[var(--accent)]">
                <Sparkles className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-[var(--foreground)] flex items-center gap-2">
                  <span>Interactive Turn &amp; Latency Simulator</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                    Live Web Audio
                  </span>
                </h2>
                <p className="text-xs text-[var(--muted-foreground)]">
                  Listen to regional acoustic synthesis and inspect turn latency stages
                </p>
              </div>
            </div>

            {/* Language Selector Pills */}
            <div className="flex items-center gap-1.5 flex-wrap">
              {VOICE_DEMOS.map((demo) => (
                <button
                  key={demo.langCode}
                  onClick={() => {
                    stopAudioDemo();
                    setActiveDemo(demo);
                  }}
                  className={`px-3 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                    activeDemo.langCode === demo.langCode
                      ? "bg-[var(--accent)] text-white font-semibold shadow-sm"
                      : "bg-[var(--card-hover)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--border)]"
                  }`}
                >
                  <span>{demo.native}</span>
                  <span className="ml-1 opacity-75 hidden sm:inline">({demo.lang})</span>
                </button>
              ))}
            </div>
          </div>

          {/* Waveform Canvas */}
          <div className="py-6 flex flex-col items-center">
            <div className="w-full max-w-lg h-24 relative flex items-center justify-center">
              <canvas ref={canvasRef} width={480} height={96} className="w-full h-full" />
            </div>

            {/* Audio Play Button */}
            <button
              onClick={playAudioDemo}
              className={`mt-4 flex items-center gap-2.5 px-6 py-2.5 rounded-full font-mono text-xs font-semibold tracking-wide transition-all cursor-pointer ${
                isPlaying
                  ? "bg-amber-500 text-white hover:bg-amber-600 shadow-lg shadow-amber-500/20"
                  : "bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] shadow-lg shadow-[var(--accent-glow)]"
              }`}
            >
              {isPlaying ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current" />}
              <span>{isPlaying ? `Playing ${activeDemo.lang} Sample...` : `Simulate ${activeDemo.lang} Voice Turn`}</span>
            </button>
          </div>

          {/* Conversation Speech Trace */}
          <div className="space-y-3 pt-4 border-t border-[var(--border)]">
            {/* Caller turn */}
            <div
              className={`p-3.5 rounded-xl border transition-all ${
                playbackPhase === "caller"
                  ? "bg-sky-500/10 border-sky-500/40 shadow-sm"
                  : "bg-[var(--card)] border-[var(--border)]"
              }`}
            >
              <div className="flex items-center justify-between text-[11px] font-mono text-[var(--muted)] mb-1">
                <span className="font-semibold text-sky-400">CALLER INGRESS · SIP RTP STREAM</span>
                <span>+0.00s</span>
              </div>
              <p className="text-sm text-[var(--foreground)] font-medium">“{activeDemo.callerText}”</p>
            </div>

            {/* Agent turn */}
            <div
              className={`p-3.5 rounded-xl border transition-all ${
                playbackPhase === "agent"
                  ? "bg-emerald-500/10 border-emerald-500/40 shadow-sm"
                  : "bg-[var(--card)] border-[var(--border)]"
              }`}
            >
              <div className="flex items-center justify-between text-[11px] font-mono mb-1">
                <span className="font-semibold text-[var(--accent)]">OMNIVOICE AGENT · STREAMING SYNTHESIS</span>
                <span className="px-2 py-0.5 rounded bg-[var(--accent-subtle)] text-[var(--accent)] font-semibold">
                  E2E: {activeDemo.p95}
                </span>
              </div>
              <p className="text-sm text-[var(--foreground)] font-medium mb-3">“{activeDemo.agentText}”</p>

              {/* Latency Pipeline Chips */}
              <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[var(--border)] text-[10px] font-mono">
                <span className="px-2 py-0.5 rounded bg-[var(--card-hover)] text-[var(--muted-foreground)] border border-[var(--border)]">
                  Silero VAD ~18ms
                </span>
                <span className="px-2 py-0.5 rounded bg-[var(--card-hover)] text-[var(--muted-foreground)] border border-[var(--border)]">
                  Sarvam ASR ~110ms
                </span>
                <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-semibold">
                  FAISS Cache Hit &lt;2ms
                </span>
                <span className="px-2 py-0.5 rounded bg-[var(--card-hover)] text-[var(--muted-foreground)] border border-[var(--border)]">
                  Groq TTFT ~175ms
                </span>
                <span className="px-2 py-0.5 rounded bg-[var(--card-hover)] text-[var(--muted-foreground)] border border-[var(--border)]">
                  Regional TTS ~113ms
                </span>
              </div>
            </div>
          </div>

          {/* Bottom Security / SLA Footnote */}
          <div className="mt-4 flex flex-col sm:flex-row items-center justify-between gap-2 text-[11px] font-mono text-[var(--muted)]">
            <span className="flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-[var(--accent)]" />
              Deterministic write confirmation gated · Zero hallucinated writes
            </span>
            <span className="flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              Target SLA: &lt;500ms mouth-to-ear turnaround
            </span>
          </div>
        </div>

        {/* Metric Bar Below Hero */}
        <div className="mt-16 grid grid-cols-2 md:grid-cols-4 gap-6 max-w-4xl mx-auto">
          <div className="p-4 rounded-xl bg-[var(--card)] border border-[var(--border)] text-center">
            <div className="text-2xl sm:text-3xl font-extrabold font-mono text-[var(--foreground)] tracking-tight">
              &lt;500ms
            </div>
            <div className="text-xs text-[var(--muted-foreground)] font-medium mt-1">
              P95 Mouth-to-Ear SLA
            </div>
          </div>
          <div className="p-4 rounded-xl bg-[var(--card)] border border-[var(--border)] text-center">
            <div className="text-2xl sm:text-3xl font-extrabold font-mono text-[var(--accent)] tracking-tight">
              11
            </div>
            <div className="text-xs text-[var(--muted-foreground)] font-medium mt-1">
              Indian Regional Languages
            </div>
          </div>
          <div className="p-4 rounded-xl bg-[var(--card)] border border-[var(--border)] text-center">
            <div className="text-2xl sm:text-3xl font-extrabold font-mono text-[var(--foreground)] tracking-tight">
              ₹1.80/min
            </div>
            <div className="text-xs text-[var(--muted-foreground)] font-medium mt-1">
              Unit Economics (vs ₹14 BPO)
            </div>
          </div>
          <div className="p-4 rounded-xl bg-[var(--card)] border border-[var(--border)] text-center">
            <div className="text-2xl sm:text-3xl font-extrabold font-mono text-emerald-400 tracking-tight">
              &lt;2ms
            </div>
            <div className="text-xs text-[var(--muted-foreground)] font-medium mt-1">
              Approved FAQ Fast-Path
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
