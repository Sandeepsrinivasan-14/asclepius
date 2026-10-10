"use client";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { BellRing, Pause, Play } from "lucide-react";
import { getToken } from "@/lib/api";
import { Badge, Card, PageHeader, Pulse, Spark, useToast } from "@/components/ui";
import { cn, news2Color, riskColor } from "@/lib/utils";

type Live = { id: string; name: string; ward: string; bed: string; age: number; sex: string; hr: number; rr: number; spo2: number; sbp: number; dbp: number; temp: number; news2: number; risk: string; qsofa: number; acvpu: string; o2: boolean };

function Ecg({ hr, color }: { hr: number; color: string }) {
  const dur = Math.max(0.5, 60 / Math.max(hr, 30));
  const beat = "M0,20 L14,20 L18,16 L22,20 L34,20 L38,32 L42,2 L46,38 L50,20 L66,20 L72,14 L80,20 L100,20";
  return (
    <svg viewBox="0 0 200 40" className="h-10 w-full" preserveAspectRatio="none">
      <defs><linearGradient id={`e${color.slice(1)}`} x1="0" x2="1"><stop offset="0" stopColor={color} stopOpacity="0" /><stop offset="0.5" stopColor={color} /><stop offset="1" stopColor={color} /></linearGradient></defs>
      <g stroke={`url(#e${color.slice(1)})`} strokeWidth="1.6" fill="none" strokeLinejoin="round" style={{ filter: `drop-shadow(0 0 3px ${color})` }}>
        <path d={beat} /><path d={beat} transform="translate(100,0)" />
        <animateTransform attributeName="transform" type="translate" from="0 0" to="-100 0" dur={`${dur}s`} repeatCount="indefinite" />
      </g>
    </svg>
  );
}

function Num({ label, v, unit, bad, d = 0 }: { label: string; v: number | string; unit: string; bad?: boolean; d?: number }) {
  return <div><div className="eyebrow !text-[9px]">{label}</div><div className={cn("font-mono text-[19px] font-semibold leading-tight", bad ? "text-aur-rose" : "text-slate-100")}>{typeof v === "number" ? v.toFixed(d) : v}<span className="ml-0.5 text-[9px] font-normal text-slate-500">{unit}</span></div></div>;
}

