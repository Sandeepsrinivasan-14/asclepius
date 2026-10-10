"use client";
import { animate, motion, useMotionValue, useTransform, AnimatePresence } from "framer-motion";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";

/* ---------- data hook ---------- */
export function useApi<T = any>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!!path);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!path) return;
    let live = true;
    setLoading(true);
    api<T>(path).then((d) => { if (live) { setData(d); setError(null); } }).catch((e) => live && setError(e.message)).finally(() => live && setLoading(false));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, tick, ...deps]);
  return { data, error, loading, reload: () => setTick((t) => t + 1), setData };
}

/* ---------- toast ---------- */
type Toast = { id: number; kind: "ok" | "err" | "info"; text: string };
const ToastCtx = createContext<(kind: Toast["kind"], text: string) => void>(() => {});
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((kind: Toast["kind"], text: string) => {
    const id = Date.now() + Math.random();
    setItems((s) => [...s, { id, kind, text }]);
    setTimeout(() => setItems((s) => s.filter((t) => t.id !== id)), 4500);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-5 right-5 z-[80] flex w-80 flex-col gap-2">
        <AnimatePresence>
          {items.map((t) => (
            <motion.div key={t.id} initial={{ opacity: 0, x: 40, scale: 0.95 }} animate={{ opacity: 1, x: 0, scale: 1 }} exit={{ opacity: 0, x: 40 }}
              className="glass pointer-events-auto flex items-start gap-2.5 p-3 text-[13px]">
              {t.kind === "ok" ? <CheckCircle2 size={16} className="mt-0.5 text-jade-400" /> : t.kind === "err" ? <XCircle size={16} className="mt-0.5 text-aur-rose" /> : <Info size={16} className="mt-0.5 text-aur-sky" />}
              <span className="flex-1">{t.text}</span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  );
}

/* ---------- layout ---------- */
export function PageHeader({ eyebrow, title, sub, actions }: { eyebrow?: string; title: ReactNode; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow && <div className="eyebrow mb-1.5 text-jade-300/80">{eyebrow}</div>}
        <h1 className="h-display text-[30px] font-semibold leading-tight text-white md:text-[36px]">{title}</h1>
        {sub && <p className="mt-1.5 max-w-3xl text-[14px] leading-relaxed text-slate-400">{sub}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </motion.div>
  );
}

export function Card({ title, sub, right, children, className, hi, pad = true, delay = 0 }: { title?: ReactNode; sub?: ReactNode; right?: ReactNode; children: ReactNode; className?: string; hi?: boolean; pad?: boolean; delay?: number }) {
  return (
    <motion.section initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay, duration: 0.45, ease: [0.22, 1, 0.36, 1] }} className={cn(hi ? "glass-hi" : "glass", "relative overflow-hidden", className)}>
      {(title || right) && (
        <header className="flex items-start justify-between gap-3 px-5 pb-1 pt-4">
          <div>
            {title && <h3 className="text-[14px] font-semibold tracking-tight text-slate-100">{title}</h3>}
            {sub && <p className="mt-0.5 text-[12px] text-slate-400">{sub}</p>}
          </div>
          {right}
        </header>
      )}
      <div className={cn(pad && "p-5", title && pad && "pt-3")}>{children}</div>
    </motion.section>
  );
}

export function Counter({ value, decimals = 0, suffix = "" }: { value: number; decimals?: number; suffix?: string }) {
  const mv = useMotionValue(0);
  const txt = useTransform(mv, (v) => `${v.toFixed(decimals)}${suffix}`);
  useEffect(() => { const c = animate(mv, value, { duration: 1.1, ease: "easeOut" }); return () => c.stop(); }, [value, mv]);
  return <motion.span>{txt}</motion.span>;
}

export function Stat({ label, value, decimals = 0, suffix, hint, color = "#34d6ae", spark, delay = 0 }: { label: string; value: number | string; decimals?: number; suffix?: string; hint?: ReactNode; color?: string; spark?: number[]; delay?: number }) {
  return (
    <Card delay={delay} className="min-h-[112px]">
      <div className="eyebrow">{label}</div>
      <div className="mt-2 flex items-end justify-between gap-2">
        <div className="h-display text-[34px] font-semibold leading-none text-white">{typeof value === "number" ? <Counter value={value} decimals={decimals} suffix={suffix} /> : value}</div>
        {spark && <Spark data={spark} color={color} w={92} h={36} />}
      </div>
      {hint && <div className="mt-2 text-[12px] text-slate-400">{hint}</div>}
      <div className="absolute inset-x-0 bottom-0 h-px" style={{ background: `linear-gradient(90deg, transparent, ${color}, transparent)` }} />
    </Card>
  );
}

export function Spark({ data, color = "#34d6ae", w = 80, h = 28 }: { data: number[]; color?: string; w?: number; h?: number }) {
  const id = useRef(`g${Math.random().toString(36).slice(2, 8)}`).current;
  return (
    <div style={{ width: w, height: h }}>
      <ResponsiveContainer>
        <AreaChart data={data.map((v, i) => ({ i, v }))} margin={{ top: 2, bottom: 2, left: 0, right: 0 }}>
          <defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={color} stopOpacity={0.5} /><stop offset="100%" stopColor={color} stopOpacity={0} /></linearGradient></defs>
          <Area type="monotone" dataKey="v" stroke={color} strokeWidth={1.6} fill={`url(#${id})`} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Ring({ value, max = 1, size = 96, stroke = 9, color = "#34d6ae", label, sub }: { value: number; max?: number; size?: number; stroke?: number; color?: string; label?: ReactNode; sub?: ReactNode }) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r, f = Math.max(0, Math.min(1, value / max));
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="rgba(255,255,255,.07)" strokeWidth={stroke} fill="none" />
        <motion.circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={stroke} fill="none" strokeLinecap="round" strokeDasharray={c}
          initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - f) }} transition={{ duration: 1.2, ease: "easeOut" }} style={{ filter: `drop-shadow(0 0 6px ${color}88)` }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <div className="h-display text-[20px] font-semibold leading-none text-white">{label}</div>
        {sub && <div className="mt-0.5 text-[10px] text-slate-400">{sub}</div>}
      </div>
    </div>
  );
}

