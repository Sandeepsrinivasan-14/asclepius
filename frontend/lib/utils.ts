import clsx, { type ClassValue } from "clsx";
export const cn = (...a: ClassValue[]) => clsx(a);
export const pct = (x: number, d = 0) => `${(x * 100).toFixed(d)}%`;
export const riskColor = (r: string) =>
  ({ high: "#ff7a90", medium: "#ffb454", "low-medium": "#f2c46d", low: "#34d6ae" } as Record<string, string>)[r] ?? "#8ea3c0";
export const news2Color = (s: number) => (s >= 7 ? "#ff7a90" : s >= 5 ? "#ffb454" : s >= 1 ? "#f2c46d" : "#34d6ae");
export const fmtTime = (iso?: string) => (iso ? new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "");
export const initials = (n: string) => n.split(/\s+/).map((p) => p[0]).slice(0, 2).join("").toUpperCase();
