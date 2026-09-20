import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  title: "OmniVoice — Enterprise Conversational AI Telephony Platform",
  description:
    "Conversational voice AI platform designed for low-latency telephone calls. Built for 11 Indian regional language codes via Sarvam AI, carrier streaming for Exotel and Twilio, in-memory FAISS grounding, and safe write confirmation gating.",
  keywords: [
    "Voice AI",
    "Telephony AI",
    "Conversational AI",
    "Indian Languages Speech",
    "Sarvam AI",
    "Exotel Integration",
    "Twilio Voice",
    "Low Latency Voice AI",
    "Groq Llama 3.1",
    "Customer Support Automation"
  ],
  authors: [{ name: "OmniVoice Technologies" }],
  openGraph: {
    title: "OmniVoice — Voice AI Platform for Enterprise Phone Lines",
    description:
      "Full-duplex speech AI platform supporting 11 Indian regional language codes with sub-500ms pipeline targets. Direct carrier audio streaming for Exotel and Twilio.",
    url: "https://omnivoice.ai",
    siteName: "OmniVoice",
    locale: "en_IN",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "OmniVoice — Conversational AI for Telephone Lines",
    description:
      "Enterprise telephony meets regional voice intelligence. Designed for low-latency conversational response across 11 Indian regional language codes.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="light" className={`${geistSans.variable} ${geistMono.variable} scroll-smooth`} suppressHydrationWarning>
      <body className="min-h-screen bg-[var(--background)] text-[var(--foreground)] antialiased selection:bg-[#059669]/20 selection:text-[#059669]">
        {children}
      </body>
    </html>
  );
}
