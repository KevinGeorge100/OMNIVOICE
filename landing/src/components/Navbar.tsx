"use client";

import { useState, useEffect } from "react";
import { Sun, Moon, ArrowUpRight, Menu, X, Terminal, Radio } from "lucide-react";

export default function Navbar() {
  const [isLight, setIsLight] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const toggleTheme = () => {
    const next = !isLight;
    setIsLight(next);
    if (next) {
      document.documentElement.classList.add("light");
      document.documentElement.setAttribute("data-theme", "light");
    } else {
      document.documentElement.classList.remove("light");
      document.documentElement.setAttribute("data-theme", "dark");
    }
  };

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-200 ${
        scrolled
          ? "bg-[var(--background)]/85 backdrop-blur-md border-b border-[var(--border)] shadow-lg shadow-black/5"
          : "bg-transparent border-b border-transparent"
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <a href="#" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent-subtle)] border border-[var(--accent)] flex items-center justify-center text-[var(--accent)] font-mono font-bold text-sm tracking-tighter shadow-sm group-hover:scale-105 transition-transform">
            ◖◗
          </div>
          <div className="flex flex-col">
            <span className="font-bold text-base tracking-tight text-[var(--foreground)]">
              omni<span className="text-[var(--accent)]">voice</span>
            </span>
            <span className="text-[9px] font-mono tracking-widest text-[var(--muted)] uppercase -mt-1">
              Telephony AI
            </span>
          </div>
          <span className="ml-2 px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-[var(--accent-subtle)] text-[var(--accent)] border border-[var(--accent)]/30">
            v1.0
          </span>
        </a>

        {/* Desktop Nav Links */}
        <nav className="hidden md:flex items-center gap-7 text-xs font-medium text-[var(--muted-foreground)]">
          <a href="#platform" className="hover:text-[var(--foreground)] transition-colors">
            Platform
          </a>
          <a href="#voices" className="hover:text-[var(--foreground)] transition-colors flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse" />
            11 Regional Voices
          </a>
          <a href="#architecture" className="hover:text-[var(--foreground)] transition-colors">
            Architecture
          </a>
          <a href="#roi" className="hover:text-[var(--foreground)] transition-colors">
            ROI Calculator
          </a>
          <a href="#developers" className="hover:text-[var(--foreground)] transition-colors">
            Developers
          </a>
          <a href="#pricing" className="hover:text-[var(--foreground)] transition-colors">
            Pricing
          </a>
        </nav>

        {/* Right Actions */}
        <div className="hidden md:flex items-center gap-3">
          <button
            onClick={toggleTheme}
            aria-label="Toggle dark/light theme"
            className="w-8 h-8 rounded-lg border border-[var(--border)] bg-[var(--card)] flex items-center justify-center text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:border-[var(--border-strong)] transition-all cursor-pointer"
          >
            {isLight ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
          </button>

          <a
            href="http://localhost:8000"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs font-medium text-[var(--muted-foreground)] hover:text-[var(--foreground)] px-3 py-1.5 rounded-lg border border-[var(--border)] hover:border-[var(--border-strong)] transition-all"
            title="Launch Operations Console"
          >
            <Terminal className="w-3.5 h-3.5 text-[var(--accent)]" />
            <span>Console</span>
            <ArrowUpRight className="w-3 h-3 text-[var(--muted)]" />
          </a>

          <a
            href="#demo"
            className="flex items-center gap-1.5 text-xs font-semibold bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white px-3.5 py-1.5 rounded-lg shadow-sm hover:shadow-[var(--accent-glow)] transition-all cursor-pointer"
          >
            <Radio className="w-3.5 h-3.5" />
            <span>Deploy Line</span>
          </a>
        </div>

        {/* Mobile Menu Button */}
        <div className="flex md:hidden items-center gap-2">
          <button
            onClick={toggleTheme}
            aria-label="Toggle theme"
            className="w-8 h-8 rounded-lg border border-[var(--border)] bg-[var(--card)] flex items-center justify-center text-[var(--muted-foreground)]"
          >
            {isLight ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
          </button>
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-1.5 rounded-lg text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden bg-[var(--card)] border-b border-[var(--border)] px-4 pt-3 pb-6 flex flex-col gap-4">
          <nav className="flex flex-col gap-3 text-sm font-medium text-[var(--muted-foreground)]">
            <a
              href="#platform"
              onClick={() => setMobileMenuOpen(false)}
              className="hover:text-[var(--foreground)]"
            >
              Platform
            </a>
            <a
              href="#voices"
              onClick={() => setMobileMenuOpen(false)}
              className="hover:text-[var(--foreground)] flex items-center gap-2"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)]" />
              11 Regional Voices
            </a>
            <a
              href="#architecture"
              onClick={() => setMobileMenuOpen(false)}
              className="hover:text-[var(--foreground)]"
            >
              Architecture
            </a>
            <a
              href="#roi"
              onClick={() => setMobileMenuOpen(false)}
              className="hover:text-[var(--foreground)]"
            >
              ROI Calculator
            </a>
            <a
              href="#developers"
              onClick={() => setMobileMenuOpen(false)}
              className="hover:text-[var(--foreground)]"
            >
              Developers
            </a>
            <a
              href="#pricing"
              onClick={() => setMobileMenuOpen(false)}
              className="hover:text-[var(--foreground)]"
            >
              Pricing
            </a>
          </nav>
          <div className="flex flex-col gap-2 pt-3 border-t border-[var(--border)]">
            <a
              href="http://localhost:8000"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 text-sm font-medium py-2 rounded-lg border border-[var(--border)] text-[var(--foreground)]"
            >
              <Terminal className="w-4 h-4 text-[var(--accent)]" />
              Launch Operations Console ↗
            </a>
            <a
              href="#demo"
              onClick={() => setMobileMenuOpen(false)}
              className="flex items-center justify-center gap-2 text-sm font-semibold py-2 rounded-lg bg-[var(--accent)] text-white"
            >
              Deploy Enterprise Line
            </a>
          </div>
        </div>
      )}
    </header>
  );
}
