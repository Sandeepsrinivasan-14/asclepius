"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { BedDouble, BookMarked, Command, HeartPulse, HelpCircle, Keyboard, LayoutDashboard, LogOut, Mic, Palette as PaletteIcon, ScanLine, Scale, Search, ShieldCheck, Stethoscope, Users, Workflow, Sparkles, Landmark, Database, ClipboardList, Contrast, Calculator } from "lucide-react";
import { useAuth } from "./auth";
import { AlertsBell, useAlerts } from "./alerts";
import { Shortcuts } from "./shortcuts";
import { ThemeMenu, useTheme } from "./theme";
import { TOUR_KEY, Tour } from "./tour";
import { api } from "@/lib/api";
import { cn, initials } from "@/lib/utils";
import { Badge, Pulse } from "./ui";

export const NAV: { section: string; items: { href: string; label: string; icon: any; hint: string }[] }[] = [
  { section: "Clinical", items: [
    { href: "/dashboard", label: "Command center", icon: LayoutDashboard, hint: "Overview of the hospital and AI safety" },
    { href: "/patients", label: "Patients", icon: Users, hint: "Search and open patient charts" },
    { href: "/monitor", label: "Live monitor", icon: HeartPulse, hint: "Real-time vitals with early-warning scores" },
    { href: "/handoff", label: "Shift handoff", icon: ClipboardList, hint: "SBAR handoff for every patient on a ward" },
    { href: "/scribe", label: "Ambient scribe", icon: Mic, hint: "Visit transcript to SOAP note and FHIR draft" },
    { href: "/calculators", label: "Calculators", icon: Calculator, hint: "CHA2DS2-VASc, CURB-65, Cockcroft-Gault, BMI and corrected calcium" },
    { href: "/imaging", label: "Imaging", icon: ScanLine, hint: "Synthetic MRI/X-ray viewer with AI overlay" },
  ]},
  { section: "Interoperability", items: [
    { href: "/interop", label: "HL7 v2 pipeline", icon: Workflow, hint: "ADT/ORU ingestion, retry and dead-letter queue" },
    { href: "/abdm", label: "ABDM consent", icon: Landmark, hint: "ABHA validation and consent manager (mock)" },
    { href: "/fhir", label: "FHIR explorer", icon: Database, hint: "Browse the FHIR R4 API and SMART launch" },
    { href: "/terminology", label: "Terminology", icon: BookMarked, hint: "ICD-10, SNOMED CT, LOINC, RxNorm lookup and Synthea import" },
  ]},
  { section: "Trust and operations", items: [
    { href: "/governance", label: "AI governance", icon: Scale, hint: "Model cards, drift, fairness, overrides" },
    { href: "/access", label: "Access and audit", icon: ShieldCheck, hint: "Break-glass, reviews and tamper-evident audit log" },
    { href: "/ops", label: "Operations twin", icon: BedDouble, hint: "Bed forecast, OPD queues, length of stay, flow" },
  ]},
];
const FLAT = NAV.flatMap((s) => s.items);

function Brand({ small }: { small?: boolean }) {
  return (
    <Link href="/dashboard" className="flex items-center gap-2.5">
      <div className="relative grid h-9 w-9 place-items-center rounded-xl border border-jade-400/40 bg-gradient-to-br from-jade-500/30 to-aur-gold/20 shadow-glow">
        <svg viewBox="0 0 32 32" className="h-5 w-5" fill="none" stroke="#6ee7c8" strokeWidth="1.8" strokeLinecap="round">
          <path d="M16 3v26" /><path d="M16 9c6-2 7 3 1 4s-6 3 0 4 5 5-1 6" stroke="#f2c46d" /><path d="M11 6c2-3 8-3 10 0" />
        </svg>
      </div>
      {!small && <div><div className="h-display text-[19px] font-semibold leading-none tracking-wide text-white">Asclepius</div><div className="mt-0.5 text-[9.5px] uppercase tracking-[0.22em] text-slate-500">Clinical intelligence</div></div>}
    </Link>
  );
}

type PaletteAction = { label: string; sub: string; run: () => void; icon: any };

