"use client";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Minus, Plus } from "lucide-react";
import { Area, Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Sankey, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { Badge, Card, Disclaimer, Gate, PageHeader, Ring, Stat, Table, Tabs, useApi } from "@/components/ui";
import { cn } from "@/lib/utils";

const tipStyle = { contentStyle: { background: "rgba(7,12,22,.95)", border: "1px solid rgba(255,255,255,.1)", borderRadius: 12, fontSize: 12 } };
const axis = { tick: { fill: "#6b7f9d", fontSize: 10 }, axisLine: false, tickLine: false } as const;
type T = "beds" | "opd" | "los" | "flow";

function Forecast({ f }: { f: any }) {
  const [w, setW] = useState(0);
  const x = f.wards[w];
  const hist = x.history.slice(-14);
  const hd = f.history_dates.slice(-14);
  const data = [...hist.map((v: number, i: number) => ({ d: hd[i].slice(5), actual: v })), ...x.forecast.map((v: number, i: number) => ({ d: f.dates[i].slice(5), forecast: v, band: [x.lower[i], x.upper[i]], })) ];
  return (
    <Card title="7-day occupancy forecast" sub={f.method} right={<div className="flex gap-1.5">{f.wards.map((a: any, i: number) => <button key={a.ward} onClick={() => setW(i)} className={cn("chip cursor-pointer", w === i && "!border-jade-400/50 !bg-jade-400/15 !text-jade-300")}>{a.ward}</button>)}</div>}>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ left: -15, right: 10 }}>
          <defs><linearGradient id="bandg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#5cc8ff" stopOpacity={0.35} /><stop offset="1" stopColor="#5cc8ff" stopOpacity={0.05} /></linearGradient></defs>
          <CartesianGrid stroke="rgba(255,255,255,.05)" vertical={false} /><XAxis dataKey="d" {...axis} /><YAxis {...axis} domain={[0, x.beds + 1]} />
          <Tooltip {...tipStyle} /><ReferenceLine y={x.beds} stroke="#ff7a90" strokeDasharray="5 5" label={{ value: `${x.beds} beds`, fill: "#ff7a90", fontSize: 11, position: "insideTopLeft" }} />
          <Area isAnimationActive={false} type="monotone" dataKey="band" stroke="none" fill="url(#bandg)" name="80% interval" />
          <Line isAnimationActive={false} type="monotone" dataKey="actual" stroke="#34d6ae" strokeWidth={2.4} dot={false} name="Occupied" connectNulls />
          <Line isAnimationActive={false} type="monotone" dataKey="forecast" stroke="#5cc8ff" strokeWidth={2.4} strokeDasharray="5 4" dot={{ r: 3 }} name="Forecast" connectNulls />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="mt-2 text-[12.5px] text-slate-400">{x.breach_day ? <Badge color="#ff7a90" dot>Capacity breach expected on {x.breach_day}</Badge> : <Badge color="#34d6ae" dot>No capacity breach forecast in 7 days</Badge>}</div>
    </Card>
  );
}

