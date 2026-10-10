"use client";
import { Area, AreaChart, CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fmtTime } from "@/lib/utils";

export const tickTime = (t: string) => new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
const tip = { contentStyle: { background: "rgba(7,12,22,.95)", border: "1px solid rgba(255,255,255,.1)", borderRadius: 12, fontSize: 12 }, labelStyle: { color: "#9fb3cf" }, cursor: { stroke: "rgba(255,255,255,.15)" } };

export function VitalChart({ data, color, unit, band, height = 150, domain }: { data: { t: string; v: number }[]; color: string; unit: string; band?: [number, number]; height?: number; domain?: [number | string, number | string] }) {
  const id = `vc${color.replace("#", "")}${unit.replace(/\W/g, "")}`;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
        <defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={color} stopOpacity={0.35} /><stop offset="100%" stopColor={color} stopOpacity={0} /></linearGradient></defs>
        <CartesianGrid stroke="rgba(255,255,255,.05)" vertical={false} />
        {band && <ReferenceArea y1={band[0]} y2={band[1]} fill="#34d6ae" fillOpacity={0.07} />}
        <XAxis dataKey="t" tickFormatter={tickTime} tick={{ fill: "#6b7f9d", fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={36} />
        <YAxis tick={{ fill: "#6b7f9d", fontSize: 10 }} axisLine={false} tickLine={false} domain={domain ?? ["auto", "auto"]} />
        <Tooltip {...tip} labelFormatter={(l) => fmtTime(l as string)} formatter={(v: number) => [`${v} ${unit}`, ""]} />
        <Area isAnimationActive={false} type="monotone" dataKey="v" stroke={color} strokeWidth={2} fill={`url(#${id})`} dot={false} activeDot={{ r: 4, fill: color }} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function News2Chart({ data }: { data: { time: string; score: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={210}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
        <CartesianGrid stroke="rgba(255,255,255,.05)" vertical={false} />
        <ReferenceArea y1={7} y2={20} fill="#ff7a90" fillOpacity={0.08} />
        <ReferenceArea y1={5} y2={7} fill="#ffb454" fillOpacity={0.07} />
        <ReferenceLine y={7} stroke="#ff7a90" strokeDasharray="4 4" strokeOpacity={0.6} />
        <ReferenceLine y={5} stroke="#ffb454" strokeDasharray="4 4" strokeOpacity={0.6} />
        <XAxis dataKey="time" tickFormatter={tickTime} tick={{ fill: "#6b7f9d", fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={40} />
        <YAxis tick={{ fill: "#6b7f9d", fontSize: 10 }} axisLine={false} tickLine={false} domain={[0, (m: number) => Math.max(10, m + 1)]} />
        <Tooltip {...tip} labelFormatter={(l) => fmtTime(l as string)} />
        <Line isAnimationActive={false} type="stepAfter" dataKey="score" stroke="#f2c46d" strokeWidth={2.4} dot={false} activeDot={{ r: 5 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function LabChart({ series, low, high, color }: { series: { t: string; v: number; flag?: string }[]; low?: number; high?: number; color: string }) {
  return (
    <ResponsiveContainer width="100%" height={92}>
      <LineChart data={series} margin={{ top: 6, right: 10, bottom: 0, left: 10 }}>
        {low !== undefined && high !== undefined && <ReferenceArea y1={low} y2={high} fill="#34d6ae" fillOpacity={0.09} />}
        <XAxis dataKey="t" hide /><YAxis hide domain={["auto", "auto"]} />
        <Tooltip {...tip} labelFormatter={(l) => fmtTime(l as string)} />
        <Line isAnimationActive={false} type="monotone" dataKey="v" stroke={color} strokeWidth={2} dot={{ r: 3, fill: color, strokeWidth: 0 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
