"use client";

import { useState, useEffect } from "react";
import { Sun, Moon, ArrowUpRight, Menu, X, Terminal } from "lucide-react";

const NAV_LINKS = [
  { label: "Product", href: "#platform" },
  { label: "Use Cases", href: "#sandbox" },
  { label: "Architecture", href: "#architecture" },
  { label: "Developers", href: "#developers" },
  { label: "Pricing", href: "#pricing" },
];

export default function Navbar() {
  const [isLight, setIsLight] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 24);
    window.addEventListener("scroll", handleScroll, { passive: true });

    const savedTheme = localStorage.getItem("omni-theme") || "light";
    const light = savedTheme === "light";
    setIsLight(light);
    document.documentElement.setAttribute("data-theme", light ? "light" : "dark");
    document.documentElement.classList.toggle("dark", !light);
    document.documentElement.classList.toggle("light", light);

    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const toggleTheme = () => {
    const next = !isLight;
    setIsLight(next);
    const theme = next ? "light" : "dark";
    localStorage.setItem("omni-theme", theme);
    document.documentElement.setAttribute("data-theme", theme);
    document.documentElement.classList.toggle("dark", !next);
    document.documentElement.classList.toggle("light", next);
  };

  const closeMobile = () => setMobileMenuOpen(false);

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? "bg-[var(--background)]/90 backdrop-blur-sm border-b border-[var(--border)] shadow-sm"
          : "bg-transparent border-b border-transparent"
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-8">

        {/* Brand */}
        <a href="#" aria-label="OmniVoice home" className="flex items-center gap-2.5 shrink-0 group">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent-subtle)] border border-[var(--accent)]/50 flex items-center justify-center text-[var(--accent)] font-mono font-bold text-sm tracking-tighter group-hover:bg-[var(--accent)] group-hover:text-white transition-all duration-200">
            ◖◗
          </div>
          <span className="font-bold text-[15px] tracking-tight text-[var(--foreground)]">
            omni<span className="text-[var(--accent)]">voice</span>
          </span>
        </a>

        {/* Desktop Nav */}
        <nav className="hidden md:flex items-center gap-1" aria-label="Primary navigation">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="px-3.5 py-2 rounded-lg text-sm font-medium text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--card-hover)] transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-1"
            >
              {link.label}
            </a>
          ))}
        </nav>

        {/* Right Rail */}
        <div className="hidden md:flex items-center gap-2 shrink-0">
          <button
            onClick={toggleTheme}
            aria-label={isLight ? "Switch to dark theme" : "Switch to light theme"}
            className="w-8 h-8 rounded-lg border border-[var(--border)] bg-[var(--card)] flex items-center justify-center text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:border-[var(--border-strong)] transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
          >
            {isLight ? <Moon className="w-3.5 h-3.5" /> : <Sun className="w-3.5 h-3.5" />}
          </button>

          <a
            href="http://localhost:8000"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-sm font-medium text-[var(--muted-foreground)] hover:text-[var(--foreground)] px-3 py-1.5 rounded-lg border border-[var(--border)] hover:border-[var(--border-strong)] hover:bg-[var(--card-hover)] transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
          >
            <Terminal className="w-3.5 h-3.5 text-[var(--accent)]" />
            Console
            <ArrowUpRight className="w-3 h-3 opacity-50" />
          </a>

          <a
            href="#platform"
            className="flex items-center gap-1.5 text-sm font-semibold bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white px-4 py-1.5 rounded-lg shadow-sm transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2"
          >
            Start Pilot
          </a>
        </div>

        {/* Mobile Controls */}
        <div className="flex md:hidden items-center gap-2">
          <button
            onClick={toggleTheme}
            aria-label={isLight ? "Switch to dark theme" : "Switch to light theme"}
            className="w-10 h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] flex items-center justify-center text-[var(--muted-foreground)]"
          >
            {isLight ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
          </button>
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
            aria-expanded={mobileMenuOpen}
            className="w-10 h-10 rounded-lg flex items-center justify-center text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--card-hover)] transition-colors"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden bg-[var(--card)] border-b border-[var(--border)] px-4 pt-2 pb-5 flex flex-col gap-1">
          <nav className="flex flex-col" aria-label="Mobile navigation">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={closeMobile}
                className="flex items-center px-3 py-3 rounded-lg text-sm font-medium text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--card-hover)] transition-colors"
              >
                {link.label}
              </a>
            ))}
          </nav>
          <div className="flex flex-col gap-2 pt-3 mt-1 border-t border-[var(--border)]">
            <a
              href="http://localhost:8000"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 text-sm font-medium py-2.5 rounded-lg border border-[var(--border)] text-[var(--foreground)] hover:bg-[var(--card-hover)] transition-colors"
            >
              <Terminal className="w-4 h-4 text-[var(--accent)]" />
              Launch Operations Console ↗
            </a>
            <a
              href="#platform"
              onClick={closeMobile}
              className="flex items-center justify-center gap-2 text-sm font-semibold py-2.5 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white transition-colors"
            >
              Start Pilot
            </a>
          </div>
        </div>
      )}
    </header>
  );
}
