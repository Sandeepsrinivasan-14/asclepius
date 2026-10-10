"use client";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";
import { useAuth } from "@/components/auth";
import { Badge, Card, Gate, Limited, PageHeader, Ring, Spark, Stat, Table, useApi } from "@/components/ui";
import { WidgetGrid, type WidgetDef } from "@/components/widgets";
import { news2Color, riskColor } from "@/lib/utils";

const LINKS = [
  { href: "/scribe", t: "Ambient scribe", d: "Turn a visit transcript into a SOAP note and a draft FHIR bundle for physician sign-off.", c: "#34d6ae" },
  { href: "/interop", t: "HL7 pipeline", d: "Watch idempotency, retries and the dead-letter queue handle messy real-world feeds.", c: "#f2c46d" },
  { href: "/governance", t: "AI governance", d: "Model cards, drift, fairness and clinician override rates in one place.", c: "#8b7bff" },
  { href: "/terminology", t: "Terminology and Synthea", d: "Look up ICD-10, SNOMED CT, LOINC and RxNorm, then import a Synthea patient.", c: "#5cc8ff" },
];

export default function Dashboard() {
  const { user } = useAuth();
  const warn = useApi("/api/warning/overview");
  const ops = useApi("/api/ops/overview");
  const meta = useApi("/api/meta");
  const hour = new Date().getHours();
  const greet = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  const noWarn = <Limited message="Clinical monitoring (NEWS2) is not part of your role." />;
  const noOps = <Limited message="Operations data is not available to your role." />;

  const widgets: WidgetDef[] = [
    { id: "stat-monitored", title: "Inpatients monitored", span: 1, node: warn.error ? noWarn : <Gate state={warn}>{(w) => <Stat label="Inpatients monitored" value={w.patients.length} hint="NEWS2 recomputed from latest vitals" spark={w.patients.slice(0, 10).map((p: any) => p.news2)} />}</Gate> },
    { id: "stat-high", title: "High-risk patients", span: 1, node: warn.error ? noWarn : <Gate state={warn}>{(w) => <Stat label="High-risk (NEWS2 ≥ 7)" value={w.counts.high} color="#ff7a90" hint="Emergency response threshold" delay={0.05} spark={[1, 2, 2, 3, 3, 4, w.counts.high]} />}</Gate> },
    { id: "stat-rising", title: "Rising in 12 hours", span: 1, node: warn.error ? noWarn : <Gate state={warn}>{(w) => <Stat label="Rising in 12 hours" value={w.rising} color="#ffb454" hint="Score up by 2 or more" delay={0.1} spark={[0, 1, 1, 2, 2, w.rising]} />}</Gate> },
    { id: "stat-beds", title: "Bed occupancy", span: 1, node: ops.error ? noOps : <Gate state={ops}>{(o) => <Stat label="Bed occupancy" value={o.occupancy * 100} suffix="%" decimals={0} color="#5cc8ff" hint={`${o.occupied} of ${o.total_beds} beds`} delay={0.15} spark={o.wards[0].sparkline} />}</Gate> },
    {
      id: "watchlist", title: "Deterioration watchlist", span: 3, node: (
        <Card title="Deterioration watchlist" sub="Highest NEWS2 first. The ML tier is a separate, explainable model shown for comparison." right={<Link href="/monitor" className="btn !py-1.5 text-[12px]">Live monitor <ArrowUpRight size={13} /></Link>} pad={false} delay={0.1} className="h-full">
          {warn.error ? <div className="p-5"><Limited message="The watchlist needs clinical monitoring permission. Physicians and nurses see it here." /></div> : <Gate state={warn}>{(w) => (
            <Table head={["Patient", "Ward", "NEWS2", "12h trend", "qSOFA", "ML risk", "Working dx"]}>
              {w.patients.slice(0, 9).map((p: any, i: number) => (
                <motion.tr key={p.id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.04 * i }} className="group cursor-pointer hover:bg-white/[0.03]">
                  <td className="td"><Link href={`/patients/${p.id}`} className="whitespace-nowrap font-medium text-white group-hover:text-jade-300">{p.name}</Link><div className="whitespace-nowrap text-[11px] text-slate-500">{p.age}{p.sex[0].toUpperCase()} · {p.bed}</div></td>
                  <td className="td"><Badge>{p.ward}</Badge></td>
                  <td className="td"><span className="inline-flex h-7 min-w-[2rem] items-center justify-center rounded-lg px-2 text-[13px] font-bold" style={{ background: `${news2Color(p.news2)}22`, color: news2Color(p.news2), boxShadow: `0 0 18px ${news2Color(p.news2)}22` }}>{p.news2}</span></td>
                  <td className="td"><Spark data={p.spark} color={news2Color(p.news2)} w={86} h={26} /></td>
                  <td className="td text-slate-300">{p.qsofa}/3</td>
                  <td className="td"><Badge className="whitespace-nowrap" color={riskColor(p.ml_tier)} dot>{(p.ml_probability * 100).toFixed(0)}% · {p.ml_tier}</Badge></td>
                  <td className="td max-w-[220px] truncate text-slate-400">{p.dx.slice(0, 2).join(", ")}</td>
                </motion.tr>
              ))}
            </Table>
          )}</Gate>}
        </Card>
      ),
    },
    {
      id: "occupancy", title: "Ward occupancy", span: 1, node: (
        <Card title="Ward occupancy" sub="Beds in use right now" delay={0.15} className="h-full">
          {ops.error ? noOps : <Gate state={ops}>{(o) => (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-1">
              {o.wards.map((w: any) => (
                <div key={w.code} className="flex items-center gap-3">
                  <Ring value={w.occupancy} size={64} stroke={7} color={w.occupancy > 0.85 ? "#ff7a90" : w.occupancy > 0.7 ? "#ffb454" : "#34d6ae"} label={`${Math.round(w.occupancy * 100)}%`} />
                  <div><div className="text-[13px] font-medium text-white">{w.code}</div><div className="text-[11px] text-slate-400">{w.occupied}/{w.beds} beds</div></div>
                </div>
              ))}
            </div>
          )}</Gate>}
        </Card>
      ),
    },
    {
      id: "platform", title: "Platform", span: 2, node: (
        <Card title="Platform" sub="What is running behind this screen" delay={0.2} className="h-full">
          <Gate state={meta}>{(m) => (
            <>
              <div className="grid grid-cols-3 gap-2 text-center sm:grid-cols-6">
                {Object.entries(m.counts).slice(0, 6).map(([k, v]: any) => (
                  <div key={k} className="rounded-xl border hairline bg-white/[0.03] p-2.5"><div className="h-display text-lg font-semibold text-white">{v.toLocaleString()}</div><div className="truncate text-[9px] uppercase tracking-wider text-slate-500">{k}</div></div>
                ))}
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">{m.standards.map((s: string) => <Badge key={s} color="#5cc8ff">{s}</Badge>)}</div>
            </>
          )}</Gate>
        </Card>
      ),
    },
    ...LINKS.map((x, i): WidgetDef => ({
      id: `link-${x.href.slice(1)}`, title: x.t, span: 1, node: (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 + i * 0.07 }} whileHover={{ y: -4 }} className="h-full">
          <Link href={x.href} className="glass group block h-full p-5">
            <div className="mb-3 h-1 w-10 rounded-full" style={{ background: x.c }} />
            <div className="flex items-center justify-between"><h3 className="h-display text-lg font-semibold text-white">{x.t}</h3><ArrowUpRight size={16} className="text-slate-500 transition group-hover:text-white" /></div>
            <p className="mt-1.5 text-[13px] leading-relaxed text-slate-400">{x.d}</p>
          </Link>
        </motion.div>
      ),
    })),
  ];

  return (
    <>
      <PageHeader eyebrow="Command center" title={<>{greet}, <span className="gradient-text">{user?.name.split(" ").slice(0, 2).join(" ")}</span></>}
        sub="A live view of who needs attention, how full the hospital is, and the health of the interoperability and AI layers. Use Customize layout to drag, resize and hide widgets." actions={<><Badge color="#34d6ae" dot>Streaming</Badge></>} />
      <WidgetGrid storageKey="asc.layout.dashboard.v1" widgets={widgets} />
    </>
  );
}
