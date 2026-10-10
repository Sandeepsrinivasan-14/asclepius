"use client";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Activity, Check, ClipboardCopy, FlaskConical, Pencil, Pill, ShieldCheck, ShieldX, X, FileText, Stethoscope, AlertTriangle } from "lucide-react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
import { api } from "@/lib/api";
import { Badge, Card, Disclaimer, Gate, Loading, Ring, Table, useApi, useToast } from "@/components/ui";
import { cn, fmtTime, pct, riskColor } from "@/lib/utils";

const sev: Record<string, string> = { contraindicated: "#ff7a90", major: "#ffb454", moderate: "#f2c46d", info: "#5cc8ff" };
const ASSERT: Record<string, string> = { present: "#34d6ae", absent: "#ff7a90", possible: "#f2c46d", historical: "#8b7bff", family: "#5cc8ff" };

/* ============ Timeline ============ */
const TL: Record<string, [any, string]> = { lab: [FlaskConical, "#5cc8ff"], note: [FileText, "#f2c46d"], medication: [Pill, "#8b7bff"], condition: [Stethoscope, "#34d6ae"], vital: [Activity, "#ff7a90"], encounter: [Stethoscope, "#34d6ae"] };
export function Timeline({ pid }: { pid: string }) {
  const st = useApi(`/api/patients/${pid}/timeline`);
  const [f, setF] = useState("all");
  return <Gate state={st}>{(d) => {
    const types = ["all", ...Array.from(new Set<string>(d.events.map((e: any) => e.type)))];
    const ev = d.events.filter((e: any) => f === "all" || e.type === f);
    return (
      <Card title="Clinical timeline" sub="Everything on the chart in one chronological stream" right={<div className="flex gap-1.5">{types.map((t) => <button key={t} onClick={() => setF(t)} className={cn("chip cursor-pointer capitalize", f === t && "!border-jade-400/50 !bg-jade-400/15 !text-jade-300")}>{t}</button>)}</div>}>
        <div className="relative ml-3 border-l hairline pl-6">
          {ev.slice(0, 80).map((e: any, i: number) => { const [Ico, c] = TL[e.type] ?? [Activity, "#8ea3c0"]; return (
            <motion.div key={i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: Math.min(i, 20) * 0.02 }} className="relative pb-4">
              <span className="absolute -left-[37px] grid h-6 w-6 place-items-center rounded-full border bg-ink-900" style={{ borderColor: `${c}66` }}><Ico size={12} style={{ color: c }} /></span>
              <div className="flex flex-wrap items-baseline gap-2"><span className="text-[13px] text-slate-100">{e.title}</span>{e.detail && <Badge color={e.detail === "high" || e.detail === "low" ? "#ffb454" : "#8ea3c0"}>{e.detail}</Badge>}</div>
              <div className="text-[11px] text-slate-500">{fmtTime(e.t)} · {e.type}</div>
            </motion.div>); })}
        </div>
      </Card>
    );
  }}</Gate>;
}

