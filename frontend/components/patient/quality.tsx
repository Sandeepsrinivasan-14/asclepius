"use client";
import { Badge, Card, Disclaimer, Gate, useApi } from "@/components/ui";

const STATUS: Record<string, { color: string; label: string }> = {
  overdue: { color: "#ff7a90", label: "Overdue" },
  due: { color: "#f2c46d", label: "Due" },
  met: { color: "#34d6ae", label: "Up to date" },
};

export function CareGaps({ pid }: { pid: string }) {
  const st = useApi(`/api/patients/${pid}/caregaps`);
  return (
    <Gate state={st}>{(d) => (
      <Card title="Care gaps" sub={`${d.open} open · ${d.met} up to date · as of ${d.as_of}`}>
        {d.gaps.length === 0 ? <div className="text-[13px] text-slate-400">No applicable preventive or monitoring items for this patient.</div> : (
          <ul className="divide-y hairline" data-testid="caregap-list">
            {d.gaps.map((g: any) => (
              <li key={g.id} className="flex flex-wrap items-center gap-3 py-2.5">
                <Badge color={STATUS[g.status].color} dot>{STATUS[g.status].label}</Badge>
                <div className="min-w-[200px] flex-1">
                  <div className="text-[13px] font-medium text-slate-100">{g.title}</div>
                  <div className="text-[12px] text-slate-400">{g.detail}</div>
                </div>
                <span className="chip capitalize">{g.category}</span>
                <span className="text-[11.5px] text-slate-500">{g.basis}</span>
              </li>
            ))}
          </ul>
        )}
        <div className="mt-3"><Disclaimer>{d.note}</Disclaimer></div>
      </Card>
    )}</Gate>
  );
}

export function LabReview({ pid }: { pid: string }) {
  const st = useApi(`/api/patients/${pid}/labreview`);
  return (
    <Gate state={st}>{(d) => (
      <div className="grid gap-5 lg:grid-cols-2" data-testid="labreview">
        <Card title="Kidney injury screen" sub="KDIGO creatinine criteria" hi={d.aki.stage > 0}>
          <div className="flex items-baseline gap-3">
            <span className="h-display text-[34px] font-semibold" style={{ color: d.aki.stage ? "#ff7a90" : "#34d6ae" }}>{d.aki.label}</span>
            {d.aki.current != null && <span className="text-[13px] text-slate-400">creatinine {d.aki.current} vs baseline {d.aki.baseline} mg/dL ({d.aki.ratio}x)</span>}
          </div>
          <div className="mt-2 text-[12.5px] text-slate-400">{d.aki.basis}</div>
          {d.aki.action && <div className="mt-3 rounded-xl border border-aur-rose/30 bg-aur-rose/10 px-3 py-2 text-[13px] text-slate-200">{d.aki.action}</div>}
        </Card>
        <Card title="Delta checks" sub="Results that moved faster than expected since the previous one">
          {d.deltas.length === 0 ? <div className="text-[13px] text-slate-400">No implausible changes between the latest two results.</div> : (
            <ul className="space-y-2.5" data-testid="delta-list">
              {d.deltas.map((x: any) => (
                <li key={x.analyte} className="text-[13px]">
                  <div className="flex items-baseline justify-between gap-2"><span className="font-medium text-slate-100">{x.display}</span><span className="font-semibold text-aur-amber">{x.previous} → {x.current} {x.unit}</span></div>
                  <div className="text-[12px] text-slate-400">{x.reasons.join(", ")} in {x.hours_apart} h. {x.action}</div>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <div className="lg:col-span-2"><Disclaimer>{d.note}</Disclaimer></div>
      </div>
    )}</Gate>
  );
}