function Opd() {
  const [extra, setExtra] = useState<Record<string, number>>({});
  const q = Object.entries(extra).filter(([, n]) => n).map(([k, n]) => `${k}:${n}`).join("|");
  const st = useApi(`/api/ops/opd?extra=${encodeURIComponent(q)}`, [q]);
  const [c, setC] = useState(0);
  return <Gate state={st}>{(d) => {
    const cl = d.clinics[c];
    const rows = cl.hours.map((h: any) => ({ hour: `${h.hour}:00`, arrivals: h.arrivals, util: Math.round(h.utilisation * 100), wait: h.mean_wait_min }));
    return (
      <div className="grid gap-5 xl:grid-cols-[1fr_1.2fr]">
        <Card title="Clinics" sub={d.method}>
          <div className="space-y-2">{d.clinics.map((x: any, i: number) => {
            const over = x.hours.some((h: any) => h.overloaded);
            return (<div key={x.clinic} onClick={() => setC(i)} className={cn("flex cursor-pointer items-center justify-between rounded-xl border p-3 transition", c === i ? "border-jade-400/40 bg-jade-400/[0.07]" : "hairline bg-white/[0.03]")}>
              <div><div className="text-[13.5px] font-medium text-white">{x.clinic}</div><div className="text-[11.5px] text-slate-500">{x.servers} doctors · {x.service_min} min / visit</div></div>
              <div className="flex items-center gap-2">{over ? <Badge color="#ff7a90" dot>Overloaded</Badge> : <Badge color="#34d6ae" dot>OK</Badge>}
                <button className="btn !p-1.5" onClick={(e) => { e.stopPropagation(); setExtra((s) => ({ ...s, [x.clinic]: Math.max(0, (s[x.clinic] ?? 0) - 1) })); }}><Minus size={12} /></button>
                <span className="w-5 text-center font-mono text-[12px] text-slate-300">{extra[x.clinic] ? `+${extra[x.clinic]}` : "±0"}</span>
                <button className="btn !p-1.5" onClick={(e) => { e.stopPropagation(); setExtra((s) => ({ ...s, [x.clinic]: Math.min(4, (s[x.clinic] ?? 0) + 1) })); }}><Plus size={12} /></button></div></div>);
          })}</div>
          <p className="mt-3 text-[12px] text-slate-500">What-if: add or remove doctors and the Erlang C model and the day simulation recompute instantly.</p>
        </Card>
        <div className="space-y-5">
          <Card title={`${cl.clinic}: utilisation and wait by hour`}>
            <ResponsiveContainer width="100%" height={230}><ComposedChart data={rows} margin={{ left: -15 }}><CartesianGrid stroke="rgba(255,255,255,.05)" vertical={false} /><XAxis dataKey="hour" {...axis} /><YAxis yAxisId="l" {...axis} /><YAxis yAxisId="r" orientation="right" {...axis} /><Tooltip {...tipStyle} /><Legend />
              <Bar isAnimationActive={false} yAxisId="l" dataKey="arrivals" fill="#5cc8ff55" radius={4} name="Arrivals" /><Line isAnimationActive={false} yAxisId="l" dataKey="util" stroke="#f2c46d" strokeWidth={2} dot={false} name="Utilisation %" /><Line isAnimationActive={false} yAxisId="r" dataKey="wait" stroke="#ff7a90" strokeWidth={2.4} dot={false} name="Mean wait (min)" /></ComposedChart></ResponsiveContainer>
          </Card>
          <Card title="Simulated waiting room" sub="Discrete-event simulation of one day"><ResponsiveContainer width="100%" height={170}><ComposedChart data={cl.queue_timeline} margin={{ left: -15 }}><CartesianGrid stroke="rgba(255,255,255,.05)" vertical={false} /><XAxis dataKey="time" {...axis} minTickGap={24} /><YAxis {...axis} /><Tooltip {...tipStyle} /><Area isAnimationActive={false} type="stepAfter" dataKey="waiting" stroke="#8b7bff" fill="#8b7bff33" name="Patients waiting" /></ComposedChart></ResponsiveContainer></Card>
        </div>
      </div>);
  }}</Gate>;
}

function Los() {
  const census = useApi("/api/ops/census");
  const [f, setF] = useState({ age: 68, ward: "MED", acuity: 4, comorbidities: 2, emergency: true });
  const [res, setRes] = useState<any>(null);
  const run = async () => setRes(await api("/api/ops/los", { body: f }));
  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_1.3fr]">
      <Card title="Length-of-stay predictor" sub="Log-linear regression on a synthetic admission cohort">
        <div className="grid grid-cols-2 gap-3">
          <div><label className="eyebrow">Age</label><input type="number" className="input mt-1" value={f.age} onChange={(e) => setF({ ...f, age: +e.target.value })} /></div>
          <div><label className="eyebrow">Ward</label><select className="input mt-1" value={f.ward} onChange={(e) => setF({ ...f, ward: e.target.value })}>{["ICU", "CCU", "MED", "NEURO"].map((w) => <option key={w}>{w}</option>)}</select></div>
          <div><label className="eyebrow">Acuity (NEWS2)</label><input type="number" className="input mt-1" value={f.acuity} onChange={(e) => setF({ ...f, acuity: +e.target.value })} /></div>
          <div><label className="eyebrow">Comorbidities</label><input type="number" className="input mt-1" value={f.comorbidities} onChange={(e) => setF({ ...f, comorbidities: +e.target.value })} /></div>
        </div>
        <label className="mt-3 flex items-center gap-2 text-[13px] text-slate-300"><input type="checkbox" checked={f.emergency} onChange={(e) => setF({ ...f, emergency: e.target.checked })} className="accent-[#34d6ae]" />Emergency admission</label>
        <button className="btn btn-primary mt-4" onClick={run}>Predict</button>
        {res && <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mt-4 grid grid-cols-3 gap-2">{[["p10", res.p10_days], ["Median", res.median_days], ["p90", res.p90_days]].map(([k, v]: any) => <div key={k} className="rounded-xl bg-white/[0.05] p-3 text-center"><div className="h-display text-2xl font-semibold text-white">{v}</div><div className="eyebrow">{k} days</div></div>)}<div className="col-span-3 text-[11.5px] text-slate-500">Model MAE {res.model.mae_days} days · R² (log) {res.model.r2_log} · n={res.model.n_train}</div></motion.div>}
      </Card>
      <Card title="Live census with expected discharge" pad={false}>
        <Gate state={census}>{(c) => (<div className="max-h-[430px] overflow-auto"><Table head={["Bed", "Age", "NEWS2", "Day", "Predicted stay", "Remaining"]}>{c.beds.map((b: any) => <tr key={b.bed}><td className="td font-mono text-[12px] text-slate-200">{b.bed}</td><td className="td text-slate-400">{b.age_band}</td><td className="td">{b.news2}</td><td className="td text-slate-400">{b.elapsed_days}</td><td className="td text-slate-400">{b.predicted_total_days} d</td><td className="td"><Badge color={b.predicted_remaining_days <= 1 ? "#34d6ae" : "#5cc8ff"}>{b.predicted_remaining_days} d</Badge></td></tr>)}</Table>
          <div className="px-4 pb-4 text-[12.5px] text-slate-400">Expected discharges: <b className="text-slate-200">{c.expected_discharges_24h}</b> in 24 h · <b className="text-slate-200">{c.expected_discharges_48h}</b> in 48 h</div></div>)}</Gate>
      </Card>
    </div>
  );
}