/* ============ Notes + coder ============ */
function Highlighted({ text, mentions }: { text: string; mentions: any[] }) {
  const parts: any[] = []; let cur = 0;
  [...mentions].sort((a, b) => a.offset - b.offset).forEach((m, i) => {
    if (m.offset < cur) return;
    parts.push(<span key={`t${i}`}>{text.slice(cur, m.offset)}</span>);
    const c = ASSERT[m.assertion] ?? "#8ea3c0";
    parts.push(<mark key={`m${i}`} title={`${m.display} · ${m.assertion} · ${(m.confidence * 100).toFixed(0)}%`} className="rounded px-1 py-0.5 text-slate-100" style={{ background: `${c}26`, boxShadow: `inset 0 -2px 0 ${c}`, textDecoration: m.assertion === "absent" ? "line-through" : undefined }}>{text.slice(m.offset, m.offset + m.text.length)}</mark>);
    cur = m.offset + m.text.length;
  });
  parts.push(<span key="end">{text.slice(cur)}</span>);
  return <p className="whitespace-pre-wrap text-[13.5px] leading-[1.9] text-slate-300">{parts}</p>;
}
export function NotesCoding({ pid }: { pid: string }) {
  const st = useApi(`/api/patients/${pid}/coding`);
  const toast = useToast();
  const [custom, setCustom] = useState("No fever. Possible pneumonia. Patient denies chest pain but reports productive cough and breathlessness on exertion. Father had diabetes.");
  const [res, setRes] = useState<any>(null);
  const run = async () => setRes(await api("/api/coding/analyze", { body: { text: custom } }));
  return (
    <div className="space-y-5">
      <Disclaimer>The coder understands negation (struck through), uncertainty, history and family history, and sends low-confidence codes to a human review queue instead of guessing. Hover a highlight for its confidence.</Disclaimer>
      <Gate state={st}>{(d) => d.notes.map((n: any, i: number) => (
        <Card key={n.note.id} title={n.note.title} sub={fmtTime(n.note.date)} delay={i * 0.05} right={<div className="flex gap-1.5">{Object.entries(ASSERT).slice(0, 4).map(([k, c]) => <Badge key={k} color={c}>{k}</Badge>)}</div>}>
          <Highlighted text={n.note.text} mentions={n.mentions} />
          <div className="mt-4"><Table head={["Concept", "Assertion", "ICD-10", "SNOMED CT", "Confidence", "Review"]}>
            {n.mentions.map((m: any, j: number) => (
              <tr key={j}><td className="td"><div className="text-slate-100">{m.display}</div><div className="text-[11px] text-slate-500">“{m.text}” · {m.kind}</div></td>
                <td className="td"><Badge color={ASSERT[m.assertion] ?? "#8ea3c0"} dot>{m.assertion}</Badge></td>
                <td className="td font-mono text-[12px] text-aur-gold">{m.codes["ICD-10"] ?? "-"}</td><td className="td font-mono text-[12px] text-aur-sky">{m.codes["SNOMED CT"] ?? "-"}</td>
                <td className="td w-40"><div className="h-1.5 overflow-hidden rounded-full bg-white/10"><motion.div initial={{ width: 0 }} animate={{ width: `${m.confidence * 100}%` }} className="h-full rounded-full" style={{ background: m.confidence < 0.7 ? "#ffb454" : "#34d6ae" }} /></div><div className="mt-1 text-[11px] text-slate-500">{(m.confidence * 100).toFixed(0)}%</div></td>
                <td className="td">{m.needs_review ? <Badge color="#ffb454">Needs review</Badge> : <Check size={14} className="text-jade-400" />}</td></tr>
            ))}</Table></div>
        </Card>
      ))}</Gate>
      <Card title="Try the coder yourself" sub="Paste any synthetic text">
        <textarea className="input min-h-[96px]" value={custom} onChange={(e) => setCustom(e.target.value)} />
        <div className="mt-3"><button className="btn btn-primary" onClick={() => run().catch((e) => toast("err", e.message))}>Analyse text</button></div>
        {res && <div className="mt-4"><Highlighted text={custom} mentions={res.mentions} /></div>}
      </Card>
    </div>
  );
}

