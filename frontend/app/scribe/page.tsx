"use client";
import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, FileSignature, Mic, Sparkles, Stethoscope, Wand2 } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Card, Disclaimer, PageHeader, useApi, useToast } from "@/components/ui";
import { cn } from "@/lib/utils";

const RT_COLOR: Record<string, string> = { Condition: "#34d6ae", Observation: "#5cc8ff", AllergyIntolerance: "#ff7a90", ServiceRequest: "#f2c46d", MedicationRequest: "#8b7bff", Composition: "#ffb454" };

export default function Scribe() {
  const demos = useApi("/api/scribe/demos");
  const pts = useApi("/api/patients");
  const toast = useToast();
  const [pid, setPid] = useState("");
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [approve, setApprove] = useState<Record<string, boolean>>({});
  const [signed, setSigned] = useState<any>(null);
  const [rec, setRec] = useState(false);

  useEffect(() => { if (demos.data && !text) setText(demos.data.demos[0].transcript); }, [demos.data]); // eslint-disable-line
  useEffect(() => { if (pts.data && !pid) setPid(pts.data.patients[0]?.id ?? ""); }, [pts.data]); // eslint-disable-line

  const run = async () => {
    setBusy(true); setSigned(null);
    try {
      const d = await api("/api/scribe/draft", { body: { transcript: text, patient_id: pid || null } });
      setDraft(d); setApprove(Object.fromEntries(Array.from(new Set<string>(d.fhir_draft.map((r: any) => r.resourceType))).map((k) => [k, true])));
    } catch (e: any) { toast("err", e.message); }
    setBusy(false);
  };
  const sign = async () => {
    try { const r = await api("/api/scribe/sign", { body: { patient_id: pid, transcript: text, approve: Object.keys(approve).filter((k) => approve[k]) } }); setSigned(r); toast("ok", `Signed. ${r.count} resources written to the chart.`); } catch (e: any) { toast("err", e.message); }
  };
  const dictate = () => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return toast("info", "Browser speech recognition is not available here. Paste a transcript instead.");
    const r = new SR(); r.continuous = true; r.interimResults = false; r.lang = "en-IN";
    r.onresult = (e: any) => setText((t) => `${t}\n${Array.from(e.results).slice(-1).map((x: any) => x[0].transcript).join(" ")}`);
    r.onend = () => setRec(false); setRec(true); r.start();
  };
  const types = useMemo(() => Object.keys(approve), [approve]);
  const N = draft?.note;
  return (
    <>
      <PageHeader eyebrow="Clinical" title="Ambient scribe" sub="Paste or dictate a consultation. Asclepius drafts a structured SOAP note with quotes as evidence, and a draft FHIR bundle that is only written to the chart after a physician approves and signs." />
      <div className="grid gap-5 xl:grid-cols-[1fr_1.35fr]">
        <div className="space-y-5">
          <Card title="Consultation transcript" right={<button className={cn("btn !py-1.5", rec && "btn-danger")} onClick={dictate}><Mic size={14} className={rec ? "animate-pulse" : ""} />{rec ? "Listening…" : "Dictate"}</button>}>
            <div className="mb-3 flex flex-wrap gap-1.5">{demos.data?.demos.map((d: any) => <button key={d.id} className="chip cursor-pointer hover:!border-jade-400/50" onClick={() => { setText(d.transcript); setDraft(null); }}>{d.title}</button>)}</div>
            <textarea className="input min-h-[300px] font-mono text-[12.5px] leading-relaxed" value={text} onChange={(e) => setText(e.target.value)} />
            <div className="mt-3 flex items-center gap-3">
              <select className="input !w-auto" value={pid} onChange={(e) => setPid(e.target.value)}>{pts.data?.patients.map((p: any) => <option key={p.id} value={p.id}>{p.name} · {p.mrn}</option>)}</select>
              <button className="btn btn-primary" onClick={run} disabled={busy || text.length < 5}><Wand2 size={14} />{busy ? "Drafting…" : "Draft note"}</button>
            </div>
          </Card>
          {draft && <Card title="Conversation">
            <div className="max-h-[360px] space-y-2 overflow-auto pr-1">{draft.utterances.map((u: any, i: number) => <div key={i} className={cn("max-w-[88%] rounded-2xl px-3.5 py-2 text-[13px] leading-relaxed", u.speaker === "doctor" ? "bg-jade-400/10 text-slate-200" : "ml-auto bg-white/[0.06] text-slate-300")}><div className="eyebrow !text-[9px] mb-0.5">{u.speaker}</div>{u.text}</div>)}</div>
          </Card>}
        </div>
        <div className="space-y-5">
          <AnimatePresence mode="wait">
          {!draft ? (
            <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}><Card className="grid min-h-[420px] place-items-center text-center"><div><div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-2xl border border-jade-400/30 bg-jade-400/10"><Sparkles className="text-jade-300" /></div><div className="h-display text-xl text-white">Your draft appears here</div><p className="mx-auto mt-1 max-w-sm text-[13px] text-slate-400">Choose a sample visit and press Draft note.</p></div></Card></motion.div>
          ) : (
            <motion.div key="draft" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
              <Card title="SOAP note" right={<Badge color="#f2c46d" dot>{draft.status}</Badge>} hi>
                <div className="grid gap-4 md:grid-cols-2">
                  <div><div className="eyebrow mb-1.5 text-jade-300">Subjective</div><p className="text-[13px] leading-relaxed text-slate-200">{N.subjective.hpi}</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">{N.subjective.positives.map((p: any) => <Badge key={p.key} color="#34d6ae" className="cursor-help" >{p.display}{p.duration ? ` · ${p.duration}` : ""}</Badge>)}{N.subjective.negatives.map((p: any) => <Badge key={p.key} color="#ff7a90"><s>{p.display}</s></Badge>)}</div>
                    {[["History", N.subjective.history], ["Medications", N.subjective.medications], ["Allergies", N.subjective.allergies]].map(([k, v]: any) => v?.length ? <div key={k} className="mt-2 text-[12.5px] text-slate-400"><span className="text-slate-500">{k}: </span>{v.map((x: any) => x.display ?? x.text ?? x).join(", ")}</div> : null)}</div>
                  <div><div className="eyebrow mb-1.5 text-aur-sky">Objective</div><div className="space-y-1 text-[13px] text-slate-300">{Object.entries(N.objective.vitals ?? {}).map(([k, v]: any) => <div key={k} className="flex justify-between rounded-lg bg-white/[0.04] px-2.5 py-1"><span className="uppercase text-slate-500">{k}</span><span>{String(v)}</span></div>)}{(N.objective.exam ?? []).map((e: any, i: number) => <div key={i} className="text-[12.5px] text-slate-400">{e.text ?? String(e)}</div>)}</div></div>
                  <div><div className="eyebrow mb-1.5 text-aur-gold">Assessment</div>{N.assessment.map((a: any) => <div key={a.key} className="rounded-xl bg-aur-gold/[0.07] p-2.5 text-[13px]"><div className="text-slate-100">{a.display} <Badge color="#f2c46d">{a.certainty}</Badge></div><div className="mt-1 font-mono text-[11px] text-slate-400">ICD-10 {a.icd10} · SNOMED {a.snomed}</div><div className="mt-1 text-[11.5px] italic text-slate-500">“{a.quote}”</div></div>)}</div>
                  <div><div className="eyebrow mb-1.5 text-aur-violet">Plan</div><ul className="space-y-1.5">{N.plan.map((p: any, i: number) => <li key={i} className="flex items-start gap-2 text-[13px] text-slate-300"><Check size={13} className="mt-1 text-jade-400" /><span>{p.text} <Badge color={RT_COLOR[p.type === "order" ? "ServiceRequest" : p.type === "medication" ? "MedicationRequest" : "Composition"]}>{p.type}</Badge></span></li>)}</ul></div>
                </div>
              </Card>
              {draft.review_flags.length > 0 && <Card title="Needs your attention">{draft.review_flags.map((f: any, i: number) => <div key={i} className="text-[13px] text-aur-amber">• {f.text ?? String(f)}</div>)}</Card>}
              <Card title="Draft FHIR resources" sub="Tick what you approve. Every draft resource is tagged ai-draft until signed.">
                <div className="mb-3 flex flex-wrap gap-2">{types.map((t) => <button key={t} onClick={() => setApprove((a) => ({ ...a, [t]: !a[t] }))} className={cn("chip cursor-pointer !px-3 !py-1.5 text-[12px]", approve[t] ? "" : "opacity-40")} style={{ color: RT_COLOR[t], borderColor: `${RT_COLOR[t]}55`, background: approve[t] ? `${RT_COLOR[t]}18` : undefined }}>{approve[t] ? <Check size={12} /> : null}{t} · {draft.fhir_draft.filter((r: any) => r.resourceType === t).length}</button>)}</div>
                <pre className="max-h-[260px] overflow-auto rounded-xl bg-ink-950/70 p-3 font-mono text-[11px] leading-relaxed text-slate-400">{JSON.stringify(draft.fhir_draft.filter((r: any) => approve[r.resourceType]).slice(0, 4), null, 2)}</pre>
                <div className="mt-4 flex items-center gap-3"><button className="btn btn-primary" onClick={sign} disabled={!!signed}><FileSignature size={14} />Sign and write to chart</button>{signed && <Badge color="#34d6ae" dot>{signed.count} resources saved</Badge>}</div>
                <div className="mt-3"><Disclaimer>{draft.disclaimer}</Disclaimer></div>
              </Card>
            </motion.div>
          )}
          </AnimatePresence>
        </div>
      </div>
    </>
  );
}
