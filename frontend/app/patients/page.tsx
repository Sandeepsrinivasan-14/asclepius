"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Lock, Search } from "lucide-react";
import { Badge, Card, Gate, PageHeader, useApi } from "@/components/ui";
import { cn, news2Color, riskColor } from "@/lib/utils";

export default function Patients() {
  const st = useApi("/api/patients");
  const [q, setQ] = useState("");
  const [ward, setWard] = useState("All");
  const [risk, setRisk] = useState("All");
  const list = useMemo(() => (st.data?.patients ?? []).filter((p: any) => {
    const s = q.toLowerCase();
    return (ward === "All" || p.ward === ward || (ward === "Outpatient" && p.status !== "inpatient")) && (risk === "All" || p.news2?.risk === risk.toLowerCase())
      && (!s || p.name.toLowerCase().includes(s) || p.mrn.toLowerCase().includes(s) || p.conditions.join(" ").toLowerCase().includes(s));
  }), [st.data, q, ward, risk]);
  const wards = ["All", "ICU", "CCU", "MED", "NEURO", "Outpatient"];
  return (
    <>
      <PageHeader eyebrow="Clinical" title="Patients" sub="Only patients you are allowed to see are listed. Restricted charts stay locked until break-glass is used and reviewed." />
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="relative min-w-[260px] flex-1 md:max-w-sm"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" /><input className="input !pl-9" placeholder="Name, MRN or condition" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <div className="flex flex-wrap gap-1.5">{wards.map((w) => <button key={w} onClick={() => setWard(w)} className={cn("chip cursor-pointer !px-3 !py-1.5 text-[12px]", ward === w && "!border-jade-400/50 !bg-jade-400/15 !text-jade-300")}>{w}</button>)}</div>
        <div className="flex flex-wrap gap-1.5">{["All", "High", "Medium", "Low"].map((w) => <button key={w} onClick={() => setRisk(w)} className={cn("chip cursor-pointer !px-3 !py-1.5 text-[12px]", risk === w && "!border-aur-gold/50 !bg-aur-gold/15 !text-aur-gold")}>{w === "All" ? "Any risk" : w + " risk"}</button>)}</div>
        <span className="text-[12px] text-slate-500">{list.length} shown</span>
      </div>
      <Gate state={st}>{() => (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {list.map((p: any, i: number) => (
            <motion.div key={p.id} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 14) * 0.03 }} whileHover={{ y: -4 }}>
              <Link href={`/patients/${p.id}`} className="glass group relative block overflow-hidden p-4 transition hover:border-jade-400/30">
                {p.news2 && <div className="absolute inset-y-0 left-0 w-[3px]" style={{ background: news2Color(p.news2.score) }} />}
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="grid h-11 w-11 place-items-center rounded-2xl border hairline bg-white/[0.04] text-[12px] font-semibold text-slate-200">{p.name.split(" ").map((x: string) => x[0]).join("").slice(0, 2)}</div>
                    <div><div className="flex items-center gap-1.5 text-[14px] font-semibold text-white group-hover:text-jade-300">{p.name}{p.restricted && <Lock size={12} className="text-aur-rose" />}</div><div className="text-[11.5px] text-slate-500">{p.age} y · {p.sex} · {p.mrn}</div></div>
                  </div>
                  {p.news2 && <div className="text-right"><div className="h-display text-[26px] font-semibold leading-none" style={{ color: news2Color(p.news2.score) }}>{p.news2.score}</div><div className="eyebrow !text-[9px]">NEWS2</div></div>}
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {p.status === "inpatient" ? <Badge color="#5cc8ff">{p.ward} · {p.bed}</Badge> : <Badge>Outpatient</Badge>}
                  {p.ml_tier && <Badge color={riskColor(p.ml_tier)} dot>ML {p.ml_tier}</Badge>}
                  {p.allergies?.length > 0 && <Badge color="#ff7a90">Allergy: {String(p.allergies[0]).replace(/^Allergy to /i, "")}</Badge>}
                </div>
                <div className="mt-3 line-clamp-2 text-[12.5px] text-slate-400">{p.conditions.join(" · ") || "No active conditions"}</div>
              </Link>
            </motion.div>
          ))}
        </div>
      )}</Gate>
    </>
  );
}
