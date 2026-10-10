"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { BadgeCheck, FileKey2, ShieldX, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Card, Disclaimer, PageHeader, useApi, useToast } from "@/components/ui";
import { cn } from "@/lib/utils";

const ST: Record<string, string> = { REQUESTED: "#f2c46d", GRANTED: "#34d6ae", DENIED: "#ff7a90", REVOKED: "#ff7a90", EXPIRED: "#8ea3c0" };
export default function Abdm() {
  const cat = useApi("/api/abdm/catalog");
  const list = useApi("/api/abdm/consent-requests");
  const pts = useApi("/api/patients");
  const toast = useToast();
  const [abha, setAbha] = useState("13-9986-9879-7302");
  const [addr, setAddr] = useState("joseph.thomas88@abdm");
  const [val, setVal] = useState<any>(null);
  const [purpose, setPurpose] = useState("CAREMGT");
  const [types, setTypes] = useState<string[]>(["Prescription", "DiagnosticReport"]);
  const [pid, setPid] = useState("pat-001");
  const [fetched, setFetched] = useState<any>(null);
  const patient = pts.data?.patients.find((p: any) => p.id === pid);
  const check = async () => setVal(await api(`/api/abdm/validate?abha=${encodeURIComponent(abha)}&address=${encodeURIComponent(addr)}`));
  const request = async () => {
    try { await api("/api/abdm/consent-requests", { body: { abha: patient?.abha ?? abha, requester: "Demo Insurer (HIU)", purpose, hi_types: types, date_from: "2020-01-01", date_to: "2030-12-31" } }); list.reload(); toast("ok", "Consent request created. The patient can now grant or deny."); } catch (e: any) { toast("err", e.message); }
  };
  const decide = async (id: string, grant: boolean) => { await api(`/api/abdm/consent-requests/${id}/decision`, { body: { grant } }); list.reload(); };
  const revoke = async (id: string) => { await api(`/api/abdm/consents/${id}/revoke`, { method: "POST" }); list.reload(); setFetched(null); };
  const fetchHi = async (id: string) => { try { setFetched(await api(`/api/abdm/health-information/${id}`)); } catch (e: any) { toast("err", e.message); setFetched(null); } };
  return (
    <>
      <PageHeader eyebrow="Interoperability" title="ABDM-aligned consent manager" sub="A mock of India’s Ayushman Bharat Digital Mission flow: validate an ABHA number, request consent for specific health-information types and a date range, let the patient grant or revoke, and release data only while consent is valid." />
      <div className="grid gap-5 xl:grid-cols-3">
        <Card title="1 · Validate identifiers" sub="Demo Verhoeff check digit catches typos">
          <label className="eyebrow">ABHA number</label><input className="input mb-3 mt-1 font-mono" value={abha} onChange={(e) => setAbha(e.target.value)} />
          <label className="eyebrow">ABHA address</label><input className="input mb-3 mt-1 font-mono" value={addr} onChange={(e) => setAddr(e.target.value)} />
          <button className="btn btn-primary" onClick={check}><BadgeCheck size={14} />Validate</button>
          {val && <div className="mt-3 space-y-2">{[["ABHA number", val.abha], ["ABHA address", val.address]].map(([l, v]: any) => <motion.div key={l} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className={cn("flex items-start gap-2 rounded-xl border p-3 text-[12.5px]", v.valid ? "border-jade-400/30 bg-jade-400/10 text-jade-300" : "border-aur-rose/30 bg-aur-rose/10 text-aur-rose")}>{v.valid ? <BadgeCheck size={15} /> : <XCircle size={15} />}<div><b>{l}</b><div className="opacity-80">{v.reason}</div></div></motion.div>)}</div>}
          <div className="mt-3 text-[11.5px] text-slate-500">Try changing the last digit to see a typo caught.</div>
        </Card>
        <Card title="2 · Request consent" sub="Acting as a health-information user (HIU)" className="xl:col-span-2">
          <div className="grid gap-4 md:grid-cols-2">
            <div><label className="eyebrow">Patient</label><select className="input mt-1" value={pid} onChange={(e) => setPid(e.target.value)}>{pts.data?.patients.map((p: any) => <option key={p.id} value={p.id}>{p.name} · {p.abha}</option>)}</select>
              <label className="eyebrow mt-3 block">Purpose</label><select className="input mt-1" value={purpose} onChange={(e) => setPurpose(e.target.value)}>{cat.data && Object.entries(cat.data.purposes).map(([k, v]: any) => <option key={k} value={k}>{k} · {v}</option>)}</select></div>
            <div><label className="eyebrow">Information types</label><div className="mt-1 flex flex-wrap gap-1.5">{cat.data?.hi_types.map((t: string) => <button key={t} onClick={() => setTypes((s) => (s.includes(t) ? s.filter((x) => x !== t) : [...s, t]))} className={cn("chip cursor-pointer !px-3 !py-1.5 text-[12px]", types.includes(t) && "!border-jade-400/50 !bg-jade-400/15 !text-jade-300")}>{t}</button>)}</div></div>
          </div>
          <div className="mt-4"><button className="btn btn-primary" onClick={request} disabled={!types.length}><FileKey2 size={14} />Create consent request</button></div>
        </Card>
      </div>
      <Card title="3 · Consent ledger" className="mt-5" sub="Grant, deny, revoke, then try to fetch. Data release is enforced server-side, not just in the UI.">
        <div className="space-y-3">{list.data?.items.map((c: any) => (
          <div key={c.id} className="rounded-2xl border hairline bg-white/[0.03] p-4">
            <div className="flex flex-wrap items-center gap-3"><Badge color={ST[c.status]} dot>{c.status}</Badge><span className="font-mono text-[12px] text-slate-400">{c.id.slice(0, 8)}</span><span className="text-[13px] text-slate-200">{c.requester}</span><Badge color="#5cc8ff">{c.purpose}</Badge><span className="text-[12px] text-slate-500">{c.hi_types.join(", ")} · {c.date_from} → {c.date_to}</span>
              <div className="ml-auto flex gap-2">{c.status === "REQUESTED" && <><button className="btn !py-1 text-[12px]" onClick={() => decide(c.id, true)}>Grant</button><button className="btn btn-danger !py-1 text-[12px]" onClick={() => decide(c.id, false)}>Deny</button></>}
                {c.status === "GRANTED" && <button className="btn btn-danger !py-1 text-[12px]" onClick={() => revoke(c.id)}><ShieldX size={12} />Revoke</button>}
                <button className="btn !py-1 text-[12px]" onClick={() => fetchHi(c.id)}>Fetch data</button></div></div>
          </div>))}
          {!list.data?.items.length && <div className="text-[13px] text-slate-500">No consent requests yet.</div>}</div>
        {fetched && <div className="mt-4 rounded-xl border border-jade-400/30 bg-jade-400/[0.07] p-4 text-[13px] text-jade-300">Released {fetched.bundle.total} resources of type {fetched.released_resource_types.join(", ")}.</div>}
        <div className="mt-4"><Disclaimer>Educational mock aligned to the ABDM consent and health-information-exchange concepts. It is not connected to any ABDM sandbox or production gateway and the ABHA scheme here is a demo check digit.</Disclaimer></div>
      </Card>
    </>
  );
}
