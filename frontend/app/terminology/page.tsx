"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { CheckCircle2, DownloadCloud, FileJson, Search, ShieldQuestion, Upload, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Card, Disclaimer, Gate, PageHeader, useApi, useToast } from "@/components/ui";
import { cn } from "@/lib/utils";

const SYSTEMS: [string, string, string][] = [["icd10", "ICD-10", "#8b7bff"], ["snomed", "SNOMED CT", "#5cc8ff"], ["loinc", "LOINC", "#34d6ae"], ["rxnorm", "RxNorm", "#f2c46d"]];

export default function Terminology() {
  const systems = useApi("/api/terminology/systems");
  const toast = useToast();
  const [sys, setSys] = useState("icd10");
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<any[]>([]);
  const [picked, setPicked] = useState<any>(null);
  const [v, setV] = useState({ system: "snomed", code: "38341003", display: "Hypertension" });
  const [vr, setVr] = useState<any>(null);
  const [bundle, setBundle] = useState<any>(null);
  const [report, setReport] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const file = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const t = setTimeout(() => { api(`/api/terminology/expand?system=${sys}&q=${encodeURIComponent(q)}&limit=24`).then((r) => setRows(r.concepts)).catch(() => setRows([])); }, 160);
    return () => clearTimeout(t);
  }, [sys, q]);

  const pick = async (r: any) => {
    try { setPicked(await api(`/api/terminology/lookup?system=${sys}&code=${encodeURIComponent(r.code)}`)); } catch (e: any) { toast("err", e.message); }
  };
  const validate = async () => {
    try { setVr(await api(`/api/terminology/validate?system=${v.system}&code=${encodeURIComponent(v.code)}&display=${encodeURIComponent(v.display)}`)); } catch (e: any) { toast("err", e.message); }
  };
  const loadSample = async () => { try { setBundle(await api("/api/import/synthea/sample")); setReport(null); } catch (e: any) { toast("err", e.message); } };
  const onFile = async (f?: File) => {
    if (!f) return;
    try { setBundle(JSON.parse(await f.text())); setReport(null); } catch { toast("err", "That file is not valid JSON."); }
  };
  const doImport = async () => {
    setBusy(true);
    try { const r = await api("/api/import/synthea", { body: bundle }); setReport(r); toast("ok", `Imported ${r.total} resources.`); } catch (e: any) { toast("err", e.message); }
    setBusy(false);
  };
  const counts = bundle ? (bundle.entry ?? []).reduce((a: Record<string, number>, e: any) => ({ ...a, [e.resource?.resourceType]: (a[e.resource?.resourceType] ?? 0) + 1 }), {}) : {};

  return (
    <>
      <PageHeader eyebrow="Interoperability" title="Terminology service and Synthea import"
        sub="Look up, validate and translate codes in the embedded ICD-10, SNOMED CT, LOINC and RxNorm subsets (the same operations FHIR exposes as $lookup, $validate-code and $translate), then import a Synthea patient into the chart store." />
      <Gate state={systems}>{(s) => (
        <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {s.systems.map((x: any) => { const meta = SYSTEMS.find((m) => m[0] === x.system)!; return <div key={x.system} className="glass p-4"><div className="eyebrow">{meta[1]}</div><div className="h-display mt-1 text-3xl font-semibold" style={{ color: meta[2] }}>{x.concepts}</div><div className="truncate text-[11px] text-slate-500">{x.uri}</div></div>; })}
        </div>
      )}</Gate>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card title="Browse and look up" sub="Type a code or a word. Click a concept to see its translations.">
          <div className="mb-3 flex flex-wrap gap-1.5" role="tablist">
            {SYSTEMS.map(([k, label, c]) => <button key={k} role="tab" aria-selected={sys === k} onClick={() => { setSys(k); setPicked(null); }} className={cn("chip transition", sys === k && "!text-white")} style={sys === k ? { background: `${c}33`, borderColor: c } : undefined}>{label}</button>)}
          </div>
          <div className="relative"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" /><input className="input !pl-9" placeholder="e.g. diabetes, E11, 2160-0, metformin" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search concepts" data-testid="term-search" /></div>
          <ul className="mt-3 max-h-[320px] space-y-1 overflow-auto pr-1" data-testid="term-results">
            {rows.map((r) => <li key={r.code}><button onClick={() => pick(r)} className={cn("flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-[13px] hover:bg-white/[0.06]", picked?.code === r.code && "bg-jade-400/10")}><span className="w-20 shrink-0 font-mono text-[12px] text-aur-sky">{r.code}</span><span className="text-slate-200">{r.display}</span></button></li>)}
            {!rows.length && <li className="px-3 py-4 text-[13px] text-slate-500">No concepts match.</li>}
          </ul>
          {picked && (
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mt-3 rounded-xl border hairline bg-white/[0.03] p-3 text-[13px]" data-testid="term-detail">
              <div className="font-medium text-white">{picked.display}</div>
              <div className="font-mono text-[11.5px] text-slate-500">{picked.system} | {picked.code}</div>
              {picked.translations.length > 0
                ? <div className="mt-2 text-slate-300">Equivalent to: {picked.translations.map((t: any) => <Badge key={t.code} color="#34d6ae">{t.system.includes("snomed") ? "SNOMED CT" : "ICD-10"} {t.code}</Badge>)}</div>
                : <div className="mt-2 text-slate-500">No curated translation for this code.</div>}
            </motion.div>
          )}
        </Card>

        <Card title="Validate a code" sub="Like ValueSet/$validate-code: is the code known, and does the display match?">
          <div className="grid gap-2 sm:grid-cols-[130px_1fr]">
            <select className="input" value={v.system} onChange={(e) => setV({ ...v, system: e.target.value })} aria-label="Code system">{SYSTEMS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
            <input className="input" value={v.code} onChange={(e) => setV({ ...v, code: e.target.value })} placeholder="Code" aria-label="Code" />
            <span className="hidden sm:block" />
            <input className="input" value={v.display} onChange={(e) => setV({ ...v, display: e.target.value })} placeholder="Display text to check (optional)" aria-label="Display" />
          </div>
          <button className="btn btn-primary mt-3" onClick={validate} data-testid="validate-btn"><ShieldQuestion size={14} />Validate</button>
          {vr && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className={cn("mt-3 flex items-start gap-2.5 rounded-xl border p-3 text-[13px]", vr.result ? "border-jade-400/30 bg-jade-400/10 text-jade-300" : "border-aur-rose/30 bg-aur-rose/10 text-aur-rose")} data-testid="validate-result">
              {vr.result ? <CheckCircle2 size={16} className="mt-0.5" /> : <XCircle size={16} className="mt-0.5" />}
              <div><div className="font-medium">{vr.result ? "Valid code" : "Unknown code"}</div><div className="text-[12px] opacity-90">{vr.message}{vr.display && vr.message === "OK" ? ` · ${vr.display}` : ""}</div></div>
            </motion.div>
          )}
          <div className="mt-4"><Disclaimer>These are hand-curated subsets so the platform runs offline. They are not the licensed releases; verify against the official SNOMED CT, LOINC, ICD-10 and RxNorm distributions before real use.</Disclaimer></div>
        </Card>
      </div>

      <Card className="mt-5" title="Import from Synthea" sub="Synthea writes one FHIR bundle per synthetic patient. Load the built-in sample or upload your own bundle (from synthea/output/fhir)." right={<Badge color="#8b7bff">Synthea FHIR R4</Badge>}>
        <div className="flex flex-wrap gap-2">
          <button className="btn" onClick={loadSample} data-testid="load-sample"><DownloadCloud size={14} />Load sample bundle</button>
          <button className="btn" onClick={() => file.current?.click()}><Upload size={14} />Upload bundle (.json)</button>
          <input ref={file} type="file" accept="application/json,.json" className="hidden" onChange={(e) => onFile(e.target.files?.[0])} aria-label="Upload Synthea bundle" />
          <button className="btn btn-primary" onClick={doImport} disabled={!bundle || busy} data-testid="import-btn"><FileJson size={14} />Import into chart store</button>
        </div>
        {bundle && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5" data-testid="bundle-summary"><span className="eyebrow mr-1">Bundle contents</span>{Object.entries(counts).map(([k, n]: any) => <Badge key={k} color="#5cc8ff">{k} × {n}</Badge>)}</div>
        )}
        {report && (
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mt-4 rounded-xl border border-jade-400/30 bg-jade-400/10 p-4 text-[13px]" data-testid="import-report">
            <div className="font-medium text-white">Imported {report.total} resources</div>
            <div className="mt-2 flex flex-wrap gap-1.5">{Object.entries(report.imported).map(([k, n]: any) => <Badge key={k} color="#34d6ae">{k} × {n}</Badge>)}</div>
            {Object.keys(report.skipped).length > 0 && <div className="mt-2 text-slate-400">Skipped (unsupported types): {Object.entries(report.skipped).map(([k, n]) => `${k} × ${n}`).join(", ")}</div>}
            <div className="mt-2 text-slate-400">Mapped onto platform codes: {report.mapped.conditions} condition(s), {report.mapped.observations} observation(s).</div>
            <Link href="/patients" className="btn btn-primary mt-3 !py-1.5">Open patients</Link>
          </motion.div>
        )}
        <p className="mt-3 text-[12px] text-slate-500">Imported patients are re-keyed, tagged <code>synthea</code>, given a synthetic ABHA number and added to Dr. Rao&apos;s panel. Terminology aliases (for example SNOMED 59621000 for hypertension) are mapped to the codes the clinical modules understand. To import a whole folder from the command line: <code>asclepius import-synthea ./output/fhir</code>.</p>
      </Card>
    </>
  );
}
