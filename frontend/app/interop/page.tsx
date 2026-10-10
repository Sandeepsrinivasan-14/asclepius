"use client";
import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Inbox, RotateCcw, Send, Skull, Zap } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Card, Gate, PageHeader, Stat, useApi, useToast } from "@/components/ui";
import { cn } from "@/lib/utils";

const STATUS: Record<string, string> = { done: "#34d6ae", queued: "#5cc8ff", retry: "#ffb454", dead: "#ff7a90" };

export default function Interop() {
  const demo = useApi("/api/interop/demo");
  const q = useApi("/api/interop/queue");
  const toast = useToast();
  const [acks, setAcks] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const send = async (i: number, raw: string) => { const r = await api("/api/interop/hl7", { raw }); setAcks((a) => ({ ...a, [i]: r.ack })); q.reload(); };
  const sendAll = async () => { setBusy(true); for (const [i, m] of demo.data.messages.entries()) await send(i, m.raw); setBusy(false); toast("ok", "All 7 demo messages submitted."); };
  const process = async () => { setBusy(true); const r = await api("/api/interop/process?passes=3", { method: "POST" }); setBusy(false); q.reload(); toast("ok", `Processed ${r.processed}, ${r.dead} dead-lettered.`); };
  const s = q.data?.stats;
  return (
    <>
      <PageHeader eyebrow="Interoperability" title="HL7 v2 ingestion pipeline" sub="Real feeds are messy: duplicates, out-of-order messages, malformed segments. This pipeline acknowledges fast (MSA), then processes asynchronously with idempotency, bounded retries with backoff, and a dead-letter queue that a human can replay."
        actions={<><button className="btn" onClick={sendAll} disabled={busy || !demo.data}><Send size={14} />Send all demo messages</button><button className="btn btn-primary" onClick={process} disabled={busy}><Zap size={14} />Run processor</button></>} />
      {s && <div className="mb-5 grid gap-3 sm:grid-cols-3 xl:grid-cols-7">{[["received", "#5cc8ff"], ["accepted", "#34d6ae"], ["duplicates", "#f2c46d"], ["rejected", "#ff7a90"], ["processed", "#34d6ae"], ["retries", "#ffb454"], ["dead_lettered", "#ff7a90"]].map(([k, c]: any) => <div key={k} className="glass p-3.5"><div className="eyebrow">{k.replace("_", " ")}</div><div className="h-display mt-1 text-3xl font-semibold" style={{ color: c }}>{s[k] ?? 0}</div></div>)}</div>}
      <div className="grid gap-5 xl:grid-cols-[1.2fr_1fr]">
        <Card title="Demo messages" sub="Each one exercises a different failure mode" pad={false}>
          <Gate state={demo}>{(d) => <div className="divide-y divide-white/[0.05]">{d.messages.map((m: any, i: number) => (
            <div key={i} className="p-4">
              <div className="mb-2 flex items-center justify-between gap-3"><div className="text-[13px] font-medium text-slate-100">{i + 1}. {m.label}</div><button className="btn !py-1 text-[12px]" onClick={() => send(i, m.raw)}><Send size={12} />Send</button></div>
              <pre className="overflow-x-auto rounded-xl bg-ink-950/70 p-3 font-mono text-[11px] leading-relaxed text-aur-sky/90">{m.raw}</pre>
              <AnimatePresence>{acks[i] && <motion.pre initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className={cn("mt-2 overflow-x-auto rounded-xl p-3 font-mono text-[11px] leading-relaxed", /MSA\|A[AE]/.test(acks[i]) ? "bg-jade-400/10 text-jade-300" : "bg-aur-rose/10 text-aur-rose")}>{acks[i]}</motion.pre>}</AnimatePresence>
            </div>))}</div>}</Gate>
        </Card>
        <div className="space-y-5">
          <Card title="Dead-letter queue" sub="Exhausted retries. Fix the cause, then replay." right={<Badge color="#ff7a90"><Skull size={11} />{q.data?.dead_letter.length ?? 0}</Badge>}>
            <div className="space-y-2.5">{q.data?.dead_letter.map((j: any) => (
              <div key={j.id} className="rounded-xl border border-aur-rose/25 bg-aur-rose/[0.06] p-3"><div className="flex items-center justify-between"><div className="text-[13px] text-slate-100">{j.type} · {j.control_id}</div><button className="btn !py-1 text-[12px]" onClick={async () => { await api(`/api/interop/dlq/${j.id}/replay`, { method: "POST" }); q.reload(); toast("info", "Re-queued for another attempt."); }}><RotateCcw size={12} />Replay</button></div>
                <div className="mt-1 text-[12px] text-aur-rose">{j.last_error}</div><div className="mt-1 text-[11px] text-slate-500">{j.attempts} attempts</div></div>))}
              {!q.data?.dead_letter.length && <div className="text-[13px] text-slate-500">Empty. Send the demo messages and run the processor.</div>}</div>
          </Card>
          <Card title="Processing log">
            <div className="max-h-[360px] space-y-1.5 overflow-auto pr-1">{q.data?.recent.map((j: any) => (
              <div key={j.id} className="flex items-start gap-2.5 rounded-xl bg-white/[0.03] p-2.5 text-[12px]"><Badge color={STATUS[j.status] ?? "#8ea3c0"} dot>{j.status}</Badge><div className="min-w-0"><div className="text-slate-200">{j.type} · {j.control_id}</div><div className="truncate text-slate-500">{j.history[j.history.length - 1]}</div></div></div>))}
              {!q.data?.recent.length && <div className="flex items-center gap-2 text-[13px] text-slate-500"><Inbox size={14} />No messages yet.</div>}</div>
          </Card>
        </div>
      </div>
    </>
  );
}