/* ============ Differential copilot ============ */
function Cited({ text, onPick }: { text: string; onPick: (id: string) => void }) {
  return <>{text.split(/(\[E\d+\])/g).map((t, i) => /^\[E\d+\]$/.test(t) ? <button key={i} onClick={() => onPick(t.slice(1, -1))} className="mx-0.5 rounded-md border border-aur-sky/40 bg-aur-sky/10 px-1 font-mono text-[10.5px] text-aur-sky hover:bg-aur-sky/25">{t.slice(1, -1)}</button> : <span key={i}>{t}</span>)}</>;
}
const CHK: Record<string, string> = { Pass: "#34d6ae", Warn: "#ffb454", Fail: "#ff7a90" };
export function Copilot({ pid }: { pid: string }) {
  const st = useApi(`/api/patients/${pid}/copilot`);
  const toast = useToast();
  const [open, setOpen] = useState<string | null>(null);
  const [hl, setHl] = useState<string | null>(null);
  const [tamper, setTamper] = useState("The patient is 240 years old and definitely has sepsis; give vancomycin 5 g now [E99].");
  const [vres, setVres] = useState<any>(null);
  const [acted, setActed] = useState<string | null>(null);
  const act = async (action: string) => { await api("/api/governance/feedback", { body: { model: "copilot", patient_id: pid, action, reason: action === "accepted" ? null : "Reviewed by clinician" } }); setActed(action); toast("ok", `Recorded: ${action}. This feeds the override-rate dashboard.`); };
  return <Gate state={st}>{(d) => {
    const top = d.differential[0]?.share ?? 1;
    return (
      <div className="grid gap-5 xl:grid-cols-[1.25fr_1fr]">
        <div className="space-y-5">
          <Card title="Differential considerations" sub="Ranked by damped likelihood ratios from cited chart evidence. The clinician’s impression is deliberately ignored to avoid anchoring.">
            <div className="space-y-2.5">
              {d.differential.map((x: any, i: number) => (
                <motion.div key={x.key} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }} className="rounded-2xl border hairline bg-white/[0.03]">
                  <button className="flex w-full items-center gap-4 p-3.5 text-left" onClick={() => setOpen(open === x.key ? null : x.key)}>
                    <div className="h-display w-6 text-center text-lg text-slate-500">{i + 1}</div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2"><span className="text-[14px] font-medium text-white">{x.name}</span>{x.cannot_miss && <Badge color="#ff7a90" dot>Cannot miss</Badge>}<Badge color={x.strength === "strong" ? "#34d6ae" : x.strength === "moderate" ? "#f2c46d" : "#8ea3c0"}>{x.strength}</Badge></div>
                      <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/10"><motion.div initial={{ width: 0 }} animate={{ width: `${(x.share / top) * 100}%` }} transition={{ duration: 0.9, delay: i * 0.05 }} className="h-full rounded-full bg-gradient-to-r from-jade-500 to-aur-sky" /></div>
                    </div>
                    <div className="h-display w-14 text-right text-xl font-semibold text-white">{pct(x.share)}</div>
                  </button>
                  {open === x.key && (
                    <div className="grid gap-4 border-t hairline p-4 md:grid-cols-2">
                      <div><div className="eyebrow mb-2 text-jade-300">For ({x.support.length})</div>{x.support.map((s: any) => <div key={s.finding} className="mb-1.5 flex items-center justify-between rounded-lg bg-jade-400/[0.07] px-2.5 py-1.5 text-[12.5px]"><span>{s.label} {s.evidence.map((e: string) => <button key={e} onClick={() => setHl(e)} className="ml-1 font-mono text-[10px] text-aur-sky">{e}</button>)}</span><span className="font-mono text-jade-300">×{s.lr}</span></div>)}</div>
                      <div><div className="eyebrow mb-2 text-aur-rose">Against ({x.against.length})</div>{x.against.map((s: any) => <div key={s.finding} className="mb-1.5 flex items-center justify-between rounded-lg bg-aur-rose/[0.08] px-2.5 py-1.5 text-[12.5px]"><span>{s.label}</span><span className="font-mono text-aur-rose">×{s.lr}</span></div>)}{!x.against.length && <div className="text-[12.5px] text-slate-500">Nothing documented against.</div>}
                        {x.unassessed?.length > 0 && <><div className="eyebrow mb-2 mt-3 text-aur-gold">Not yet assessed</div><div className="flex flex-wrap gap-1.5">{x.unassessed.map((u: string) => <Badge key={u} color="#f2c46d">{u}</Badge>)}</div></>}</div>
                    </div>)}
                </motion.div>
              ))}
            </div>
          </Card>
          <Card title="Verified narrative" sub={`Source: ${d.narrative_source}. Every sentence is checked before release.`} right={<Badge color={CHK[d.verification.status]} dot>{d.verification.released ? "Released" : "Blocked"}</Badge>}>
            <p className="text-[14px] leading-[1.85] text-slate-200"><Cited text={d.narrative} onPick={setHl} /></p>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="text-[12px] text-slate-400">Your decision:</span>
              <button className="btn" disabled={!!acted} onClick={() => act("accepted")}><Check size={14} className="text-jade-400" />Accept</button>
              <button className="btn" disabled={!!acted} onClick={() => act("modified")}><Pencil size={14} className="text-aur-gold" />Modify</button>
              <button className="btn" disabled={!!acted} onClick={() => act("rejected")}><X size={14} className="text-aur-rose" />Reject</button>
              {acted && <Badge color="#34d6ae">Logged: {acted}</Badge>}
            </div>
          </Card>
          <Card title="Red flags and suggested next steps">
            <div className="space-y-2">{d.red_flags.map((r: any, i: number) => <div key={i} className="flex gap-2 rounded-xl border border-aur-rose/30 bg-aur-rose/10 p-3 text-[13px] text-aur-rose"><AlertTriangle size={15} className="mt-0.5 shrink-0" />{r.text}</div>)}</div>
            <div className="mt-3 grid gap-2 md:grid-cols-2">{d.next_steps.map((n: any, i: number) => <div key={i} className="rounded-xl bg-white/[0.03] p-3 text-[13px]"><div className="text-slate-100">{n.test}</div><div className="mt-1 text-[11.5px] text-slate-500">for {n.for.join(", ")}</div></div>)}</div>
          </Card>
        </div>
        <div className="space-y-5">
          <Card title="Safety verifier" sub="Independent checks run on every narrative">
            <div className="space-y-2">{d.verification.checks.map((c: any) => <div key={c.name} className="flex items-start gap-2.5 rounded-xl bg-white/[0.03] p-2.5">{c.status === "Pass" ? <ShieldCheck size={16} className="mt-0.5 text-jade-400" /> : <ShieldX size={16} className="mt-0.5" style={{ color: CHK[c.status] }} />}<div><div className="text-[13px] text-slate-100">{c.name}</div><div className="text-[11.5px] text-slate-500">{c.details}</div></div></div>)}</div>
          </Card>
          <Card title="Chart evidence" sub="Citations resolve to these items">
            <div className="max-h-[360px] space-y-1.5 overflow-auto pr-1">{d.evidence.map((e: any) => <div key={e.id} className={cn("flex gap-2.5 rounded-xl p-2.5 text-[12.5px] transition", hl === e.id ? "bg-aur-sky/20 ring-1 ring-aur-sky/50" : "bg-white/[0.03]")}><span className="font-mono text-[11px] text-aur-sky">{e.id}</span><div className="min-w-0"><div className="text-slate-200">{e.text}</div><div className="text-[10.5px] text-slate-500">{e.ref} · {e.finding} ({e.polarity})</div></div></div>)}</div>
          </Card>
          <Card title="Break the verifier" sub="Paste a hallucinated narrative and watch it get blocked">
            <textarea className="input min-h-[80px] font-mono text-[12px]" value={tamper} onChange={(e) => setTamper(e.target.value)} />
            <button className="btn btn-danger mt-3" onClick={async () => setVres(await api("/api/copilot/verify", { body: { patient_id: pid, narrative: tamper } }))}>Run verifier</button>
            {vres && <div className="mt-3 space-y-1.5"><Badge color={vres.released ? "#34d6ae" : "#ff7a90"} dot>{vres.released ? "Released" : "Blocked by verifier"}</Badge>{vres.checks.filter((c: any) => c.status !== "Pass").map((c: any) => <div key={c.name} className="text-[12px]" style={{ color: CHK[c.status] }}>{c.name}: {c.details}</div>)}</div>}
          </Card>
        </div>
      </div>
    );
  }}</Gate>;
}

