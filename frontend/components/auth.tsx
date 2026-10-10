"use client";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, getToken, setToken, type User } from "@/lib/api";

type Ctx = { user: User | null; ready: boolean; login: (u: string) => Promise<void>; logout: () => void; can: (roles: string[]) => boolean };
const AuthCtx = createContext<Ctx>(null as unknown as Ctx);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const router = useRouter();
  const path = usePathname();

  useEffect(() => {
    if (!getToken()) { setReady(true); return; }
    api<User>("/api/auth/me").then(setUser).catch(() => setToken(null)).finally(() => setReady(true));
  }, []);

  useEffect(() => {
    if (ready && !user && path !== "/login") router.replace("/login");
  }, [ready, user, path, router]);

  const login = useCallback(async (username: string) => {
    const r = await api<{ token: string; user: User }>("/api/auth/login", { body: { username } });
    setToken(r.token);
    setUser(r.user);
  }, []);
  const logout = useCallback(() => { setToken(null); setUser(null); router.replace("/login"); }, [router]);
  const can = useCallback((roles: string[]) => !!user && roles.includes(user.role), [user]);
  return <AuthCtx.Provider value={{ user, ready, login, logout, can }}>{children}</AuthCtx.Provider>;
}
