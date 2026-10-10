"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Contrast, Moon, Palette, Siren, Sun } from "lucide-react";
import { cn } from "@/lib/utils";

export type ThemeName = "night" | "day" | "icu";
export const THEMES: { id: ThemeName; label: string; hint: string; icon: any; swatch: string[] }[] = [
  { id: "night", label: "Aurora night", hint: "Deep navy with jade and gold", icon: Moon, swatch: ["#04070d", "#34d6ae", "#f2c46d"] },
  { id: "day", label: "Clinic day", hint: "Warm ivory, ink and coral", icon: Sun, swatch: ["#f7f3ea", "#1d2433", "#e4573d"] },
  { id: "icu", label: "ICU night", hint: "Low-glare red for night shifts", icon: Siren, swatch: ["#0b0507", "#ff7a6b", "#ffb454"] },
];

type Ctx = { theme: ThemeName; contrast: boolean; setTheme: (t: ThemeName) => void; setContrast: (v: boolean) => void; cycle: () => void };
const ThemeCtx = createContext<Ctx>({ theme: "night", contrast: false, setTheme: () => {}, setContrast: () => {}, cycle: () => {} });
export const useTheme = () => useContext(ThemeCtx);

/** Runs before first paint (see layout.tsx) so the saved theme never flashes. */
export const THEME_BOOT = `try{var d=document.documentElement,t=localStorage.getItem("asc.theme"),c=localStorage.getItem("asc.contrast");if(t==="day"||t==="icu"||t==="night")d.dataset.theme=t;if(c==="1")d.dataset.contrast="high"}catch(e){}`;

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeName>("night");
  const [contrast, setContrastState] = useState(false);

  useEffect(() => {
    const d = document.documentElement;
    setThemeState((d.dataset.theme as ThemeName) || "night");
    setContrastState(d.dataset.contrast === "high");
  }, []);

  const setTheme = useCallback((t: ThemeName) => {
    setThemeState(t);
    document.documentElement.dataset.theme = t;
    try { localStorage.setItem("asc.theme", t); } catch {}
  }, []);
  const setContrast = useCallback((v: boolean) => {
    setContrastState(v);
    if (v) document.documentElement.dataset.contrast = "high"; else delete document.documentElement.dataset.contrast;
    try { localStorage.setItem("asc.contrast", v ? "1" : "0"); } catch {}
  }, []);
  const cycle = useCallback(() => setTheme(THEMES[(THEMES.findIndex((t) => t.id === theme) + 1) % THEMES.length].id), [theme, setTheme]);
  return <ThemeCtx.Provider value={{ theme, contrast, setTheme, setContrast, cycle }}>{children}</ThemeCtx.Provider>;
}

export function ThemeMenu() {
  const { theme, contrast, setTheme, setContrast } = useTheme();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", h); document.addEventListener("keydown", k);
    return () => { document.removeEventListener("mousedown", h); document.removeEventListener("keydown", k); };
  }, [open]);
  const Current = THEMES.find((t) => t.id === theme)!.icon;
  return (
    <div className="relative" ref={ref} data-tour="theme">
      <button className="btn !p-2" onClick={() => setOpen((v) => !v)} aria-haspopup="menu" aria-expanded={open} aria-label="Appearance" title="Appearance (T cycles themes)"><Current size={15} /></button>
      <AnimatePresence>
        {open && (
          <motion.div role="menu" initial={{ opacity: 0, y: -6, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -4 }} className="glass-hi absolute right-0 top-full z-[60] mt-2 w-72 p-2">
            <div className="eyebrow px-2 pb-1.5 pt-1"><Palette size={11} className="mr-1 inline" />Appearance</div>
            {THEMES.map((t) => (
              <button key={t.id} role="menuitemradio" aria-checked={theme === t.id} onClick={() => setTheme(t.id)} className={cn("flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-left transition", theme === t.id ? "bg-jade-400/10" : "hover:bg-white/[0.05]")}>
                <span className="flex -space-x-1.5">{t.swatch.map((c) => <span key={c} className="h-5 w-5 rounded-full border border-white/20" style={{ background: c }} />)}</span>
                <span className="min-w-0 flex-1"><span className="block text-[13px] font-medium text-slate-100">{t.label}</span><span className="block text-[11px] text-slate-400">{t.hint}</span></span>
                {theme === t.id && <span className="h-2 w-2 rounded-full bg-jade-400" />}
              </button>
            ))}
            <button role="menuitemcheckbox" aria-checked={contrast} onClick={() => setContrast(!contrast)} className="mt-1 flex w-full items-center gap-3 rounded-xl border-t hairline px-2.5 py-2.5 text-left hover:bg-white/[0.05]">
              <Contrast size={16} className="text-slate-300" />
              <span className="min-w-0 flex-1"><span className="block text-[13px] font-medium text-slate-100">High contrast</span><span className="block text-[11px] text-slate-400">Stronger borders and text for low-vision use (H)</span></span>
              <span className={cn("relative h-5 w-9 rounded-full transition", contrast ? "bg-jade-500" : "bg-white/15")}><span className={cn("absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all", contrast ? "left-[18px]" : "left-0.5")} /></span>
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
