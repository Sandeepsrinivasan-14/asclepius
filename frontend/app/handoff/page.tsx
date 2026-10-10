"use client";
import Link from "next/link";
import { useState } from "react";
import { motion } from "framer-motion";
import { Printer } from "lucide-react";
import { Badge, Card, Gate, PageHeader, useApi } from "@/components/ui";
import { cn, news2Color, riskColor, pct } from "@/lib/utils";

export default function Handoff() {
  const [ward, setWard] = useState("ICU");
  const st = useApi(`/api/handoff/ward/${ward}`, [ward]);
  return (
    <>
      <PageHeader eyebrow="Clinical" title="Shift handoff" sub="An SBAR summary for every patient on the ward, generated only from structured chart data and ordered by acuity. Printable for the bedside round."
        actions={<button className="btn" onClick={() => window.print()}><Printer size={14} />Print</button>} />
      <div className="mb-4 flex gap-1.5">{["ICU", "CCU", "MED", "NEURO"].map((w) => <button key={w} onClick={() => setWard(w)} className={cn("chip cursor-pointer !px-3.5 !py-1.5 text-[12px]", ward === w && "!border-jade-400/50 !bg-jade-400/15 !text-jade-300")}>{w}</button>)}</div>
      <Gate state={st}>{(d) => (
        <>
          <div className="mb-4 flex gap-2"><Badge color="#5cc8ff">{d.count} patients</Badge><Badge color="#ff7a90">{d.high_acuity} high acuity</Badge></div>
          <div className="grid gap-4 xl:grid-cols-2">
            {d.patients.map((h: any, i: number) => (
              <motion.div key={h.patient} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
                <Link href={`/patients/${h.patient}`} className="glass block p-5 transition hover:border-jade-400/30" style={{ borderLeft: `3px solid ${news2Color(h.assessment.news2.score)}` }}>
                  <div className="flex items-start justify-between"><div><div className="text-[15px] font-semibold text-white">{h.name}</div><div className="text-[12px] text-slate-500">{h.bed}</div></div>
                    <div className="flex gap-1.5"><Badge color={riskColor(h.assessment.news2.risk)} dot>NEWS2 {h.assessment.news2.score}</Badge><Badge color={riskColor(h.assessment.ml_risk.tier)}>ML {pct(h.assessment.ml_risk.probability)}</Badge></div></div>
                  <p className="mt-3 text-[13px] leading-relaxed text-slate-300"><b className="text-aur-rose">S</b> {h.situation}</p>
                  <p className="mt-2 text-[12.5px] leading-relaxed text-slate-400"><b className="text-aur-sky">B</b> {h.background.diagnoses.join(", ")}. Allergies: {h.background.allergies.join(", ")}.</p>
                  <ul className="mt-2 space-y-1">{h.recommendation.slice(0, 3).map((r: any, j: number) => <li key={j} className="text-[12.5px] text-slate-300"><b className="text-jade-400">R</b> {r.text}</li>)}</ul>
                </Link>
              </motion.div>
            ))}
          </div>
        </>
      )}</Gate>
    </>
  );
}
