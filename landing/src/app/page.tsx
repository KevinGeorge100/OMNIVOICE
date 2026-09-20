import Navbar from "@/components/Navbar";
import Hero from "@/components/Hero";
import TrustBar from "@/components/TrustBar";
import FeatureGrid from "@/components/FeatureGrid";
import VoiceSandbox from "@/components/VoiceSandbox";
import ArchitectureSection from "@/components/ArchitectureSection";
import CodeShowcase from "@/components/CodeShowcase";
import RoiCalculator from "@/components/RoiCalculator";
import PricingSection from "@/components/PricingSection";
import FaqSection from "@/components/FaqSection";
import Footer from "@/components/Footer";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-[var(--background)] text-[var(--foreground)] selection:bg-[var(--accent)]/20 selection:text-[var(--accent)]">
      <Navbar />
      <main className="flex-1">
        {/* Hero — editorial split, realtime call visualization */}
        <Hero />
        {/* Infrastructure stack strip */}
        <TrustBar />
        {/* 3 capability pillars — pale mint background */}
        <FeatureGrid />
        {/* Full-width voice simulation — 3 panels */}
        <VoiceSandbox />
        {/* Connected pipeline architecture */}
        <ArchitectureSection />
        {/* Dark ink developer section */}
        <CodeShowcase />
        {/* ROI calculator — visual bar comparison */}
        <RoiCalculator />
        {/* Pricing tiers — pale mint background */}
        <PricingSection />
        {/* FAQ accordion */}
        <FaqSection />
      </main>
      {/* Dark CTA strip + footer */}
      <Footer />
    </div>
  );
}