function Palette({ open, onClose, actions }: { open: boolean; onClose: () => void; actions: PaletteAction[] }) {
  const [q, setQ] = useState("");
  const [patients, setPatients] = useState<any[]>([]);
  const [idx, setIdx] = useState(0);
  const router = useRouter();
  const inp = useRef<HTMLInputElement>(null);
  useEffect(() => { if (open) { setQ(""); setIdx(0); setTimeout(() => inp.current?.focus(), 30); api("/api/patients").then((d) => setPatients(d.patients)).catch(() => {}); } }, [open]);
  const results = useMemo(() => {
    const s = q.toLowerCase();
    const pages = FLAT.filter((i) => !s || i.label.toLowerCase().includes(s) || i.hint.toLowerCase().includes(s)).map((i) => ({ kind: "Page", label: i.label, sub: i.hint, href: i.href, icon: i.icon, run: undefined as undefined | (() => void) }));
    const pts = patients.filter((p) => s && (p.name.toLowerCase().includes(s) || (p.mrn ?? "").toLowerCase().includes(s) || (p.conditions || []).join(" ").toLowerCase().includes(s))).slice(0, 6)
      .map((p) => ({ kind: "Patient", label: p.name, sub: `${p.mrn} · ${p.age}${p.sex[0].toUpperCase()} · ${(p.conditions || [])[0] ?? ""}`, href: `/patients/${p.id}`, icon: Stethoscope, run: undefined as undefined | (() => void) }));
    const acts = actions.filter((a) => !s || a.label.toLowerCase().includes(s) || a.sub.toLowerCase().includes(s)).map((a) => ({ kind: "Action", label: a.label, sub: a.sub, href: `action:${a.label}`, icon: a.icon, run: a.run }));
    return [...pts, ...pages, ...acts].slice(0, 10);
  }, [q, patients, actions]);
  const go = (r: { href: string; run?: () => void }) => { onClose(); if (r.run) r.run(); else router.push(r.href); };
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[90] flex items-start justify-center bg-black/60 px-4 pt-[14vh] backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
          <motion.div onClick={(e) => e.stopPropagation()} initial={{ y: -16, scale: 0.97 }} animate={{ y: 0, scale: 1 }} exit={{ y: -10, opacity: 0 }} className="glass-hi w-full max-w-xl overflow-hidden">
            <div className="flex items-center gap-3 border-b hairline px-4 py-3">
              <Search size={16} className="text-slate-400" />
              <input ref={inp} value={q} onChange={(e) => { setQ(e.target.value); setIdx(0); }} placeholder="Jump to a patient, condition or module…" className="flex-1 bg-transparent text-[14px] outline-none placeholder:text-slate-500"
                onKeyDown={(e) => { if (e.key === "ArrowDown") { e.preventDefault(); setIdx((i) => Math.min(i + 1, results.length - 1)); } if (e.key === "ArrowUp") { e.preventDefault(); setIdx((i) => Math.max(i - 1, 0)); } if (e.key === "Enter" && results[idx]) go(results[idx]); if (e.key === "Escape") onClose(); }} />
              <span className="kbd">esc</span>
            </div>
            <div className="max-h-[50vh] overflow-auto p-2">
              {results.map((r, i) => (
                <button key={r.href + r.label} onMouseEnter={() => setIdx(i)} onClick={() => go(r)} className={cn("flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left", i === idx ? "bg-jade-400/10" : "")}>
                  <r.icon size={16} className={i === idx ? "text-jade-300" : "text-slate-500"} />
                  <div className="min-w-0 flex-1"><div className="truncate text-[13px] text-slate-100">{r.label}</div><div className="truncate text-[11.5px] text-slate-500">{r.sub}</div></div>
                  <span className="eyebrow">{r.kind}</span>
                </button>
              ))}
              {!results.length && <div className="p-6 text-center text-[13px] text-slate-500">No matches</div>}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const { user, logout, ready } = useAuth();
  const path = usePathname();
  const router = useRouter();
  const { cycle, contrast, setContrast } = useTheme();
  const [pal, setPal] = useState(false);
  const [help, setHelp] = useState(false);
  const [tour, setTour] = useState(false);
  const { alerts, reload } = useAlerts(!!user && path !== "/login");
  const chord = useRef<{ key: string; at: number } | null>(null);

  useEffect(() => {
    const GO: Record<string, string> = { d: "/dashboard", p: "/patients", m: "/monitor", i: "/interop", t: "/terminology", c: "/calculators" };
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPal((v) => !v); return; }
      const el = e.target as HTMLElement | null;
      if (e.metaKey || e.ctrlKey || e.altKey || (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable))) return;
      const k = e.key.toLowerCase();
      if (e.key === "?") { e.preventDefault(); setHelp((v) => !v); return; }
      if (e.key === "Escape") { setHelp(false); return; }
      if (chord.current && Date.now() - chord.current.at < 1200 && chord.current.key === "g" && GO[k]) { chord.current = null; router.push(GO[k]); return; }
      chord.current = k === "g" ? { key: "g", at: Date.now() } : null;
      if (k === "t") cycle();
      if (k === "h") setContrast(!contrast);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [router, cycle, contrast, setContrast]);

  useEffect(() => {
    if (!user || path === "/login") return;
    try { if (!localStorage.getItem(TOUR_KEY)) { const t = setTimeout(() => setTour(true), 900); return () => clearTimeout(t); } } catch {}
  }, [user, path]);

  const actions = useMemo<PaletteAction[]>(() => [
    { label: "Take the product tour", sub: "A 40-second walkthrough of the interface", icon: HelpCircle, run: () => setTour(true) },
    { label: "Keyboard shortcuts", sub: "Show every shortcut (also: ?)", icon: Keyboard, run: () => setHelp(true) },
    { label: "Cycle theme", sub: "Aurora night, Clinic day, ICU night (also: T)", icon: PaletteIcon, run: cycle },
    { label: "Toggle high contrast", sub: "Stronger borders and text (also: H)", icon: Contrast, run: () => setContrast(!contrast) },
  ], [cycle, contrast, setContrast]);

  if (path === "/login") return <>{children}</>;
  if (!ready || !user) return <div className="grid min-h-screen place-items-center"><Pulse /></div>;

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-[248px] shrink-0 flex-col border-r hairline bg-ink-900/50 px-4 py-5 backdrop-blur-xl lg:flex">
        <Brand />
        <nav data-tour="nav" aria-label="Modules" className="mt-7 flex-1 space-y-5 overflow-y-auto pr-1">
          {NAV.map((s) => (
            <div key={s.section}>
              <div className="eyebrow mb-1.5 px-2.5 text-slate-500">{s.section}</div>
              {s.items.map((it) => {
                const active = path === it.href || (it.href !== "/dashboard" && path.startsWith(it.href));
                return (
                  <Link key={it.href} href={it.href} className={cn("group relative mb-0.5 flex items-center gap-2.5 rounded-xl px-2.5 py-2 text-[13px] transition", active ? "text-white" : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-100")}>
                    {active && <motion.span layoutId="nav-active" className="absolute inset-0 rounded-xl border border-jade-400/25 bg-gradient-to-r from-jade-400/15 to-transparent" transition={{ type: "spring", stiffness: 400, damping: 32 }} />}
                    <it.icon size={16} className={cn("relative", active ? "text-jade-300" : "text-slate-500 group-hover:text-slate-300")} />
                    <span className="relative">{it.label}</span>
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="glass mt-4 p-3" data-tour="user">
          <div className="flex items-center gap-2.5">
            <div className="grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br from-jade-500 to-aur-sky text-[12px] font-bold text-ink-950">{initials(user.name)}</div>
            <div className="min-w-0 flex-1"><div className="truncate text-[13px] font-medium text-white">{user.name}</div><div className="truncate text-[11px] text-slate-400">{user.title}</div></div>
            <button onClick={logout} className="btn !p-1.5" title="Sign out"><LogOut size={14} /></button>
          </div>
        </div>
      </aside>
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b hairline bg-ink-950/60 px-5 py-3 backdrop-blur-xl lg:px-8">
          <div className="lg:hidden"><Brand small /></div>
          <button data-tour="search" onClick={() => setPal(true)} className="btn flex-1 !justify-start !rounded-xl text-slate-400 md:max-w-md"><Search size={14} /><span className="flex-1 text-left">Search patients, conditions, modules</span><span className="kbd flex items-center gap-1"><Command size={10} />K</span></button>
          <div className="ml-auto flex items-center gap-2">
            <div className="hidden items-center gap-2 xl:flex">
              <Badge color="#f2c46d" dot>Synthetic data only</Badge>
              <Badge color="#8b7bff">Not a medical device</Badge>
              <Badge color="#34d6ae" dot>API live</Badge>
            </div>
            <button className="btn !p-2" onClick={() => setTour(true)} aria-label="Take the tour" title="Take the tour"><HelpCircle size={15} /></button>
            <button className="btn !p-2" onClick={() => setHelp(true)} aria-label="Keyboard shortcuts" title="Keyboard shortcuts (?)"><Keyboard size={15} /></button>
            <AlertsBell alerts={alerts} reload={reload} />
            <ThemeMenu />
          </div>
        </header>
        <main id="main" className="mx-auto max-w-[1500px] px-5 py-7 lg:px-8">
          <AnimatePresence mode="wait"><motion.div key={path} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }}>{children}</motion.div></AnimatePresence>
        </main>
      </div>
      <Palette open={pal} onClose={() => setPal(false)} actions={actions} />
      <Shortcuts open={help} onClose={() => setHelp(false)} />
      <Tour open={tour} onClose={() => setTour(false)} />
    </div>
  );
}
