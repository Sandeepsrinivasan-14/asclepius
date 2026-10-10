"use client";
import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, ArrowRight, Sparkles, X } from "lucide-react";

type Step = { target?: string; title: string; body: string };
export const TOUR_STEPS: Step[] = [
  { title: "Welcome to Asclepius", body: "A synthetic-data clinical platform where every AI output is cited, verified, audited and measured. This 40-second tour shows where things live. Nothing here is real patient data." },
  { target: "nav", title: "Every module, one sidebar", body: "Clinical work, interoperability (HL7, FHIR, ABDM, terminology) and trust and operations (governance, audit, operations twin). What you see depends on your role." },
  { target: "search", title: "Jump anywhere", body: "Press Ctrl/Cmd + K to search patients, conditions and modules. Press ? at any time for every keyboard shortcut." },
  { target: "alerts", title: "Alerts that matter", body: "High-risk deterioration scores, dead-lettered HL7 messages and pending break-glass reviews gather here, filtered by your role." },
  { target: "theme", title: "Make it yours", body: "Switch between Aurora night, Clinic day and a low-glare ICU night theme, and turn on high contrast for low-vision use." },
  { target: "user", title: "Who you are decides what you see", body: "Sign out and try another persona: a nurse sees ward patients, a privacy officer sees the audit trail, a pharmacist sees medication safety." },
  { title: "Try this next", body: "Open Patients, pick Joseph Thomas, then use the Body map and Differential copilot tabs. Click a [E#] citation, then try Break the verifier. You can restart this tour from the header at any time." },
];

export const TOUR_KEY = "asc.tour.v1";
const visible = (el: Element | null) => !!el && (el as HTMLElement).getBoundingClientRect().width > 0;

export function Tour({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const steps = TOUR_STEPS;
  const step = steps[i];

  const measure = useCallback(() => {
    if (!step?.target) { setRect(null); return; }
    const el = document.querySelector(`[data-tour="${step.target}"]`);
    if (visible(el)) { (el as HTMLElement).scrollIntoView({ block: "nearest" }); setRect((el as HTMLElement).getBoundingClientRect()); } else setRect(null);
  }, [step]);

  useEffect(() => { if (open) setI(0); }, [open]);
  useLayoutEffect(() => { if (open) measure(); }, [open, measure]);
  useEffect(() => {
    if (!open) return;
    window.addEventListener("resize", measure); window.addEventListener("scroll", measure, true);
    return () => { window.removeEventListener("resize", measure); window.removeEventListener("scroll", measure, true); };
  }, [open, measure]);

  const finish = useCallback(() => { try { localStorage.setItem(TOUR_KEY, "done"); } catch {} onClose(); }, [onClose]);
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => {
      if (e.key === "Escape") finish();
      if (e.key === "ArrowRight") setI((v) => Math.min(v + 1, steps.length - 1));
      if (e.key === "ArrowLeft") setI((v) => Math.max(v - 1, 0));
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, finish, steps.length]);

  const W = 360;
  const vw = typeof window === "undefined" ? 1200 : window.innerWidth;
  const vh = typeof window === "undefined" ? 800 : window.innerHeight;
  let left = Math.max(16, (vw - W) / 2), top = Math.max(16, vh / 2 - 130);
  if (rect) {
    left = rect.right + 20 + W < vw ? rect.right + 20 : Math.max(16, Math.min(vw - W - 16, rect.left));
    top = rect.right + 20 + W < vw ? Math.max(16, Math.min(vh - 280, rect.top)) : Math.min(vh - 280, rect.bottom + 16);
  }
  return (
    <AnimatePresence>
      {open && (
        <motion.div key="tour" className="fixed inset-0 z-[94]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} role="dialog" aria-modal="true" aria-label="Product tour" data-testid="tour">
          {rect ? <div className="tour-hole" style={{ left: rect.left - 6, top: rect.top - 6, width: rect.width + 12, height: rect.height + 12 }} /> : <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />}
          <motion.div key={i} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass-hi fixed z-[96] p-5" style={{ left, top, width: Math.min(W, vw - 32) }}>
            <div className="mb-2 flex items-center justify-between">
              <span className="eyebrow flex items-center gap-1.5 text-jade-300"><Sparkles size={12} />Step {i + 1} of {steps.length}</span>
              <button className="btn !p-1" onClick={finish} aria-label="Close tour"><X size={13} /></button>
            </div>
            <h3 className="h-display text-[20px] font-semibold text-white">{step.title}</h3>
            <p className="mt-1.5 text-[13px] leading-relaxed text-slate-300">{step.body}</p>
            <div className="mt-4 flex items-center justify-between">
              <div className="flex gap-1.5">{steps.map((_, n) => <button key={n} onClick={() => setI(n)} aria-label={`Go to step ${n + 1}`} className={`h-1.5 rounded-full transition-all ${n === i ? "w-6 bg-jade-400" : "w-1.5 bg-white/25"}`} />)}</div>
              <div className="flex gap-2">
                {i > 0 && <button className="btn !py-1.5" onClick={() => setI(i - 1)}><ArrowLeft size={13} />Back</button>}
                {i < steps.length - 1 ? <button className="btn btn-primary !py-1.5" onClick={() => setI(i + 1)}>Next<ArrowRight size={13} /></button> : <button className="btn btn-primary !py-1.5" onClick={finish}>Finish</button>}
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
