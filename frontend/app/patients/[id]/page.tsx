"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { motion } from "framer-motion";
import { Activity, AlertOctagon, ArrowLeft, BrainCircuit, Boxes, FileOutput, FilterX, ClipboardList, FileText, FlaskConical, Globe2, Lock, Pill, ShieldAlert, UserRound, Siren, Clock } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Modal, PageHeader, Tabs, useApi, useToast, Loading, ErrorBox, Disclaimer } from "@/components/ui";
import { Overview, VitalsLabs } from "@/components/patient/tabs";
import { BodyMapTab, makeFilter, type OrganFilter } from "@/components/patient/bodymap";
import { Copilot, Handoff, MedRec, NotesCoding, Portal, Timeline, Warning } from "@/components/patient/tabs2";
import { news2Color, riskColor } from "@/lib/utils";

type T = "overview" | "bodymap" | "vitals" | "timeline" | "notes" | "copilot" | "warning" | "medrec" | "handoff" | "portal";

export default function PatientPage() {
  const { id } = useParams<{ id: string }>();
  const st = useApi(`/api/patients/${id}`);
  const [tab, setTab] = useState<T>("overview");
  const bm = useApi(st.data ? `/api/patients/${id}/bodymap` : null);
  const [organ, setOrgan] = useState<string | null>(null);
  const [filter, setFilter] = useState<OrganFilter | null>(null);
  const [btg, setBtg] = useState(false);
  const [reason, setReason] = useState("");
  const toast = useToast();

  if (st.error && /restricted|break|403|access/i.test(st.error)) {
    return (
      <div className="mx-auto mt-16 max-w-xl text-center">
        <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="glass-hi p-10">
          <div className="mx-auto mb-5 grid h-16 w-16 place-items-center rounded-2xl border border-aur-rose/40 bg-aur-rose/10"><Lock className="text-aur-rose" /></div>
          <h2 className="h-display text-2xl font-semibold text-white">This record is restricted</h2>
          <p className="mt-2 text-[14px] leading-relaxed text-slate-400">{st.error}</p>
          <p className="mt-2 text-[13px] text-slate-500">In an emergency you can use break-glass. Your reason is recorded, the access expires automatically, and a privacy officer reviews it afterwards.</p>
          <div className="mt-6 flex justify-center gap-2"><Link href="/patients" className="btn"><ArrowLeft size={14} />Back</Link>{["physician", "nurse"].length && <button onClick={() => setBtg(true)} className="btn btn-danger"><Siren size={14} />Break glass</button>}</div>
        </motion.div>
        <Modal open={btg} onClose={() => setBtg(false)} title="Emergency access">
          <p className="mb-3 text-[13px] text-slate-400">Document a clinical reason (at least 15 characters). This action is written to the tamper-evident audit log.</p>
          <textarea className="input min-h-[96px]" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Unresponsive patient in ED, need medication history before intubation" />
          <div className="mt-4 flex justify-end gap-2"><button className="btn" onClick={() => setBtg(false)}>Cancel</button>
            <button className="btn btn-danger" onClick={async () => { try { await api("/api/access/break-glass", { body: { patient_id: id, reason } }); toast("ok", "Break-glass granted for 60 minutes. A privacy review was opened."); setBtg(false); st.reload(); } catch (e: any) { toast("err", e.message); } }}>Confirm and access</button></div>
        </Modal>
      </div>
    );
  }
  if (st.error) return <ErrorBox message={st.error} />;
  if (!st.data) return <Loading />;
  const p = st.data;
  const tabs: { id: T; label: string; icon: any }[] = [
    { id: "overview", label: "Overview", icon: <UserRound size={14} /> }, { id: "bodymap", label: "Body map", icon: <Boxes size={14} /> }, { id: "vitals", label: "Vitals and labs", icon: <FlaskConical size={14} /> }, { id: "timeline", label: "Timeline", icon: <Clock size={14} /> },
    { id: "notes", label: "Notes and coding", icon: <FileText size={14} /> }, { id: "copilot", label: "Differential copilot", icon: <BrainCircuit size={14} /> }, { id: "warning", label: "Early warning", icon: <Activity size={14} /> },
    { id: "medrec", label: "Medication safety", icon: <Pill size={14} /> }, { id: "handoff", label: "SBAR handoff", icon: <ClipboardList size={14} /> }, { id: "portal", label: "Patient portal", icon: <Globe2 size={14} /> },
  ];
  return (
    <>
      <Link href="/patients" className="mb-4 inline-flex items-center gap-1.5 text-[12.5px] text-slate-500 hover:text-slate-200"><ArrowLeft size={13} />All patients</Link>
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-hi relative mb-5 overflow-hidden p-6">
        <div className="absolute -right-10 -top-10 h-48 w-48 rounded-full bg-jade-500/20 blur-3xl" />
        <div className="relative flex flex-wrap items-center gap-6">
          <div className="grid h-16 w-16 place-items-center rounded-2xl bg-gradient-to-br from-jade-500 to-aur-sky text-[20px] font-bold text-ink-950">{p.name.split(" ").map((x: string) => x[0]).join("").slice(0, 2)}</div>
          <div className="min-w-[240px] flex-1">
            <h1 className="h-display text-[30px] font-semibold leading-tight text-white">{p.name}</h1>
            <div className="mt-1 text-[13px] text-slate-400">{p.age} years · {p.sex} · born {p.birth_date} · {p.mrn}</div>
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              <Badge color="#5cc8ff">ABHA {p.abha}</Badge><Badge color="#8b7bff">{p.abha_address}</Badge>
              {p.status === "inpatient" ? <Badge color="#34d6ae" dot>{p.ward} · {p.bed}</Badge> : <Badge>Outpatient</Badge>}
              {p.allergies_detail?.length > 0 && <Badge color="#ff7a90"><AlertOctagon size={11} />Allergy</Badge>}
              {p.access_reason === "break_glass" && <Badge color="#ff7a90" dot>Break-glass access</Badge>}
            </div>
          </div>
          <Link href={`/patients/${id}/discharge`} className="btn no-print self-start" data-testid="discharge-link"><FileOutput size={14} />Discharge summary</Link>
          {p.news2 && <div className="flex gap-5 text-right">
            <div><div className="eyebrow">NEWS2</div><div className="h-display text-[44px] font-semibold leading-none" style={{ color: news2Color(p.news2.score) }}>{p.news2.score}</div></div>
            <div><div className="eyebrow">ML tier</div><div className="h-display text-[44px] font-semibold capitalize leading-none" style={{ color: riskColor(p.ml_tier) }}>{p.ml_tier}</div></div>
          </div>}
        </div>
      </motion.div>
      {filter && (
        <div className="glass mb-4 flex items-center gap-3 border-jade-400/30 px-4 py-2.5 text-[13px]" data-testid="filter-banner">
          <span className="text-slate-300">Chart filtered to <b className="text-white">{filter.label}</b>. Problems, medications, vitals and labs outside this system are hidden.</span>
          <button className="btn ml-auto !py-1" onClick={() => { setFilter(null); }}><FilterX size={13} />Clear</button>
        </div>
      )}
      <Tabs tabs={tabs} value={tab} onChange={setTab} layout="patient" />
      <motion.div key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        {tab === "overview" && <Overview p={p} filter={filter} />}
        {tab === "bodymap" && (bm.data ? <BodyMapTab bm={bm.data} selected={organ} onSelect={setOrgan} onFilter={(o) => { setFilter(o ? makeFilter(o) : null); }} filterKey={filter?.key ?? null} /> : bm.error ? <ErrorBox message={bm.error} /> : <Loading />)}
        {tab === "vitals" && <VitalsLabs pid={id} filter={filter} />}
        {tab === "timeline" && <Timeline pid={id} />}
        {tab === "notes" && <NotesCoding pid={id} />}
        {tab === "copilot" && <Copilot pid={id} />}
        {tab === "warning" && <Warning pid={id} />}
        {tab === "medrec" && <MedRec pid={id} />}
        {tab === "handoff" && <Handoff pid={id} />}
        {tab === "portal" && <Portal pid={id} />}
      </motion.div>
    </>
  );
}
