"use client";

export type User = { username: string; name: string; role: string; title: string; wards?: string[] };

let token: string | null = null;
export const setToken = (t: string | null) => {
  token = t;
  try { t ? sessionStorage.setItem("asc.token", t) : sessionStorage.removeItem("asc.token"); } catch {}
};
export const getToken = () => {
  if (token) return token;
  try { token = sessionStorage.getItem("asc.token"); } catch {}
  return token;
};

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown; raw?: string } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const t = getToken();
  if (t) headers.Authorization = `Bearer ${t}`;
  let body: BodyInit | undefined;
  if (opts.raw !== undefined) { body = opts.raw; headers["Content-Type"] = "text/plain"; }
  else if (opts.body !== undefined) { body = JSON.stringify(opts.body); headers["Content-Type"] = "application/json"; }
  const res = await fetch(path, { method: opts.method || (body ? "POST" : "GET"), headers, body });
  const text = await res.text();
  let json: any = null;
  try { json = text ? JSON.parse(text) : null; } catch {}
  if (!res.ok) {
    const e = json?.error;
    throw new ApiError(res.status, e?.code || "error", e?.message || json?.detail?.[0]?.msg || json?.issue?.[0]?.diagnostics || res.statusText);
  }
  return json as T;
}

export const img = (p: string) => `${p}${p.includes("?") ? "&" : "?"}access_token=${getToken() ?? ""}`;
