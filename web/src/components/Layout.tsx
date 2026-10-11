import { AnimatePresence, motion } from "framer-motion";
import { Menu, Moon, Radar, Sun, X } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useTheme } from "../lib/hooks";
import { cx, Disclaimer } from "./ui";

const NAV = [
  { to: "/analyze", label: "Analyze" },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/about", label: "About & limits" },
];

function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2.5 rounded-lg" aria-label="TrialRadar home">
      <span className="grid h-9 w-9 place-items-center rounded-xl bg-accent text-accent-ink"><Radar size={20} aria-hidden /></span>
      <span className="display text-xl font-semibold tracking-tight">TrialRadar</span>
    </Link>
  );
}

export default function Layout() {
  const { dark, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const link = ({ isActive }: { isActive: boolean }) =>
    cx("rounded-lg px-3 py-2 text-[15px] font-medium min-h-[44px] inline-flex items-center", isActive ? "bg-accent-soft text-ink" : "text-muted hover:text-ink");
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2 focus:text-accent-ink">Skip to content</a>
      <header className="sticky top-0 z-40 border-b border-line bg-bg/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
          <Logo />
          <nav aria-label="Main" className="hidden items-center gap-1 sm:flex">
            {NAV.map((n) => <NavLink key={n.to} to={n.to} className={link}>{n.label}</NavLink>)}
          </nav>
          <div className="flex items-center gap-1">
            <button onClick={toggle} aria-label={dark ? "Switch to light theme" : "Switch to dark theme"} aria-pressed={dark}
              className="grid h-11 w-11 place-items-center rounded-xl text-muted hover:bg-surface2 hover:text-ink">
              {dark ? <Sun size={19} aria-hidden /> : <Moon size={19} aria-hidden />}
            </button>
            <button className="grid h-11 w-11 place-items-center rounded-xl text-muted hover:bg-surface2 sm:hidden" aria-expanded={open} aria-controls="mobile-nav"
              aria-label={open ? "Close menu" : "Open menu"} onClick={() => setOpen(!open)}>
              {open ? <X size={20} aria-hidden /> : <Menu size={20} aria-hidden />}
            </button>
          </div>
        </div>
        {open && (
          <nav id="mobile-nav" aria-label="Main" className="border-t border-line px-4 pb-3 sm:hidden">
            {NAV.map((n) => <NavLink key={n.to} to={n.to} onClick={() => setOpen(false)} className={(s) => cx(link(s), "w-full")}>{n.label}</NavLink>)}
          </nav>
        )}
      </header>
      <main id="main" tabIndex={-1} className="flex-1 outline-none">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={loc.pathname} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.22 }}>
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>
      <footer className="mt-16 border-t border-line">
        <div className="mx-auto max-w-6xl space-y-4 px-4 py-8 sm:px-6">
          <Disclaimer compact />
          <p className="text-[13px] leading-relaxed text-muted">
            Data: <a className="underline" href="https://clinicaltrials.gov" target="_blank" rel="noreferrer">ClinicalTrials.gov</a>, U.S. National Library of Medicine.
            Open source (MIT). No LLMs and no API keys. Built for the Regeneron challenge at HackRU 2026.
          </p>
        </div>
      </footer>
    </div>
  );
}
