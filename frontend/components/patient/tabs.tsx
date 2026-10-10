"use client";
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { AlertOctagon, Check, CheckCheck, ClipboardCopy, FlaskConical, Pencil, ShieldCheck, ShieldX, X } from "lucide-react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { Badge, Card, Disclaimer, Gate, Loading, Ring, Table, useApi, useToast } from "@/components/ui";
import { cn, fmtTime, news2Color, pct, riskColor } from "@/lib/utils";
import { LabChart, News2Chart, VitalChart } from "./charts";
import type { OrganFilter } from "./bodymap";

const sevColor: Record<string, string> = { contraindicated: "#ff7a90", major: "#ffb454", moderate: "#f2c46d", info: "#5cc8ff", high: "#ff7a90", medium: "#ffb454", low: "#34d6ae" };

/* ============ Overview ============ */
export function Overview({ p, filter }: { p: any; filter?: OrganFilter | null }) {
  const v = p.vitals;
  const conditions = filter ? p.conditions_detail.filter((c: any) => filter.conditionIds.has(c.id)) : p.conditions_detail;
  const medications = filter ? p.medications.filter((m: any) => filter.medIds.has(m.id)) : p.medications;
  const items = v ? [["Heart rate", v.hr, "/min", "#ff7a90"], ["Resp. rate", v.rr, "/min", "#5cc8ff"], ["SpO₂", v.spo2, "%", "#34d6ae"], ["Temp", v.temp, "°C", "#ffb454"], ["BP", `${v.sbp}/${v.dbp}`, "mmHg", "#8b7bff"], ["Consciousness", v.acvpu, "", "#f2c46d"]] : [];
  return (
    <div className="grid gap-5 xl:grid-cols-3">
      <Card title="Latest vitals" sub={v ? fmtTime(v.time) : ""} className="xl:col-span-2" delay={0}>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
          {items.map(([l, val, u, c]: any, i) => (
            <motion.div key={l} initial={{ opacity: 0, scale: 0.94 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.05 }} className="rounded-2xl border hairline bg-white/[0.03] p-3.5">
              <div className="eyebrow">{l}</div><div className="h-display mt-1 text-[28px] font-semibold" style={{ color: c }}>{val}<span className="ml-1 text-[12px] font-normal text-slate-500">{u}</span></div>
            </motion.div>
          ))}
          {!items.length && <div className="text-slate-500">No vitals recorded.</div>}
        </div>
      </Card>
      <Card title="Early warning" delay={0.05}>
        {p.news2 ? <div className="flex items-center gap-5"><Ring value={p.news2.score} max={20} size={110} color={news2Color(p.news2.score)} label={p.news2.score} sub="NEWS2" /><div className="text-[13px] leading-relaxed text-slate-300"><Badge color={riskColor(p.news2.risk)} dot>{p.news2.risk} risk</Badge><p className="mt-2 text-slate-400">{p.news2.response}</p></div></div> : <div className="text-slate-500">Not an inpatient.</div>}
      </Card>
      <Card title="Problems" delay={0.1}>
        <ul className="space-y-2" data-testid="problems">{conditions.map((c: any) => <li key={c.id} className="flex items-center justify-between rounded-xl bg-white/[0.03] px-3 py-2 text-[13px]"><span className="text-slate-100">{c.display}</span><span className="text-[11px] text-slate-500">{c.onset?.slice(0, 10)}</span></li>)}{!conditions.length && <div className="text-slate-500">None for this selection.</div>}</ul>
      </Card>
      <Card title="Medications" delay={0.15}>
        <ul className="space-y-2">{medications.map((m: any) => <li key={m.id} className="rounded-xl bg-white/[0.03] px-3 py-2 text-[13px]"><div className="text-slate-100">{m.display}</div><div className="text-[11.5px] text-slate-500">{m.sig}</div></li>)}{!medications.length && <div className="text-slate-500">None recorded.</div>}</ul>
      </Card>
      <Card title="Allergies and flags" delay={0.2}>
        {p.allergies_detail.length ? <ul className="space-y-2">{p.allergies_detail.map((a: any, i: number) => <li key={i} className="flex items-center gap-2 rounded-xl border border-aur-rose/30 bg-aur-rose/10 px-3 py-2 text-[13px] text-aur-rose"><AlertOctagon size={14} />{a.display ?? a.substance ?? JSON.stringify(a)}</li>)}</ul> : <div className="text-[13px] text-slate-400">No known drug allergies.</div>}
        <div className="mt-3 flex flex-wrap gap-1.5"><Badge color="#5cc8ff">Access: {p.access_reason}</Badge>{p.restricted && <Badge color="#ff7a90">Restricted record</Badge>}</div>
      </Card>
    </div>
  );
}

/* ============ Vitals and labs ============ */
const VMETA: Record<string, [string, string, string, [number, number]?]> = {
  hr: ["Heart rate", "/min", "#ff7a90", [51, 90]], rr: ["Respiratory rate", "/min", "#5cc8ff", [12, 20]], spo2: ["SpO₂", "%", "#34d6ae", [96, 100]], temp: ["Temperature", "°C", "#ffb454", [36.1, 38]],
  sbp: ["Systolic BP", "mmHg", "#8b7bff", [111, 219]], dbp: ["Diastolic BP", "mmHg", "#a89bff"], o2flow: ["Oxygen flow", "L/min", "#6ee7c8"],
};
export function VitalsLabs({ pid, filter }: { pid: string; filter?: OrganFilter | null }) {
  const vit = useApi(`/api/patients/${pid}/vitals`);
  const labs = useApi(`/api/patients/${pid}/labs`);
  return (
    <div className="space-y-5">
      <Gate state={vit}>{(v) => (
        <>
          <Card title="NEWS2 over time" sub="Recomputed every hour from the charted vitals. Shaded zones are the RCP 5–6 and 7+ response thresholds."><News2Chart data={v.news2} /></Card>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {Object.keys(VMETA).filter((k) => v.series[k]?.length && (!filter || filter.vitalKeys.has(k))).map((k) => (
              <Card key={k} title={VMETA[k][0]} sub={`Latest ${v.series[k][v.series[k].length - 1].v} ${VMETA[k][1]}`}><VitalChart data={v.series[k]} color={VMETA[k][2]} unit={VMETA[k][1]} band={VMETA[k][3]} /></Card>
            ))}
          </div>
        </>
      )}</Gate>
      <Gate state={labs}>{(l) => (
        <Card title="Laboratory results" sub="Green band is the reference interval. Hover for values and times.">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {l.labs.filter((x: any) => !filter || filter.labKeys.has(x.key)).map((x: any) => {
              const last = x.series[x.series.length - 1]; const abn = last.flag && last.flag !== "normal";
              return (
                <div key={x.key} className={cn("rounded-2xl border bg-white/[0.03] p-3", abn ? "border-aur-amber/30" : "hairline")}>
                  <div className="flex items-start justify-between"><div className="text-[12.5px] font-medium text-slate-200">{x.name}</div>{abn && <Badge color="#ffb454">{last.flag}</Badge>}</div>
                  <div className="h-display text-[22px] font-semibold text-white">{last.v}<span className="ml-1 text-[11px] font-normal text-slate-500">{x.unit}</span></div>
                  <LabChart series={x.series} low={x.low} high={x.high} color={abn ? "#ffb454" : "#34d6ae"} />
                  <div className="text-[10.5px] text-slate-500">LOINC {x.loinc} · ref {x.low}–{x.high}</div>
                </div>
              );
            })}
          </div>
        </Card>
      )}</Gate>
    </div>
  );
}
