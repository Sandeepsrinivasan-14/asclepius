"use client";
import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, Fingerprint, Lock, Scale, ShieldCheck, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/components/auth";
import { Badge } from "@/components/ui";
import { initials } from "@/lib/utils";

const Helix = dynamic(() => import("@/components/helix"), { ssr: false });
const ROLE_COLOR: Record<string, string> = { physician: "#34d6ae", nurse: "#5cc8ff", pharmacist: "#8b7bff", admin: "#f2c46d", privacy_officer: "#ff7a90" };

export default function Login() {
  const [personas, setPersonas] = useState<any[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const { login, user } = useAuth();
  const router = useRouter();
  useEffect(() => { api("/api/auth/personas").then(setPersonas).catch(() => {}); }, []);
  useEffect(() => { if (user) router.replace("/dashboard"); }, [user, router]);
  const enter = async (u: string) => { setBusy(u); await login(u); router.push("/dashboard"); };

  return (
    <div className="relative grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <div className="relative hidden overflow-hidden lg:block">
        <div className="absolute inset-y-0 right-[-8%] w-[62%]"><Helix /></div><div className="absolute inset-0 bg-gradient-to-r from-ink-950 via-ink-950/60 to-transparent" />
        <div className="relative z-10 flex h-full flex-col justify-between p-12">
          <div className="flex items-center gap-3"><div className="grid h-10 w-10 place-items-center rounded-xl border border-jade-400/40 bg-jade-500/10 shadow-glow"><Sparkles size={18} className="text-jade-300" /></div><span className="h-display text-2xl font-semibold tracking-wide text-white">Asclepius</span></div>
          <div>
            <motion.h1 initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.8 }} className="h-display max-w-lg text-[54px] font-semibold leading-[1.05] text-white">Clinical intelligence that <span className="gradient-text">shows its work.</span></motion.h1>
            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 }} className="mt-5 max-w-md text-[15px] leading-relaxed text-slate-300/80">FHIR R4, HL7 v2 and an ABDM-aligned consent layer, with explainable AI that is verified, audited and governed before a clinician ever sees it.</motion.p>
            <div className="mt-7 flex flex-wrap gap-2"><Badge color="#34d6ae">FHIR R4</Badge><Badge color="#5cc8ff">SMART on FHIR</Badge><Badge color="#f2c46d">HL7 v2.5.1</Badge><Badge color="#8b7bff">ABDM mock</Badge><Badge color="#ff7a90">Hash-chained audit</Badge></div>
          </div>
          <div className="text-[12px] text-slate-500">All patients, notes, images and identifiers are synthetic. Educational software, not a medical device.</div>
        </div>
      </div>
      <div className="relative flex items-center justify-center p-6 lg:p-12">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-md">
          <div className="eyebrow text-jade-300/80">Demo sign-in</div>
          <h2 className="h-display mt-1 text-[32px] font-semibold text-white">Choose a role to explore</h2>
          <p className="mt-2 text-[13.5px] text-slate-400">Each persona has different permissions, so you can see role-based access, break-glass and audit working for real.</p>
          <div className="mt-6 space-y-2.5">
            {personas.map((p, i) => (
              <motion.button key={p.username} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.08 * i }} whileHover={{ x: 4 }} onClick={() => enter(p.username)} disabled={!!busy}
                className="glass group flex w-full items-center gap-3.5 p-3.5 text-left transition hover:border-jade-400/30">
                <div className="grid h-11 w-11 shrink-0 place-items-center rounded-full text-[13px] font-bold text-ink-950" style={{ background: `linear-gradient(135deg, ${ROLE_COLOR[p.role] ?? "#8ea3c0"}, #ffffff55)` }}>{initials(p.name)}</div>
                <div className="min-w-0 flex-1"><div className="text-[14px] font-medium text-white">{p.name}</div><div className="truncate text-[12px] text-slate-400">{p.title}</div></div>
                {busy === p.username ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-jade-400 border-t-transparent" /> : <ArrowRight size={16} className="text-slate-600 transition group-hover:translate-x-1 group-hover:text-jade-300" />}
              </motion.button>
            ))}
          </div>
          <div className="mt-6 grid grid-cols-3 gap-2 text-center text-[11px] text-slate-500">
            <div className="glass p-2.5"><Lock size={14} className="mx-auto mb-1 text-jade-300" />ABAC + consent</div>
            <div className="glass p-2.5"><Fingerprint size={14} className="mx-auto mb-1 text-aur-gold" />Tamper-evident</div>
            <div className="glass p-2.5"><ShieldCheck size={14} className="mx-auto mb-1 text-aur-sky" />Verified AI</div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