export function Badge({ children, color = "#8ea3c0", dot, className }: { children: ReactNode; color?: string; dot?: boolean; className?: string }) {
  return (
    <span className={cn("chip", className)} style={{ color, borderColor: `${color}44`, background: `${color}14` }}>
      {dot && <span className="h-1.5 w-1.5 rounded-full" style={{ background: color, boxShadow: `0 0 8px ${color}` }} />}
      {children}
    </span>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange, layout = "tabs" }: { tabs: { id: T; label: string; icon?: ReactNode }[]; value: T; onChange: (t: T) => void; layout?: string }) {
  return (
    <div className="glass mb-5 flex w-full flex-wrap gap-1 p-1">
      {tabs.map((t) => (
        <button key={t.id} onClick={() => onChange(t.id)} className={cn("relative flex shrink-0 items-center gap-1.5 rounded-xl px-3 py-2 text-[13px] font-medium transition", value === t.id ? "text-white" : "text-slate-400 hover:text-slate-200")}>
          {value === t.id && <motion.span layoutId={`tab-${layout}`} className="absolute inset-0 rounded-xl border border-jade-400/30 bg-jade-400/10" transition={{ type: "spring", stiffness: 420, damping: 34 }} />}
          <span className="relative flex items-center gap-1.5">{t.icon}{t.label}</span>
        </button>
      ))}
    </div>
  );
}

export function Skeleton({ h = 120, className }: { h?: number; className?: string }) {
  return <div className={cn("shimmer rounded-2xl", className)} style={{ height: h }} />;
}
export function Loading({ rows = 3 }: { rows?: number }) {
  return <div className="space-y-3">{Array.from({ length: rows }).map((_, i) => <Skeleton key={i} h={96} />)}</div>;
}
export function ErrorBox({ message }: { message: string }) {
  return <div className="glass flex items-center gap-3 border-aur-rose/30 p-4 text-[13px] text-aur-rose"><AlertTriangle size={16} />{message}</div>;
}
export function Limited({ message }: { message: string }) {
  return <div className="glass flex items-center gap-3 p-5 text-[13px] text-slate-400"><Info size={16} className="shrink-0 text-aur-sky" />{message}</div>;
}
export function Gate({ state, children }: { state: { data: any; error: string | null; loading: boolean }; children: (d: any) => ReactNode }) {
  if (state.error) return <ErrorBox message={state.error} />;
  if (!state.data) return <Loading />;
  return <>{children(state.data)}</>;
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; wide?: boolean }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
          <motion.div onClick={(e) => e.stopPropagation()} initial={{ scale: 0.94, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.96, opacity: 0 }} className={cn("glass-hi max-h-[88vh] w-full overflow-auto p-6", wide ? "max-w-3xl" : "max-w-lg")}>
            <div className="mb-4 flex items-center justify-between">
              <h3 className="h-display text-xl font-semibold text-white">{title}</h3>
              <button className="btn !p-1.5" onClick={onClose}><X size={14} /></button>
            </div>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead><tr className="border-b hairline">{head.map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-white/[0.05]">{children}</tbody>
      </table>
    </div>
  );
}

export const Disclaimer = ({ children }: { children: ReactNode }) => (
  <div className="flex items-start gap-2 rounded-xl border border-aur-gold/20 bg-aur-gold/[0.06] px-3 py-2 text-[12px] leading-relaxed text-aur-gold/90"><Info size={14} className="mt-0.5 shrink-0" />{children}</div>
);

export function Pulse({ color = "#34d6ae" }: { color?: string }) {
  return <span className="relative inline-flex h-2.5 w-2.5"><span className="absolute inline-flex h-full w-full animate-pulseRing rounded-full" style={{ background: color }} /><span className="relative inline-flex h-2.5 w-2.5 rounded-full" style={{ background: color }} /></span>;
}
