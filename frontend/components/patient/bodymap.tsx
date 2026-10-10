"use client";
import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import { Filter, FilterX, MousePointerClick } from "lucide-react";
import { Badge, Card, Skeleton } from "@/components/ui";
import { cn } from "@/lib/utils";

const Scene = dynamic(() => import("@/components/bodymap3d"), { ssr: false, loading: () => <Skeleton h={460} /> });
const COLOR: Record<string, string> = { clear: "#3f8f80", watch: "#f2c46d", abnormal: "#ffb454", critical: "#ff5a73" };
const LABEL: Record<string, string> = { clear: "No findings", watch: "On treatment", abnormal: "Abnormal", critical: "Critical" };

export type OrganFilter = { key: string; label: string; conditionIds: Set<string>; medIds: Set<string>; labKeys: Set<string>; vitalKeys: Set<string> };
export const makeFilter = (o: any): OrganFilter => ({
  key: o.key, label: o.label, conditionIds: new Set(o.conditions.map((c: any) => c.id)), medIds: new Set(o.meds.map((m: any) => m.id)),
  labKeys: new Set(o.labs.map((l: any) => l.key)), vitalKeys: new Set(o.vitals.map((v: any) => v.key)),
});

export function BodyMapTab({ bm, selected, onSelect, onFilter, filterKey }: { bm: any; selected: string | null; onSelect: (k: string | null) => void; onFilter: (o: any | null) => void; filterKey: string | null }) {
  const sel = bm.organs.find((o: any) => o.key === selected);
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <Card title="Anatomical map" sub="Drag to rotate. Click an organ to inspect it, then filter the whole chart to that system." pad={false}>
        <div className="relative h-[470px] w-full" data-testid="bodymap-canvas" aria-label="3D anatomical body map. Use the organ list for keyboard access.">
          <Scene organs={bm.organs.map((o: any) => ({ key: o.key, status: o.status }))} selected={selected} onSelect={onSelect} />
          <div className="pointer-events-none absolute bottom-3 left-3 flex flex-wrap gap-1.5">{Object.entries(COLOR).map(([k, c]) => <span key={k} className="chip" style={{ color: c, borderColor: `${c}55` }}><span className="h-1.5 w-1.5 rounded-full" style={{ background: c }} />{LABEL[k]}</span>)}</div>
        </div>
      </Card>
      <div className="space-y-4">
        <Card title="Organ systems" sub="Ranked by severity. This list is the keyboard-accessible equivalent of the 3D model.">
          <ul className="grid gap-2 sm:grid-cols-2" data-testid="organ-list">
            {bm.ranked.map((k: string) => {
              const o = bm.organs.find((x: any) => x.key === k);
              return (
                <li key={k}>
                  <button onClick={() => onSelect(selected === k ? null : k)} aria-pressed={selected === k} data-testid={`organ-${k}`}
                    className={cn("flex w-full items-center gap-2.5 rounded-xl border px-3 py-2 text-left transition", selected === k ? "border-jade-400/50 bg-jade-400/10" : "hairline bg-white/[0.03] hover:bg-white/[0.07]")}>
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: COLOR[o.status], boxShadow: `0 0 10px ${COLOR[o.status]}` }} />
                    <span className="min-w-0 flex-1"><span className="block truncate text-[13px] font-medium text-slate-100">{o.label}</span><span className="block text-[11px] text-slate-400">{LABEL[o.status]}{o.conditions.length ? ` · ${o.conditions.length} problem${o.conditions.length > 1 ? "s" : ""}` : ""}</span></span>
                  </button>
                </li>
              );
            })}
          </ul>
        </Card>
        <Card title={sel ? sel.label : "Select an organ"} sub={sel ? undefined : "Nothing selected"} right={sel && <Badge color={COLOR[sel.status]} dot>{LABEL[sel.status]}</Badge>} hi={!!sel}>
          {!sel ? <div className="flex items-center gap-2 text-[13px] text-slate-400"><MousePointerClick size={15} />Click an organ on the model or in the list to see its problems, results, vitals and treatments.</div> : (
            <motion.div key={sel.key} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="space-y-3 text-[13px]" data-testid="organ-detail">
              {sel.conditions.length > 0 && <Section title="Problems">{sel.conditions.map((c: any) => <li key={c.id} className="text-slate-100">{c.display}</li>)}</Section>}
              {sel.labs.length > 0 && <Section title="Latest results">{sel.labs.map((l: any) => <li key={l.key} className="flex justify-between gap-2 text-slate-200"><span>{l.name}</span><span className={l.flag === "normal" ? "text-slate-400" : "font-semibold text-aur-amber"}>{l.value} {l.unit}{l.flag !== "normal" && ` · ${l.flag}`}</span></li>)}</Section>}
              {sel.vitals.length > 0 && <Section title="Vitals">{sel.vitals.map((v: any) => <li key={v.key} className="flex justify-between gap-2 text-slate-200"><span>{v.name}</span><span className={v.flag === "normal" ? "text-slate-400" : "font-semibold text-aur-amber"}>{v.value} {v.unit}</span></li>)}</Section>}
              {sel.meds.length > 0 && <Section title="Treatments">{sel.meds.map((m: any) => <li key={m.id} className="text-slate-200">{m.display}<span className="text-slate-500"> · {m.sig}</span></li>)}</Section>}
              {!sel.conditions.length && !sel.labs.length && !sel.vitals.length && !sel.meds.length && <div className="text-slate-400">Nothing recorded for this system.</div>}
              <div className="flex gap-2 pt-1">
                {filterKey === sel.key
                  ? <button className="btn" onClick={() => onFilter(null)}><FilterX size={14} />Clear chart filter</button>
                  : <button className="btn btn-primary" onClick={() => onFilter(sel)} data-testid="apply-organ-filter"><Filter size={14} />Filter chart to this organ</button>}
              </div>
            </motion.div>
          )}
        </Card>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <div><div className="eyebrow mb-1">{title}</div><ul className="space-y-1">{children}</ul></div>;
}
