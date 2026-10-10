"use client";
import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Eye, EyeOff, ScanLine } from "lucide-react";
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { img } from "@/lib/api";
import { Badge, Card, Disclaimer, Gate, PageHeader, Ring, useApi } from "@/components/ui";
import { cn, pct } from "@/lib/utils";

export default function Imaging() {
  const studies = useApi("/api/imaging/studies");
  const [sid, setSid] = useState("MR-BRAIN-A");
  const det = useApi(`/api/imaging/studies/${sid}`, [sid]);
  const [i, setI] = useState(12);
  const [overlay, setOverlay] = useState(true);
  const [play, setPlay] = useState(false);
  const n = det.data?.study.slices ?? 24;
  const raf = useRef<any>(null);
  useEffect(() => { if (det.data) setI(det.data.analysis.best_slice ?? 0); }, [det.data?.study.id]); // eslint-disable-line
  useEffect(() => { if (!play) return; raf.current = setInterval(() => setI((x) => (x + 1) % n), 220); return () => clearInterval(raf.current); }, [play, n]);
  const a = det.data?.analysis;
  const curve = a?.per_slice_probability.map((p: number, k: number) => ({ k, p })) ?? [];
  const pos = a && a.probability > 0.5;
  return (
    <>
      <PageHeader eyebrow="Clinical" title="Imaging viewer" sub="Synthetic phantoms only. A classical atlas-subtraction detector scores every slice and paints a heat overlay. The architecture is ready for a validated model to replace it." />
      <div className="mb-4 flex flex-wrap gap-2">{studies.data?.studies.map((s: any) => <button key={s.id} onClick={() => { setSid(s.id); setPlay(false); }} className={cn("glass px-4 py-2.5 text-left transition", sid === s.id && "!border-jade-400/40 shadow-glow")}><div className="text-[13px] font-medium text-white">{s.title}</div><div className="text-[11px] text-slate-500">{s.modality} · {s.slices} slices</div></button>)}</div>
      <Gate state={det}>{(d) => (
        <div className="grid gap-5 xl:grid-cols-[1.3fr_1fr]">
          <Card pad={false} className="scan-line">
            <div className="relative mx-auto aspect-square w-full max-w-[640px] bg-black">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={img(`/api/imaging/studies/${sid}/slice/${i}.png`)} alt="slice" className="absolute inset-0 h-full w-full object-contain [image-rendering:auto]" />
              {overlay && <img src={img(`/api/imaging/studies/${sid}/overlay/${i}.png`)} alt="overlay" className="absolute inset-0 h-full w-full object-contain mix-blend-screen opacity-90" />}
              <div className="absolute left-3 top-3 font-mono text-[11px] text-jade-300/80">{d.metadata.StudyDescription}<br />slice {i + 1}/{n} · {d.metadata.PixelSpacing[0]} mm</div>
              <div className="absolute bottom-3 right-3 font-mono text-[11px] text-slate-400">{d.metadata.PatientName}</div>
              <div className="absolute bottom-3 left-3 rounded-full bg-black/60 px-2.5 py-1 font-mono text-[11px] text-slate-300">P(finding) {pct(a.per_slice_probability[i] ?? 0)}</div>
            </div>
            <div className="flex items-center gap-4 p-4">
              <input type="range" min={0} max={n - 1} value={i} onChange={(e) => setI(+e.target.value)} className="flex-1 accent-[#34d6ae]" />
              <button className="btn" onClick={() => setPlay((v) => !v)}>{play ? "Pause" : "Scroll"}</button>
              <button className="btn" onClick={() => setOverlay((v) => !v)}>{overlay ? <Eye size={14} /> : <EyeOff size={14} />}AI overlay</button>
            </div>
          </Card>
          <div className="space-y-5">
            <Card title="AI finding" hi>
              <div className="flex items-center gap-5"><Ring value={a.probability} size={104} color={pos ? "#ff7a90" : "#34d6ae"} label={pct(a.probability)} sub="max slice" />
                <div><Badge color={pos ? "#ff7a90" : "#34d6ae"} dot>{a.finding}</Badge>{a.location && <div className="mt-2 text-[12.5px] text-slate-400">Best slice {a.best_slice + 1} · x {a.location.x}, y {a.location.y}</div>}<button className="btn mt-3 !py-1.5 text-[12px]" onClick={() => setI(a.best_slice)}><ScanLine size={13} />Jump to best slice</button></div></div>
            </Card>
            <Card title="Per-slice probability">
              <ResponsiveContainer width="100%" height={170}><AreaChart data={curve} margin={{ left: -20, right: 6, top: 6 }}><defs><linearGradient id="pg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#ff7a90" stopOpacity={0.5} /><stop offset="1" stopColor="#ff7a90" stopOpacity={0} /></linearGradient></defs>
                <CartesianGrid stroke="rgba(255,255,255,.05)" vertical={false} /><XAxis dataKey="k" tick={{ fill: "#6b7f9d", fontSize: 10 }} axisLine={false} tickLine={false} /><YAxis domain={[0, 1]} tick={{ fill: "#6b7f9d", fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: "rgba(7,12,22,.95)", border: "1px solid rgba(255,255,255,.1)", borderRadius: 12, fontSize: 12 }} /><ReferenceLine x={i} stroke="#34d6ae" /><Area isAnimationActive={false} type="monotone" dataKey="p" stroke="#ff7a90" strokeWidth={2} fill="url(#pg)" /></AreaChart></ResponsiveContainer>
            </Card>
            <Card title="DICOM-style metadata"><div className="grid grid-cols-2 gap-1.5 font-mono text-[11.5px]">{Object.entries(d.metadata).map(([k, v]: any) => <div key={k} className="flex justify-between rounded-lg bg-white/[0.04] px-2.5 py-1.5"><span className="text-slate-500">{k}</span><span className="truncate pl-2 text-slate-300">{String(v)}</span></div>)}</div></Card>
            <Disclaimer>{a.disclaimer}</Disclaimer>
          </div>
        </div>
      )}</Gate>
    </>
  );
}
