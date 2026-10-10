"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Printer } from "lucide-react";
import { ErrorBox, Loading, useApi } from "@/components/ui";
import { fmtTime } from "@/lib/utils";

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="page-break mt-6"><h2 className="eyebrow border-b hairline pb-1.5 text-slate-300">{title}</h2><div className="mt-2.5 text-[13.5px] leading-relaxed text-slate-200">{children}</div></section>;
}

export default function Discharge() {
  const { id } = useParams<{ id: string }>();
  const d = useApi(`/api/patients/${id}/discharge`);
  if (d.error) return <ErrorBox message={d.error} />;
  if (!d.data) return <Loading />;
  const s = d.data;
  return (
    <>
      <div className="no-print mb-5 flex items-center justify-between gap-3">
        <Link href={`/patients/${id}`} className="inline-flex items-center gap-1.5 text-[12.5px] text-slate-500 hover:text-slate-200"><ArrowLeft size={13} />Back to chart</Link>
        <button className="btn btn-primary" onClick={() => window.print()} data-testid="print-discharge"><Printer size={14} />Print or save as PDF</button>
      </div>
      <article className="glass print-sheet mx-auto max-w-3xl p-8" data-testid="discharge-sheet">
        <header className="flex flex-wrap items-start justify-between gap-4 border-b hairline pb-5">
          <div>
            <div className="eyebrow text-jade-300">Discharge summary</div>
            <h1 className="h-display mt-1 text-[30px] font-semibold text-white">{s.patient.name}</h1>
            <div className="mt-1 text-[13px] text-slate-400">{s.patient.age} years · {s.patient.sex} · born {s.patient.birth_date}</div>
          </div>
          <div className="text-right text-[12px] text-slate-400">
            <div className="print-chip inline-block rounded-md border border-aur-gold/50 px-2 py-1 font-semibold uppercase tracking-wider text-aur-gold">{s.status}</div>
            <div className="mt-2">Generated {fmtTime(s.generated)}</div>
            {s.attending.length > 0 && <div>Attending: {s.attending.join(", ")}</div>}
          </div>
        </header>

        <Block title="Admission">
          {s.encounter.ward ? <>Ward {s.encounter.ward}, bed {s.encounter.bed}. </> : null}
          {s.encounter.admitted ? <>Admitted {fmtTime(s.encounter.admitted)}. </> : null}
          {s.encounter.reason ? <>Reason: {s.encounter.reason}.</> : null}
          {s.course_note && <p className="mt-1.5 text-slate-300">Latest note: {s.course_note}</p>}
        </Block>
        <Block title="Diagnoses"><ol className="list-decimal space-y-1 pl-5">{s.diagnoses.map((x: any, i: number) => <li key={i}>{x.display}{x.onset ? <span className="text-slate-500"> (since {x.onset.slice(0, 10)})</span> : null}</li>)}{!s.diagnoses.length && <li className="list-none text-slate-500">None recorded.</li>}</ol></Block>
        {s.abnormal_results.length > 0 && <Block title="Abnormal results at discharge"><table className="w-full text-[13px]"><tbody>{s.abnormal_results.map((r: any) => <tr key={r.name} className="border-b hairline"><td className="py-1.5">{r.name}</td><td className="py-1.5 font-medium">{r.value} {r.unit}</td><td className="py-1.5 text-slate-400">{r.flag}</td></tr>)}</tbody></table>{s.renal_function && <p className="mt-2 text-slate-400">Estimated GFR (CKD-EPI 2021): {s.renal_function.egfr} mL/min/1.73 m²</p>}</Block>}
        <Block title="Medicines to continue"><ul className="space-y-1.5">{s.medications_on_discharge.map((m: any, i: number) => <li key={i}><b className="font-medium text-white">{m.display}</b><span className="text-slate-400"> · {m.sig}</span></li>)}{!s.medications_on_discharge.length && <li className="text-slate-500">No active medicines.</li>}</ul></Block>
        <Block title="Allergies"><ul className="list-disc pl-5">{s.allergies.map((a: string) => <li key={a}>{a}</li>)}</ul></Block>
        {s.pending_tests.length > 0 && <Block title="Tests still pending"><ul className="list-disc pl-5">{s.pending_tests.map((t: string) => <li key={t}>{t}</li>)}</ul></Block>}
        <Block title="Follow-up"><ul className="list-disc pl-5">{s.follow_up.map((f: string) => <li key={f}>{f}</li>)}</ul></Block>
        <Block title="Come back or call urgently if"><ul className="list-disc pl-5">{s.warning_signs.map((w: string) => <li key={w}>{w}</li>)}</ul></Block>

        <footer className="mt-8 grid gap-6 border-t hairline pt-5 text-[12px] text-slate-400 sm:grid-cols-2">
          <div><div className="mb-8 border-b border-dashed hairline" />Physician signature and date</div>
          <div><div className="mb-8 border-b border-dashed hairline" />Patient or carer acknowledgement</div>
        </footer>
        <p className="mt-5 text-[11px] text-slate-500">{s.disclaimer}</p>
      </article>
    </>
  );
}
