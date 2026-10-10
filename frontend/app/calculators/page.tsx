"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { Badge, Card, Disclaimer, PageHeader, useToast } from "@/components/ui";
import { cn } from "@/lib/utils";

type Field = { key: string; label: string; kind: "number" | "bool" | "sex"; unit?: string; def?: string };

const CALCS: { id: string; title: string; blurb: string; fields: Field[] }[] = [
  { id: "cha2ds2-vasc", title: "CHA2DS2-VASc", blurb: "Stroke risk in atrial fibrillation.", fields: [
    { key: "age", label: "Age", kind: "number", unit: "years", def: "70" }, { key: "sex", label: "Sex", kind: "sex" },
    { key: "chf", label: "Heart failure", kind: "bool" }, { key: "hypertension", label: "Hypertension", kind: "bool" }, { key: "diabetes", label: "Diabetes", kind: "bool" },
    { key: "stroke", label: "Prior stroke, TIA or embolism", kind: "bool" }, { key: "vascular", label: "Vascular disease", kind: "bool" }] },
  { id: "curb65", title: "CURB-65", blurb: "Severity of community-acquired pneumonia.", fields: [
    { key: "age", label: "Age", kind: "number", unit: "years", def: "70" }, { key: "confusion", label: "New confusion", kind: "bool" },
    { key: "urea_mmol_l", label: "Urea", kind: "number", unit: "mmol/L", def: "6" }, { key: "resp_rate", label: "Respiratory rate", kind: "number", unit: "/min", def: "20" },
    { key: "sbp", label: "Systolic BP", kind: "number", unit: "mmHg", def: "120" }, { key: "dbp", label: "Diastolic BP", kind: "number", unit: "mmHg", def: "80" }] },
  { id: "cockcroft-gault", title: "Cockcroft-Gault", blurb: "Creatinine clearance for drug dosing.", fields: [
    { key: "age", label: "Age", kind: "number", unit: "years", def: "60" }, { key: "sex", label: "Sex", kind: "sex" },
    { key: "weight_kg", label: "Weight", kind: "number", unit: "kg", def: "70" }, { key: "creatinine_mg_dl", label: "Creatinine", kind: "number", unit: "mg/dL", def: "1.0" }] },
  { id: "bmi-bsa", title: "BMI and BSA", blurb: "Body mass index and Mosteller surface area.", fields: [
    { key: "height_cm", label: "Height", kind: "number", unit: "cm", def: "170" }, { key: "weight_kg", label: "Weight", kind: "number", unit: "kg", def: "70" }] },
  { id: "corrected-calcium", title: "Corrected calcium", blurb: "Calcium adjusted for low albumin.", fields: [
    { key: "calcium_mg_dl", label: "Calcium", kind: "number", unit: "mg/dL", def: "8.4" }, { key: "albumin_g_dl", label: "Albumin", kind: "number", unit: "g/dL", def: "3.0" }] },
];

const BAND: Record<string, string> = { low: "#34d6ae", healthy: "#34d6ae", normal: "#34d6ae", mild: "#34d6ae", moderate: "#f2c46d", overweight: "#f2c46d", underweight: "#f2c46d", high: "#ff6b81", severe: "#ff6b81", obese: "#ff6b81" };

function Calc({ c }: { c: (typeof CALCS)[number] }) {
  const toast = useToast();
  const [vals, setVals] = useState<Record<string, any>>(() => Object.fromEntries(c.fields.map((f) => [f.key, f.kind === "bool" ? false : f.kind === "sex" ? "female" : f.def ?? ""])));
  const [res, setRes] = useState<any>(null);
  const run = async () => {
    const body: Record<string, any> = {};
    for (const f of c.fields) body[f.key] = f.kind === "number" ? (vals[f.key] === "" ? null : Number(vals[f.key])) : vals[f.key];
    try { setRes(await api(`/api/calculators/${c.id}`, { body })); } catch (e: any) { setRes(null); toast("err", e.message); }
  };
  return (
    <Card title={c.title} sub={c.blurb}>
      <div className="grid gap-3 sm:grid-cols-2" data-testid={`calc-${c.id}`}>
        {c.fields.map((f) => f.kind === "bool" ? (
          <label key={f.key} className="flex items-center gap-2 text-[13px] text-slate-300"><input type="checkbox" checked={!!vals[f.key]} onChange={(e) => setVals({ ...vals, [f.key]: e.target.checked })} />{f.label}</label>
        ) : f.kind === "sex" ? (
          <label key={f.key} className="text-[13px] text-slate-300">{f.label}<select className="input mt-1" value={vals[f.key]} onChange={(e) => setVals({ ...vals, [f.key]: e.target.value })}><option value="female">Female</option><option value="male">Male</option></select></label>
        ) : (
          <label key={f.key} className="text-[13px] text-slate-300">{f.label}{f.unit && <span className="text-slate-500"> ({f.unit})</span>}<input className="input mt-1" inputMode="decimal" value={vals[f.key]} onChange={(e) => setVals({ ...vals, [f.key]: e.target.value })} /></label>
        ))}
      </div>
      <button className={cn("btn mt-4")} onClick={run}>Calculate</button>
      {res && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mt-4 rounded-xl border hairline bg-white/[0.03] p-3" data-testid="calc-result" aria-live="polite">
          <div className="flex items-baseline gap-2"><span className="h-display text-3xl font-semibold text-white">{res.score}</span><span className="text-[12px] text-slate-500">{res.unit ?? (res.max ? `of ${res.max}` : "")}</span><Badge color={BAND[res.band] ?? "#8b7bff"}>{res.band}</Badge></div>
          {res.bsa_m2 && <div className="mt-1 text-[13px] text-slate-300">Body surface area {res.bsa_m2} m2</div>}
          <p className="mt-2 text-[13px] text-slate-300">{res.interpretation}</p>
          {res.components && <ul className="mt-2 space-y-0.5 text-[12px] text-slate-400">{Object.entries(res.components).map(([k, v]) => <li key={k} className={cn(v ? "text-white" : "")}>{v ? `+${v}` : "0"} {k}</li>)}</ul>}
        </motion.div>
      )}
    </Card>
  );
}

export default function Calculators() {
  return (
    <>
      <PageHeader eyebrow="Clinical" title="Bedside calculators" sub="Validated scores with every component shown. They run on the values you enter, not on a chart, and are decision support only." />
      <div className="grid gap-5 xl:grid-cols-2">{CALCS.map((c) => <Calc key={c.id} c={c} />)}</div>
      <div className="mt-5"><Disclaimer>Calculators follow published formulas on synthetic-data tooling. Verify against current guidelines and local policy before any clinical use.</Disclaimer></div>
    </>
  );
}
