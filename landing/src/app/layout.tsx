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
    "Sub-500ms full-duplex conversational voice AI for real phone lines. Native support for 11 Indian regional languages, direct Exotel/Twilio SIP integration, in-memory FAISS grounding, and safe write confirmation gating.",
  keywords: [
    "Voice AI",
    "Telephony AI",
    "Conversational AI",
    "Indian Languages Speech",
    "Sarvam AI",
    "Exotel Integration",
    "Twilio Voice",
    "Sub-500ms Voice",
    "Groq Llama 3",
    "Customer Support Automation"
  ],
  authors: [{ name: "OmniVoice Technologies" }],
  openGraph: {
    title: "OmniVoice — Voice AI Platform for Enterprise Phone Lines",
    description:
      "Full-duplex speech AI in 11 Indian languages with sub-500ms latency. Direct carrier SIP integration for modern call centers.",
    url: "https://omnivoice.ai",
    siteName: "OmniVoice",
    locale: "en_IN",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "OmniVoice — Conversational AI for Telephone Lines",
    description:
      "Enterprise telephony meets regional voice intelligence. Under 500ms mouth-to-ear turnaround across 11 Indian languages.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} scroll-smooth`}>
      <body className="min-h-screen bg-[var(--background)] text-[var(--foreground)] antialiased selection:bg-[#10b981]/20 selection:text-[#10b981]">
        {children}
      </body>
    </html>
  );
}
