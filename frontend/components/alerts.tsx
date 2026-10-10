"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Bell, HeartPulse, ShieldAlert, Skull, X } from "lucide-react";
import { api } from "@/lib/api";
import { news2Color } from "@/lib/utils";

type Alert = { id: string; kind: "risk" | "dlq" | "review"; title: string; sub: string; href: string; color: string };

/** Role-aware alerts. Each source is optional: a 403 simply means the role does not see that kind of alert. */
export function useAlerts(enabled: boolean) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const load = useCallback(async () => {
    const out: Alert[] = [];
    await Promise.all([
      api("/api/warning/overview").then((w) => {
        for (const p of w.patients.filter((x: any) => x.news2 >= 7).slice(0, 5)) out.push({ id: `r-${p.id}`, kind: "risk", title: `${p.name}: NEWS2 ${p.news2}`, sub: `${p.ward} · ${p.bed} · emergency response threshold`, href: `/patients/${p.id}`, color: news2Color(p.news2) });
      }).catch(() => {}),
      api("/api/interop/queue").then((q) => {
        if (q.dead_letter?.length) out.push({ id: "dlq", kind: "dlq", title: `${q.dead_letter.length} HL7 message(s) dead-lettered`, sub: "Fix the cause, then replay from the pipeline", href: "/interop", color: "#ffb454" });
      }).catch(() => {}),
      api("/api/access/reviews").then((r) => {
        const open = r.reviews.filter((x: any) => x.status === "open");
        if (open.length) out.push({ id: "rev", kind: "review", title: `${open.length} break-glass review(s) pending`, sub: "Privacy officer sign-off required", href: "/access", color: "#ff7a90" });
      }).catch(() => {}),
    ]);
    setAlerts(out);
  }, []);
  useEffect(() => {
    if (!enabled) return;
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [enabled, load]);
  return { alerts, reload: load };
}

const ICON = { risk: HeartPulse, dlq: Skull, review: ShieldAlert } as const;

export function AlertsBell({ alerts, reload }: { alerts: Alert[]; reload: () => void }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open]);
  return (
    <>
      <button data-tour="alerts" className="btn relative !p-2" onClick={() => { reload(); setOpen(true); }} aria-label={`Alerts (${alerts.length})`} title="Alerts">
        <Bell size={15} />
        {alerts.length > 0 && <span className="absolute -right-1 -top-1 grid h-4 min-w-[1rem] place-items-center rounded-full bg-aur-rose px-1 text-[9.5px] font-bold text-white" data-testid="alert-count">{alerts.length}</span>}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div className="fixed inset-0 z-[85] bg-black/40 backdrop-blur-[2px]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setOpen(false)}>
            <motion.aside role="dialog" aria-label="Alerts" data-testid="alerts-drawer" onClick={(e) => e.stopPropagation()} initial={{ x: 380 }} animate={{ x: 0 }} exit={{ x: 380 }} transition={{ type: "spring", stiffness: 320, damping: 34 }} className="glass-hi absolute right-0 top-0 flex h-full w-full max-w-sm flex-col !rounded-none !rounded-l-2xl p-5">
              <div className="mb-4 flex items-center justify-between"><h2 className="h-display text-xl font-semibold text-white">Alerts</h2><button className="btn !p-1.5" onClick={() => setOpen(false)} aria-label="Close alerts"><X size={14} /></button></div>
              <div className="flex-1 space-y-2.5 overflow-auto">
                {alerts.map((a) => {
                  const Icon = ICON[a.kind];
                  return (
                    <Link key={a.id} href={a.href} onClick={() => setOpen(false)} className="flex items-start gap-3 rounded-xl border hairline bg-white/[0.03] p-3 transition hover:bg-white/[0.07]">
                      <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg" style={{ background: `${a.color}22`, color: a.color }}><Icon size={15} /></span>
                      <span className="min-w-0"><span className="block text-[13px] font-medium text-slate-100">{a.title}</span><span className="block text-[11.5px] text-slate-400">{a.sub}</span></span>
                    </Link>
                  );
                })}
                {!alerts.length && <div className="rounded-xl border hairline p-6 text-center text-[13px] text-slate-400">Nothing needs attention right now.</div>}
              </div>
              <p className="mt-3 text-[11px] text-slate-500">Alerts refresh every 30 seconds and only include what your role may see.</p>
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