/* ============ Early warning ============ */
export function Warning({ pid }: { pid: string }) {
  const st = useApi(`/api/patients/${pid}/warning`);
  return <Gate state={st}>{(d) => {
    const ex = d.ml.explanation as any[];
    const rows = ex.map((e) => ({ fill: e.contribution >= 0 ? "#ff7a90" : "#34d6ae", label: e.label, v: e.contribution, value: `${e.value}${e.unit ? " " + e.unit : ""}`, ref: e.reference }));
    return (
      <div className="grid gap-5 xl:grid-cols-3">
        <Card title="NEWS2 parts" sub="Royal College of Physicians score, computed exactly">
          <div className="space-y-2">{Object.entries(d.news2.parts).map(([k, v]: any) => <div key={k} className="flex items-center gap-3"><span className="w-14 text-[12px] uppercase text-slate-400">{k}</span><div className="flex flex-1 gap-1">{[0, 1, 2, 3].map((n) => <div key={n} className="h-2.5 flex-1 rounded-full" style={{ background: n < v ? (v === 3 ? "#ff7a90" : v === 2 ? "#ffb454" : "#f2c46d") : "rgba(255,255,255,.08)" }} />)}</div><span className="w-4 text-right text-[13px] font-semibold text-white">{v}</span></div>)}</div>
          <div className="mt-4 flex items-center justify-between rounded-xl bg-white/[0.04] p-3"><span className="text-[12px] text-slate-400">Total</span><span className="h-display text-2xl font-semibold text-white">{d.news2.score}</span></div>
          <p className="mt-3 text-[12.5px] leading-relaxed text-slate-400">{d.news2.response} <span className="text-slate-500">({d.news2.frequency})</span></p>
          <div className="mt-3 flex gap-2"><Badge color={riskColor(d.qsofa.risk)}>qSOFA {d.qsofa.score}/3</Badge></div>
        </Card>
        <Card title="Learned model: why this risk?" sub="Exact additive explanation of the logistic model, in log-odds" className="xl:col-span-2">
          <div className="mb-3 flex items-center gap-5"><Ring value={d.ml.probability} size={104} color={riskColor(d.ml.tier)} label={pct(d.ml.probability)} sub={d.ml.tier} /><div className="text-[13px] leading-relaxed text-slate-400">Predicted probability of deterioration in the next 24 hours versus a population base rate of <b className="text-slate-200">{pct(d.ml.base_rate, 1)}</b>. Bars show how much each measurement pushed the risk up (right) or down (left) relative to a typical patient.</div></div>
          <div className="space-y-1.5">
            {rows.map((r, i) => { const mx = Math.max(...rows.map((x) => Math.abs(x.v)), 0.1); const w = (Math.abs(r.v) / mx) * 50; return (
              <div key={r.label} className="group grid grid-cols-[130px_1fr_150px] items-center gap-3 text-[12.5px]">
                <span className="truncate text-slate-300">{r.label}</span>
                <div className="relative h-5 rounded-md bg-white/[0.04]"><div className="absolute inset-y-0 left-1/2 w-px bg-white/20" />
                  <motion.div initial={{ width: 0 }} animate={{ width: `${w}%` }} transition={{ duration: 0.8, delay: i * 0.04 }} className="absolute inset-y-0 rounded-md" style={{ background: r.fill, left: r.v >= 0 ? "50%" : undefined, right: r.v < 0 ? "50%" : undefined, boxShadow: `0 0 14px ${r.fill}55` }} /></div>
                <span className="font-mono text-[11px] text-slate-400">{r.v > 0 ? "+" : ""}{r.v} · {r.value}</span>
              </div>); })}
            <div className="flex justify-between pt-1 text-[10.5px] text-slate-500"><span>← lowers risk</span><span>raises risk →</span></div>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">{[["AUC", d.model.auc], ["NEWS2-like AUC", d.model.auc_news2_like_rule], ["Brier", d.model.brier], ["ECE", d.model.ece]].map(([k, v]: any) => <div key={k} className="rounded-xl bg-white/[0.04] p-2.5 text-center"><div className="h-display text-lg font-semibold text-white">{v}</div><div className="text-[10px] uppercase tracking-wider text-slate-500">{k}</div></div>)}</div>
        </Card>
      </div>
    );
  }}</Gate>;
}

