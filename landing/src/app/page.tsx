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
    <div className="flex min-h-screen flex-col bg-[var(--background)] text-[var(--foreground)] selection:bg-[#10b981]/25 selection:text-[#10b981]">
      <Navbar />
      <main className="flex-1">
        <Hero />
        <TrustBar />
        <FeatureGrid />
        <VoiceSandbox />
        <ArchitectureSection />
        <CodeShowcase />
        <RoiCalculator />
        <PricingSection />
        <FaqSection />
      </main>
      <Footer />
    </div>
  );
}
