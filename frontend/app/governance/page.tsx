"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Eye } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, Card, Disclaimer, Gate, PageHeader, Ring, Tabs, useApi } from "@/components/ui";
import { cn, pct } from "@/lib/utils";

const tipStyle = { contentStyle: { background: "rgba(7,12,22,.95)", border: "1px solid rgba(255,255,255,.1)", borderRadius: 12, fontSize: 12 } };
const LV: Record<string, string> = { stable: "#34d6ae", watch: "#ffb454", drift: "#ff7a90" };
type T = "cards" | "drift" | "fair" | "override";

export default function Governance() {
  const [tab, setTab] = useState<T>("cards");
  const models = useApi("/api/governance/models");
  const drift = useApi("/api/governance/drift");
  const fair = useApi("/api/governance/fairness");
  const ov = useApi("/api/governance/overrides");
  return (
    <>
      <PageHeader eyebrow="Trust and operations" title="AI governance" sub="Responsible deployment is part of the product. Every model has a card with its intended use and limits, is monitored for drift, audited for subgroup fairness, and measured against how often clinicians override it." />
      <Tabs tabs={[{ id: "cards", label: "Model cards" }, { id: "drift", label: "Drift (PSI)" }, { id: "fair", label: "Fairness" }, { id: "override", label: "Clinician overrides" }]} value={tab} onChange={setTab} layout="gov" />
      {tab === "cards" && <Gate state={models}>{(m) => (
        <div className="space-y-5">
          <div className="grid gap-5 xl:grid-cols-2">{m.models.map((x: any, i: number) => (
            <Card key={x.id} delay={i * 0.05} title={<span className="flex items-center gap-2">{x.name}<Badge color="#34d6ae" dot>{x.status}</Badge><span className="font-mono text-[11px] font-normal text-slate-500">v{x.version}</span></span>} sub={x.kind}>
              <p className="text-[13px] leading-relaxed text-slate-300"><b className="text-slate-100">Intended use. </b>{x.intended_use}</p>
              <div className="mt-3 grid grid-cols-2 gap-2">{Object.entries(x.metrics).map(([k, v]: any) => <div key={k} className="rounded-xl bg-white/[0.04] p-2.5"><div className="h-display text-lg font-semibold text-white">{typeof v === "number" && /concordance|prevalence/i.test(k) ? pct(v, 1) : String(v)}</div><div className="text-[10.5px] leading-tight text-slate-500">{k}</div></div>)}</div>
              <div className="mt-3"><div className="eyebrow mb-1 text-aur-rose">Out of scope</div><div className="flex flex-wrap gap-1.5">{x.out_of_scope.map((o: string) => <Badge key={o} color="#ff7a90">{o}</Badge>)}</div></div>
              <div className="mt-3"><div className="eyebrow mb-1 text-aur-gold">Known limitations</div><ul className="space-y-1 text-[12.5px] text-slate-400">{x.limitations.map((l: string) => <li key={l}>• {l}</li>)}</ul></div>
              <div className="mt-3 rounded-xl border border-jade-400/20 bg-jade-400/[0.06] p-3 text-[12.5px] text-jade-300"><Eye size={13} className="mr-1.5 inline" />{x.oversight}</div>
              <div className="mt-2 text-[11.5px] text-slate-500">Data: {x.data}</div>
            </Card>))}</div>
          <Card title="Calibration" sub="Predicted versus observed event rate in ten equal-sized bins. Points on the diagonal are well calibrated.">
            <ResponsiveContainer width="100%" height={260}><LineChart data={m.calibration} margin={{ left: -10, right: 10 }}><CartesianGrid stroke="rgba(255,255,255,.05)" /><XAxis dataKey="predicted" tick={{ fill: "#6b7f9d", fontSize: 10 }} axisLine={false} tickLine={false} /><YAxis tick={{ fill: "#6b7f9d", fontSize: 10 }} axisLine={false} tickLine={false} /><Tooltip {...tipStyle} /><Legend />
              <Line isAnimationActive={false} type="monotone" dataKey="observed" stroke="#34d6ae" strokeWidth={2.5} dot={{ r: 3 }} name="Observed" /><Line isAnimationActive={false} type="monotone" dataKey="predicted" stroke="#f2c46d" strokeDasharray="5 5" dot={false} name="Perfect calibration" /></LineChart></ResponsiveContainer>
          </Card>
        </div>)}</Gate>}
      {tab === "drift" && <Gate state={drift}>{(d) => (
        <div className="space-y-5">
          <Card title="Population stability index" sub={`${d.summary.drifting} features drifting, ${d.summary.watch} on watch, worst: ${d.summary.worst}. Window of ${d.window_rows} live rows versus the training cohort.`}>
            <ResponsiveContainer width="100%" height={300}><BarChart data={d.features.map((f: any) => ({ ...f, fill: LV[f.level] }))} margin={{ left: -10 }}><CartesianGrid stroke="rgba(255,255,255,.05)" vertical={false} /><XAxis dataKey="label" tick={{ fill: "#9fb3cf", fontSize: 11 }} axisLine={false} tickLine={false} /><YAxis tick={{ fill: "#6b7f9d", fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip {...tipStyle} cursor={{ fill: "rgba(255,255,255,.04)" }} /><ReferenceLine y={d.thresholds.watch ?? 0.1} stroke="#ffb454" strokeDasharray="4 4" /><ReferenceLine y={d.thresholds.drift ?? 0.25} stroke="#ff7a90" strokeDasharray="4 4" />
              <Bar isAnimationActive={false} dataKey="psi" radius={6} /></BarChart></ResponsiveContainer>
            <p className="mt-2 text-[12.5px] leading-relaxed text-slate-400">{d.interpretation}</p>
          </Card>
          <div className="grid gap-3 md:grid-cols-4">{d.features.slice(0, 8).map((f: any) => <div key={f.feature} className="glass p-3.5"><div className="flex justify-between"><span className="text-[12.5px] text-slate-200">{f.label}</span><Badge color={LV[f.level]}>{f.level}</Badge></div><div className="mt-2 text-[12px] text-slate-500">training {f.reference} → now {f.current}</div></div>)}</div>
        </div>)}</Gate>}
      {tab === "fair" && <Gate state={fair}>{(f) => (
        <div className="space-y-5">
          <Disclaimer>{f.rule} {f.caveat}</Disclaimer>
          <div className="grid gap-5 xl:grid-cols-2">{f.attributes.map((a: any) => (
            <Card key={a.attribute} title={<span className="flex items-center gap-2">{a.attribute}{a.flagged ? <Badge color="#ffb454"><AlertTriangle size={11} />Flagged</Badge> : <Badge color="#34d6ae"><CheckCircle2 size={11} />Within rule</Badge>}</span>} sub={`AUC gap ${a.auc_gap} · TPR ratio ${a.tpr_ratio} (rule: ≥ 0.80)`}>
              <ResponsiveContainer width="100%" height={210}><BarChart data={Object.entries(a.groups).map(([k, v]: any) => ({ group: k, TPR: v.tpr, FPR: v.fpr, AUC: v.auc }))} margin={{ left: -15 }}><CartesianGrid stroke="rgba(255,255,255,.05)" vertical={false} /><XAxis dataKey="group" tick={{ fill: "#9fb3cf", fontSize: 11 }} axisLine={false} tickLine={false} /><YAxis domain={[0, 1]} tick={{ fill: "#6b7f9d", fontSize: 10 }} axisLine={false} tickLine={false} /><Tooltip {...tipStyle} cursor={{ fill: "rgba(255,255,255,.04)" }} /><Legend />
                <Bar isAnimationActive={false} dataKey="AUC" fill="#5cc8ff" radius={4} /><Bar isAnimationActive={false} dataKey="TPR" fill="#34d6ae" radius={4} /><Bar isAnimationActive={false} dataKey="FPR" fill="#ff7a90" radius={4} /></BarChart></ResponsiveContainer>
              <div className="mt-2 flex flex-wrap gap-2">{Object.entries(a.groups).map(([k, v]: any) => <Badge key={k}>{k}: n={v.n}</Badge>)}</div>
            </Card>))}</div>
        </div>)}</Gate>}
      {tab === "override" && <Gate state={ov}>{(o) => (
        <div className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">{Object.entries(o.models).map(([k, v]: any, i) => (
            <Card key={k} delay={i * 0.05}><div className="flex items-center gap-4"><Ring value={v.override_rate} size={84} stroke={8} color={v.override_rate > 0.4 ? "#ff7a90" : v.override_rate > 0.25 ? "#ffb454" : "#34d6ae"} label={pct(v.override_rate)} sub="override" />
              <div><div className="text-[14px] font-medium capitalize text-white">{k}</div><div className="text-[11.5px] text-slate-500">{v.accepted} accepted · {v.modified} modified · {v.rejected} rejected</div><div className="mt-1 text-[11px] text-jade-300">{v.live_events} live events</div></div></div>
              <div className="mt-3 space-y-1">{v.top_reasons.map((r: any) => <div key={r.reason} className="flex justify-between text-[12px] text-slate-400"><span>{r.reason}</span><span className="text-slate-500">{r.count}</span></div>)}</div></Card>))}</div>
          <Card title="Recent decisions" sub={o.note}><div className="space-y-1.5">{o.recent.map((r: any) => <div key={r.id} className="flex items-center gap-3 rounded-xl bg-white/[0.03] px-3 py-2 text-[12.5px]"><Badge color={r.action === "accepted" ? "#34d6ae" : r.action === "modified" ? "#f2c46d" : "#ff7a90"}>{r.action}</Badge><span className="capitalize text-slate-200">{r.model}</span><span className="text-slate-500">{r.user}</span><span className="flex-1 truncate text-slate-400">{r.reason}</span>{r.simulated && <Badge>simulated</Badge>}</div>)}</div></Card>
        </div>)}</Gate>}
    </>
  );
}
