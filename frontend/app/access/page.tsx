"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { CheckCircle2, Link2, ShieldAlert, ShieldCheck, Siren } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Card, Disclaimer, PageHeader, Table, Tabs, useApi, useToast } from "@/components/ui";
import { fmtTime } from "@/lib/utils";

type T = "audit" | "reviews" | "grants";
export default function Access() {
  const [tab, setTab] = useState<T>("audit");
  const audit = useApi("/api/audit");
  const verify = useApi("/api/audit/verify");
  const reviews = useApi("/api/access/reviews");
  const grants = useApi("/api/access/grants");
  const toast = useToast();
  const [only, setOnly] = useState(false);
  const decide = async (id: string, decision: string) => { try { await api(`/api/access/reviews/${id}`, { body: { decision, note: decision === "justified" ? "Reason consistent with emergency care." : "Reason not consistent with care relationship." } }); reviews.reload(); toast("ok", `Marked ${decision}.`); } catch (e: any) { toast("err", e.message); } };
  const rows = (audit.data?.entries ?? []).filter((e: any) => !only || e.break_glass);
  return (
    <>
      <PageHeader eyebrow="Trust and operations" title="Access and audit" sub="Every read of a patient record is authorised by role, care relationship and consent, and recorded in a SHA-256 hash chain. Altering any past entry breaks every hash after it."
        actions={verify.data && <Badge color={verify.data.valid ? "#34d6ae" : "#ff7a90"} dot>{verify.data.valid ? `Chain intact · ${verify.data.entries} entries` : "Chain BROKEN"}</Badge>} />
      <Tabs tabs={[{ id: "audit", label: "Audit log" }, { id: "reviews", label: "Break-glass reviews" }, { id: "grants", label: "My active grants" }]} value={tab} onChange={setTab} layout="acc" />
      {tab === "audit" && (
        <Card title="Tamper-evident log" sub="Newest first. Each row’s hash covers the previous row’s hash." right={<button className={`chip cursor-pointer ${only ? "!border-aur-rose/50 !text-aur-rose" : ""}`} onClick={() => setOnly((v) => !v)}><Siren size={11} />Break-glass only</button>} pad={false}>
          {audit.error ? <div className="p-5 text-[13px] text-slate-400">{audit.error}. Sign in as <b>Nandini Menon</b> (privacy officer) to read the audit log.</div> : (
            <Table head={["#", "Time", "Actor", "Action", "Patient", "Outcome", "Hash"]}>{rows.slice(0, 60).map((e: any) => (
              <tr key={e.seq} className={e.break_glass ? "bg-aur-rose/[0.05]" : ""}><td className="td font-mono text-[11px] text-slate-500">{e.seq}</td><td className="td whitespace-nowrap text-[12px] text-slate-400">{fmtTime(e.ts)}</td>
                <td className="td"><div className="text-slate-100">{e.actor}</div><div className="text-[11px] text-slate-500">{e.role}</div></td>
                <td className="td"><span className="font-mono text-[12px] text-aur-sky">{e.action}</span>{e.detail && <div className="max-w-[300px] truncate text-[11px] text-slate-500">{e.detail}</div>}</td>
                <td className="td font-mono text-[12px] text-slate-400">{e.patient ?? "-"}</td><td className="td"><Badge color={e.outcome === "ok" ? "#34d6ae" : "#ff7a90"}>{e.outcome}</Badge>{e.break_glass ? <Badge color="#ff7a90" className="ml-1">BTG</Badge> : null}</td>
                <td className="td font-mono text-[10.5px] text-slate-600"><Link2 size={10} className="mr-1 inline" />{e.hash.slice(0, 10)}…</td></tr>))}</Table>)}
        </Card>)}
      {tab === "reviews" && (
        <div className="space-y-4">
          {reviews.error && <Card><div className="text-[13px] text-slate-400">{reviews.error}. Sign in as the privacy officer to review break-glass events.</div></Card>}
          {reviews.data?.reviews.map((r: any) => (
            <Card key={r.id}><div className="flex flex-wrap items-center gap-3"><Badge color={r.status === "open" ? "#ffb454" : r.status === "justified" ? "#34d6ae" : "#ff7a90"} dot>{r.status}</Badge><span className="text-[14px] font-medium text-white">{r.name}</span><span className="font-mono text-[12px] text-slate-500">→ {r.patient}</span><span className="text-[12px] text-slate-500">{fmtTime(r.granted_at)}</span>
              {r.status === "open" && <div className="ml-auto flex gap-2"><button className="btn !py-1 text-[12px]" onClick={() => decide(r.id, "justified")}><CheckCircle2 size={13} className="text-jade-400" />Justified</button><button className="btn btn-danger !py-1 text-[12px]" onClick={() => decide(r.id, "inappropriate")}><ShieldAlert size={13} />Inappropriate</button></div>}</div>
              <p className="mt-2 text-[13px] italic text-slate-300">“{r.reason}”</p>{r.note && <p className="mt-1 text-[12px] text-slate-500">Reviewer note: {r.note}</p>}</Card>))}
          {reviews.data && !reviews.data.reviews.length && <Card><div className="text-[13px] text-slate-400">No break-glass events yet. Open a restricted patient (a lock icon in the patient list) as a physician and use break-glass to create one.</div></Card>}
        </div>)}
      {tab === "grants" && (
        <Card title="Your active emergency grants">{grants.data?.grants.length ? grants.data.grants.map((g: any, i: number) => <div key={i} className="flex justify-between rounded-xl bg-white/[0.04] p-3 text-[13px]"><span className="font-mono">{g.patient}</span><span className="text-slate-400">expires {fmtTime(g.expires)}</span></div>) : <div className="text-[13px] text-slate-400">None. Grants expire automatically after the configured window.</div>}</Card>)}
      <div className="mt-5"><Disclaimer>Demonstration of access-control patterns. In production this would integrate with an identity provider, enforce MFA, and ship audit records to write-once storage.</Disclaimer></div>
    </>
  );
}