function Flow() {
  const st = useApi("/api/ops/flow");
  return <Gate state={st}>{(d) => {
    const idx = Object.fromEntries(d.nodes.map((n: any, i: number) => [n.id, i]));
    const data = { nodes: d.nodes.map((n: any) => ({ name: n.label })), links: d.links.map((l: any) => ({ source: idx[l.source], target: idx[l.target], value: l.value })) };
    const colors = ["#34d6ae", "#5cc8ff", "#f2c46d", "#8b7bff", "#ff7a90", "#6ee7c8", "#ffb454", "#a89bff", "#9fb3cf"];
    return (
      <Card title="Patient flow" sub={`${d.note} Last ${d.period_days} days.`}>
        <ResponsiveContainer width="100%" height={460}>
          <Sankey data={data} nodePadding={26} nodeWidth={14} margin={{ left: 10, right: 230, top: 10, bottom: 10 }} link={{ stroke: "#5cc8ff", strokeOpacity: 0.22 }}
            node={({ x, y, width, height, index, payload }: any) => <g><rect x={x} y={y} width={width} height={height} rx={4} fill={colors[index % colors.length]} /><text x={x + width + 8} y={y + height / 2} fill="#cbd8ec" fontSize={12} dominantBaseline="middle">{payload.name} ({payload.value})</text></g>}>
            <Tooltip {...tipStyle} />
          </Sankey>
        </ResponsiveContainer>
      </Card>);
  }}</Gate>;
}

export default function Ops() {
  const [tab, setTab] = useState<T>("beds");
  const ov = useApi("/api/ops/overview");
  const fc = useApi("/api/ops/forecast");
  return (
    <>
      <PageHeader eyebrow="Trust and operations" title="Hospital operations twin" sub="A digital twin for administrators: forecast beds with Holt-Winters, size OPD clinics with queueing theory and simulation, predict length of stay, and see where patients flow." />
      <Gate state={ov}>{(o) => <div className="mb-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">{o.wards.map((w: any, i: number) => (
        <Card key={w.code} delay={i * 0.05}><div className="flex items-center gap-4"><Ring value={w.occupancy} size={84} stroke={8} color={w.occupancy > 0.85 ? "#ff7a90" : w.occupancy > 0.7 ? "#ffb454" : "#34d6ae"} label={`${Math.round(w.occupancy * 100)}%`} /><div><div className="text-[14px] font-medium text-white">{w.name}</div><div className="text-[12px] text-slate-500">{w.occupied}/{w.beds} beds · {w.available} free</div><div className={cn("text-[11.5px]", w.change_vs_yesterday > 0 ? "text-aur-amber" : "text-slate-500")}>{w.change_vs_yesterday > 0 ? "+" : ""}{w.change_vs_yesterday} vs yesterday</div></div></div></Card>))}</div>}</Gate>
      <Tabs tabs={[{ id: "beds", label: "Bed forecast" }, { id: "opd", label: "OPD queues" }, { id: "los", label: "Length of stay" }, { id: "flow", label: "Patient flow" }]} value={tab} onChange={setTab} layout="ops" />
      {tab === "beds" && <Gate state={fc}>{(f) => <Forecast f={f} />}</Gate>}
      {tab === "opd" && <Opd />}
      {tab === "los" && <Los />}
      {tab === "flow" && <Flow />}
    </>
  );
}