export default function Monitor() {
  const [live, setLive] = useState<Record<string, Live>>({});
  const [hist, setHist] = useState<Record<string, number[]>>({});
  const [on, setOn] = useState(true);
  const [ward, setWard] = useState("All");
  const [status, setStatus] = useState("connecting");
  const toast = useToast();
  const es = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!on) { es.current?.close(); setStatus("paused"); return; }
    const src = new EventSource(`/api/monitor/stream?interval=1.2&access_token=${getToken()}`);
    es.current = src;
    src.onopen = () => setStatus("live");
    src.onerror = () => setStatus("reconnecting");
    src.onmessage = (m) => {
      const d = JSON.parse(m.data);
      const patients = Object.entries(d.patients).map(([id, v]: any) => ({ id, ...v }));
      setLive((prev) => { const next: Record<string, Live> = { ...prev }; patients.forEach((p: any) => { next[p.id] = { ...(prev[p.id] ?? {}), ...p }; }); return next; });
      setHist((prev) => { const n = { ...prev }; patients.forEach((p: any) => { n[p.id] = [...(n[p.id] ?? []).slice(-40), p.news2]; }); return n; });
      (d.alarms ?? []).forEach((a: any) => toast("err", `Alarm: ${a.id} moved to ${a.risk} risk (NEWS2 ${a.news2})`));
    };
    return () => src.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [on]);

  // enrich names once via snapshot
  useEffect(() => { fetch("/api/monitor/snapshot", { headers: { Authorization: `Bearer ${getToken()}` } }).then((r) => r.json()).then((d) => setLive((prev) => { const n = { ...prev }; d.patients.forEach((p: any) => { n[p.id] = { ...p, ...(prev[p.id] ?? {}), name: p.name, ward: p.ward, bed: p.bed, age: p.age, sex: p.sex }; }); return n; })).catch(() => {}); }, []);

  const rows = useMemo(() => Object.values(live).filter((p) => p.name && (ward === "All" || p.ward === ward)).sort((a, b) => b.news2 - a.news2), [live, ward]);
  const wards = ["All", ...Array.from(new Set(Object.values(live).map((p) => p.ward).filter(Boolean)))];
  return (
    <>
      <PageHeader eyebrow="Clinical" title="Live bedside monitor" sub="A simulated telemetry stream (server-sent events) drives NEWS2 and qSOFA recalculation in real time. Tiles reorder by acuity and raise an alarm when a patient crosses a risk band."
        actions={<><Badge color={status === "live" ? "#34d6ae" : "#ffb454"} dot>{status}</Badge><button className="btn" onClick={() => setOn((v) => !v)}>{on ? <Pause size={14} /> : <Play size={14} />}{on ? "Pause" : "Resume"}</button></>} />
      <div className="mb-4 flex gap-1.5">{wards.map((w) => <button key={w} onClick={() => setWard(w)} className={cn("chip cursor-pointer !px-3 !py-1.5 text-[12px]", ward === w && "!border-jade-400/50 !bg-jade-400/15 !text-jade-300")}>{w}</button>)}</div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        <AnimatePresence>
          {rows.map((p) => { const c = news2Color(p.news2); return (
            <motion.div layout key={p.id} initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ type: "spring", stiffness: 300, damping: 30 }}>
              <Link href={`/patients/${p.id}`} className={cn("glass relative block overflow-hidden p-4", p.news2 >= 7 && "!border-aur-rose/50")} style={p.news2 >= 7 ? { boxShadow: "0 0 40px -10px rgba(255,122,144,.5)" } : undefined}>
                {p.news2 >= 7 && <div className="absolute inset-0 animate-pulse bg-aur-rose/[0.04]" />}
                <div className="relative flex items-start justify-between">
                  <div><div className="text-[14px] font-semibold text-white">{p.name}</div><div className="text-[11px] text-slate-500">{p.bed} · {p.age}{p.sex?.[0]?.toUpperCase()}</div></div>
                  <div className="text-right"><div className="h-display text-[30px] font-semibold leading-none" style={{ color: c, textShadow: `0 0 20px ${c}66` }}>{p.news2}</div><div className="eyebrow !text-[9px]">NEWS2</div></div>
                </div>
                <div className="relative mt-1"><Ecg hr={p.hr} color={c} /></div>
                <div className="relative mt-1 grid grid-cols-5 gap-2">
                  <Num label="HR" v={p.hr} unit="/m" bad={p.hr > 110 || p.hr < 50} /><Num label="RR" v={p.rr} unit="/m" bad={p.rr > 24 || p.rr < 9} /><Num label="SpO₂" v={p.spo2} unit="%" bad={p.spo2 < 92} />
                  <Num label="SBP" v={p.sbp} unit="" bad={p.sbp < 100} /><Num label="Temp" v={p.temp} unit="°" d={1} bad={p.temp > 38.5 || p.temp < 36} />
                </div>
                <div className="relative mt-3 flex items-center justify-between"><div className="flex gap-1.5"><Badge color={riskColor(p.risk)} dot>{p.risk}</Badge><Badge>qSOFA {p.qsofa}</Badge>{p.o2 && <Badge color="#5cc8ff">O₂</Badge>}</div><Spark data={hist[p.id] ?? [p.news2]} color={c} w={70} h={22} /></div>
              </Link>
            </motion.div>); })}
        </AnimatePresence>
      </div>
      {!rows.length && <Card><div className="flex items-center gap-3 text-slate-400"><Pulse />Waiting for telemetry…</div></Card>}
    </>
  );
}