/* ============ Medication reconciliation ============ */
export function MedRec({ pid }: { pid: string }) {
  const ex = useApi("/api/medrec/examples");
  const [lists, setLists] = useState<{ source: string; text: string }[] | null>(null);
  const [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const cur = lists ?? ex.data?.lists ?? [];
  const run = async () => { setBusy(true); try { setRes(await api(`/api/patients/${pid}/medrec`, { body: { lists: cur } })); } catch (e: any) { toast("err", e.message); } setBusy(false); };
  return (
    <div className="space-y-5">
      <Card title="Medication lists from different sources" sub="Brand names, abbreviations and free text are normalised to RxNorm, then checked against allergies, interactions and renal function.">
        <div className="grid gap-4 md:grid-cols-2">{cur.map((l: any, i: number) => (
          <div key={i}><input className="input mb-2 font-medium" value={l.source} onChange={(e) => setLists(cur.map((x: any, j: number) => (j === i ? { ...x, source: e.target.value } : x)))} />
            <textarea className="input min-h-[130px] font-mono text-[12.5px]" value={l.text} onChange={(e) => setLists(cur.map((x: any, j: number) => (j === i ? { ...x, text: e.target.value } : x)))} /></div>
        ))}</div>
        <div className="mt-3"><button className="btn btn-primary" onClick={run} disabled={busy || !cur.length}>{busy ? "Reconciling…" : "Reconcile and check safety"}</button></div>
      </Card>
      {res && (<>
        <div className="grid gap-3 md:grid-cols-4">{Object.entries(res.counts).map(([k, v]: any) => <div key={k} className="glass p-4 text-center" style={{ borderColor: `${sev[k]}44` }}><div className="h-display text-3xl font-semibold" style={{ color: sev[k] }}>{v}</div><div className="eyebrow mt-1">{k}</div></div>)}</div>
        <div className="grid gap-5 xl:grid-cols-[1.2fr_1fr]">
          <Card title="Reconciled list" sub={`eGFR ${res.context.egfr} (CKD-EPI 2021) · K⁺ ${res.context.potassium} · age ${res.context.age}`} pad={false}>
            <Table head={["Drug", "Class", "Seen in", "Suggested action"]}>{res.reconciled.map((r: any) => (
              <tr key={r.key}><td className="td"><div className="font-medium text-white">{r.display}</div><div className="font-mono text-[10.5px] text-slate-500">RxNorm {r.rxnorm}</div></td><td className="td text-slate-400">{r.class}</td>
                <td className="td text-[12px] text-slate-400">{r.regimens.map((g: any, i: number) => <div key={i}>{g.text}</div>)}</td>
                <td className="td"><Badge color={r.suggested_action.startsWith("Avoid") ? "#ff7a90" : r.suggested_action.startsWith("Review") ? "#ffb454" : "#34d6ae"}>{r.suggested_action}</Badge><div className="mt-1 text-[11px] text-slate-500">{r.issues} issue(s)</div></td></tr>))}</Table>
          </Card>
          <Card title="Safety problems" sub="Most severe first">
            <div className="max-h-[520px] space-y-2 overflow-auto pr-1">{res.problems.map((p: any, i: number) => (
              <div key={i} className="rounded-xl border p-3 text-[12.5px]" style={{ borderColor: `${sev[p.severity]}44`, background: `${sev[p.severity]}10` }}>
                <div className="mb-1 flex items-center gap-2"><Badge color={sev[p.severity]}>{p.severity}</Badge><span className="eyebrow">{p.kind}</span><span className="text-slate-300">{p.drugs.join(" + ")}</span></div>
                <div className="leading-relaxed text-slate-300">{p.message}</div><div className="mt-1 text-slate-500">→ {p.action}</div></div>))}</div>
          </Card>
        </div>
        <Card title="Pharmacist checklist">{res.checklist.map((c: string, i: number) => <div key={i} className="flex items-start gap-2 py-1 text-[13px] text-slate-300"><Check size={14} className="mt-0.5 text-jade-400" />{c}</div>)}<div className="mt-3"><Disclaimer>{res.disclaimer}</Disclaimer></div></Card>
      </>)}
    </div>
  );
}

/* ============ SBAR handoff ============ */
export function Handoff({ pid }: { pid: string }) {
  const st = useApi(`/api/patients/${pid}/handoff`);
  const toast = useToast();
  return <Gate state={st}>{(h) => {
    const a = h.assessment;
    const text = `SBAR — ${h.name} (${h.ward} ${h.bed})\nS: ${h.situation}\nB: Admitted ${fmtTime(h.background.admitted)}; ${h.background.diagnoses.join(", ")}. History: ${h.background.history.join(", ")}. Allergies: ${h.background.allergies.join(", ")}.\nA: NEWS2 ${a.news2.score} (${a.news2.risk}), qSOFA ${a.qsofa.score}/3.\nR:\n${h.recommendation.map((r: any) => "- " + r.text).join("\n")}`;
    return (
      <div className="grid gap-5 xl:grid-cols-2">
        {[["S", "Situation", "#ff7a90", <p key="s" className="text-[14px] leading-relaxed text-slate-200">{h.situation}</p>],
          ["B", "Background", "#5cc8ff", <div key="b" className="space-y-2 text-[13px] text-slate-300"><div><span className="text-slate-500">Diagnoses: </span>{h.background.diagnoses.join(", ")}</div><div><span className="text-slate-500">History: </span>{h.background.history.join(", ") || "None"}</div><div><span className="text-slate-500">Allergies: </span>{h.background.allergies.join(", ")}</div><div><span className="text-slate-500">Medications: </span>{h.background.medications.join("; ")}</div></div>],
          ["A", "Assessment", "#f2c46d", <div key="a" className="space-y-3"><div className="flex gap-2"><Badge color={riskColor(a.news2.risk)}>NEWS2 {a.news2.score}</Badge><Badge color={riskColor(a.qsofa.risk)}>qSOFA {a.qsofa.score}</Badge><Badge color={riskColor(a.ml_risk.tier)}>ML {pct(a.ml_risk.probability)}</Badge></div>
            <div className="grid grid-cols-2 gap-2">{a.trends.map((t: any) => <div key={t.key} className="rounded-xl bg-white/[0.04] p-2.5 text-[12px]"><div className="text-slate-400">{t.label}</div><div className="text-slate-100">{t.from} → {t.to} {t.unit} <span className={t.concerning ? "text-aur-rose" : "text-slate-500"}>({t.direction})</span></div></div>)}</div></div>],
          ["R", "Recommendation", "#34d6ae", <ul key="r" className="space-y-2">{h.recommendation.map((r: any, i: number) => <li key={i} className="flex gap-2 text-[13px] text-slate-300"><Check size={14} className="mt-0.5 shrink-0 text-jade-400" />{r.text}</li>)}</ul>],
        ].map(([l, t, c, body]: any, i) => (
          <Card key={l} delay={i * 0.06} title={<span className="flex items-center gap-2"><span className="grid h-6 w-6 place-items-center rounded-lg text-[12px] font-bold text-ink-950" style={{ background: c }}>{l}</span>{t}</span>}>{body}</Card>
        ))}
        <div className="xl:col-span-2 flex items-center justify-between"><span className="text-[12px] text-slate-500">Generated from: {h.generated_from} · acuity {h.acuity}</span><button className="btn" onClick={() => { navigator.clipboard?.writeText(text); toast("ok", "SBAR copied to clipboard"); }}><ClipboardCopy size={14} />Copy as text</button></div>
      </div>
    );
  }}</Gate>;
}

/* ============ Patient portal ============ */
export function Portal({ pid }: { pid: string }) {
  const [lang, setLang] = useState("en");
  const [level, setLevel] = useState("simple");
  const st = useApi(`/api/patients/${pid}/portal?lang=${lang}&level=${level}`, [lang, level]);
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="glass flex gap-1 p-1">{[["en", "English"], ["ta", "தமிழ்"], ["hi", "हिन्दी"]].map(([k, l]) => <button key={k} onClick={() => setLang(k)} className={cn("rounded-xl px-4 py-1.5 text-[13px]", lang === k ? "bg-jade-400/15 text-jade-300" : "text-slate-400")}>{l}</button>)}</div>
        <div className="glass flex gap-1 p-1">{["simple", "detailed"].map((k) => <button key={k} onClick={() => setLevel(k)} className={cn("rounded-xl px-4 py-1.5 text-[13px] capitalize", level === k ? "bg-aur-gold/15 text-aur-gold" : "text-slate-400")}>{k}</button>)}</div>
      </div>
      <Gate state={st}>{(d) => (
        <div className="grid gap-5 xl:grid-cols-[1.4fr_1fr]">
          <div className="space-y-5">
            {Object.entries(d.sections).map(([k, s]: any, i) => (
              <Card key={k} title={s.title} delay={i * 0.05} className={k === "warning" ? "!border-aur-rose/30" : ""}>
                {s.items.map((it: any, j: number) => typeof it === "string"
                  ? <div key={j} className="flex gap-2 py-1.5 text-[14px] leading-relaxed text-slate-200"><span className="text-jade-400">•</span>{it}</div>
                  : <div key={j} className="flex items-start justify-between gap-3 border-b hairline py-2.5 text-[14px] leading-relaxed text-slate-200 last:border-0"><span>{it.text}</span>{it.flag && it.flag !== "normal" && <Badge color="#ffb454">{it.flag}</Badge>}</div>)}
              </Card>))}
          </div>
          <div className="space-y-5">
            <Card title="Review gate"><Badge color={d.review_status === "draft" ? "#f2c46d" : "#34d6ae"} dot>{d.review_status}</Badge><p className="mt-3 text-[13px] leading-relaxed text-slate-400">A clinician must approve this summary before it is released to the patient. Translations are template-based, not machine-generated, so numbers and medicine names cannot drift.</p></Card>
            <Card title="Readability"><div className="grid grid-cols-2 gap-2">{[["Grade level", d.readability.flesch_kincaid_grade], ["Words", d.readability.words], ["Sentences", d.readability.sentences], ["Avg words/sentence", d.readability.avg_sentence_words]].map(([k, v]: any) => <div key={k} className="rounded-xl bg-white/[0.04] p-3 text-center"><div className="h-display text-xl font-semibold text-white">{v}</div><div className="text-[10px] uppercase tracking-wider text-slate-500">{k}</div></div>)}</div></Card>
            <Disclaimer>{d.disclaimer}</Disclaimer>
          </div>
        </div>)}</Gate>
    </div>
  );
}
