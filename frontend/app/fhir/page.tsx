"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { KeyRound, Play, Search } from "lucide-react";
import { getToken } from "@/lib/api";
import { Badge, Card, PageHeader, useApi } from "@/components/ui";
import { cn } from "@/lib/utils";

const TYPES = ["Patient", "Observation", "Condition", "MedicationRequest", "Encounter", "DocumentReference", "AllergyIntolerance", "ServiceRequest", "Composition", "Practitioner", "Location"];

function Json({ v }: { v: any }) {
  const html = JSON.stringify(v, null, 2).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, (m) => {
      let c = "#f2c46d"; if (/^"/.test(m)) c = /:$/.test(m) ? "#5cc8ff" : "#6ee7c8"; else if (/true|false/.test(m)) c = "#ff7a90"; else if (/null/.test(m)) c = "#8ea3c0";
      return `<span style="color:${c}">${m}</span>`;
    });
  return <pre className="max-h-[520px] overflow-auto rounded-xl bg-ink-950/80 p-4 font-mono text-[11.5px] leading-relaxed text-slate-400" dangerouslySetInnerHTML={{ __html: html }} />;
}

const b64url = (buf: ArrayBuffer) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

export default function FhirExplorer() {
  const [type, setType] = useState("Patient");
  const [patient, setPatient] = useState("");
  const [count, setCount] = useState("5");
  const [extra, setExtra] = useState("");
  const [out, setOut] = useState<any>(null);
  const [url, setUrl] = useState("");
  const [ms, setMs] = useState<number | null>(null);
  const [status, setStatus] = useState<number | null>(null);
  const [smart, setSmart] = useState<{ step: string; data: any }[]>([]);
  const [busy, setBusy] = useState(false);
  const cfg = useApi("/.well-known/smart-configuration");

  const call = async (u: string, token?: string) => {
    const t0 = performance.now();
    const r = await fetch(u, { headers: { Authorization: `Bearer ${token ?? getToken()}`, Accept: "application/fhir+json" } });
    const j = await r.json().catch(() => ({})); setMs(Math.round(performance.now() - t0)); setStatus(r.status); setUrl(u); setOut(j); return j;
  };
  const search = () => { const p = new URLSearchParams(); if (patient) p.set(type === "Patient" ? "_id" : "patient", patient); if (count) p.set("_count", count); extra.split("&").filter(Boolean).forEach((kv) => { const [k, v] = kv.split("="); if (k && v) p.set(k, v); }); return call(`/fhir/${type}?${p.toString()}`); };

  const runSmart = async () => {
    setBusy(true); setSmart([]);
    const log = (step: string, data: any) => setSmart((s) => [...s, { step, data }]);
    try {
      const bytes = crypto.getRandomValues(new Uint8Array(48)); const verifier = b64url(bytes.buffer);
      const challenge = b64url(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier)));
      log("1. Generate PKCE verifier and S256 challenge", { code_verifier: verifier.slice(0, 20) + "…", code_challenge: challenge });
      const redirect = `${location.origin}/fhir`;
      const q = new URLSearchParams({ response_type: "code", client_id: "demo-smart-app", redirect_uri: redirect, scope: "launch/patient patient/Patient.read patient/Observation.read openid", state: "xyz", code_challenge: challenge, code_challenge_method: "S256", login_hint: "dr.rao", launch_patient: "pat-001" });
      const a = await fetch(`/api/smart/authorize?${q}`, { headers: { Accept: "application/json" } }).then((r) => r.json());
      log("2. Authorization endpoint returns a one-time code", { code: a.code.slice(0, 10) + "…", state: a.state });
      const form = new URLSearchParams({ grant_type: "authorization_code", code: a.code, code_verifier: verifier, client_id: "demo-smart-app", redirect_uri: redirect });
      const t = await fetch("/api/smart/token", { method: "POST", body: form }).then((r) => r.json());
      log("3. Token endpoint verifies SHA256(verifier) = challenge", { token_type: t.token_type, scope: t.scope, patient: t.patient, expires_in: t.expires_in });
      const bad = await fetch("/fhir/Patient/pat-002", { headers: { Authorization: `Bearer ${t.access_token}` } });
      const ok = await fetch(`/fhir/Patient/${t.patient}`, { headers: { Authorization: `Bearer ${t.access_token}` } });
      log("4. FHIR call inside the launch context", { "GET Patient/pat-001": ok.status, "GET Patient/pat-002 (other patient)": bad.status, "GET Condition (scope not granted)": (await fetch("/fhir/Condition", { headers: { Authorization: `Bearer ${t.access_token}` } })).status });
    } catch (e: any) { log("Error", { message: String(e) }); }
    setBusy(false);
  };

  return (
    <>
      <PageHeader eyebrow="Interoperability" title="FHIR R4 explorer" sub="Query the standards-compliant API directly, read the CapabilityStatement, and run a real SMART App Launch (authorization code with PKCE S256) in your browser." />
      <div className="grid gap-5 xl:grid-cols-[1.3fr_1fr]">
        <div className="space-y-5">
          <Card title="Search" sub="GET /fhir/{type}?…">
            <div className="flex flex-wrap gap-1.5">{TYPES.map((t) => <button key={t} onClick={() => setType(t)} className={cn("chip cursor-pointer !px-3 !py-1.5 text-[12px]", type === t && "!border-jade-400/50 !bg-jade-400/15 !text-jade-300")}>{t}</button>)}</div>
            <div className="mt-3 grid gap-3 md:grid-cols-3"><input className="input font-mono" placeholder={type === "Patient" ? "_id (e.g. pat-001)" : "patient (e.g. pat-001)"} value={patient} onChange={(e) => setPatient(e.target.value)} /><input className="input font-mono" placeholder="_count" value={count} onChange={(e) => setCount(e.target.value)} /><input className="input font-mono" placeholder="extra: category=vital-signs&code=8867-4" value={extra} onChange={(e) => setExtra(e.target.value)} /></div>
            <div className="mt-3 flex flex-wrap gap-2"><button className="btn btn-primary" onClick={search}><Search size={14} />Search</button><button className="btn" onClick={() => call("/fhir/metadata")}>CapabilityStatement</button><button className="btn" onClick={() => call(`/fhir/Patient/${patient || "pat-001"}/$everything`)}>$everything</button></div>
          </Card>
          {out && <Card title={<span className="flex items-center gap-2"><Badge color={status && status < 300 ? "#34d6ae" : "#ff7a90"}>{status}</Badge><span className="font-mono text-[12px] font-normal text-slate-400">{url}</span></span>} right={<span className="text-[12px] text-slate-500">{ms} ms{out.total !== undefined ? ` · total ${out.total}` : ""}</span>}><Json v={out} /></Card>}
        </div>
        <div className="space-y-5">
          <Card title="SMART App Launch" sub="Standalone launch, public client, PKCE S256" hi right={<button className="btn btn-primary !py-1.5" onClick={runSmart} disabled={busy}><Play size={13} />Run flow</button>}>
            <div className="space-y-2.5">{smart.map((s, i) => <motion.div key={i} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} className="rounded-xl bg-white/[0.04] p-3"><div className="mb-1 text-[12.5px] font-medium text-jade-300">{s.step}</div><pre className="overflow-x-auto font-mono text-[11px] text-slate-400">{JSON.stringify(s.data, null, 1)}</pre></motion.div>)}
              {!smart.length && <div className="flex items-center gap-2 text-[13px] text-slate-500"><KeyRound size={14} />Press Run flow to perform the four steps.</div>}</div>
          </Card>
          <Card title="/.well-known/smart-configuration">{cfg.data && <Json v={cfg.data} />}</Card>
        </div>
      </div>
    </>
  );
}
