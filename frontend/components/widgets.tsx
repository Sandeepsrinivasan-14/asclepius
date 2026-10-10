"use client";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Eye, EyeOff, GripVertical, LayoutGrid, Plus, RotateCcw, Check } from "lucide-react";
import { cn } from "@/lib/utils";

export type WidgetDef = { id: string; title: string; span: 1 | 2 | 3 | 4; node: ReactNode };
type Slot = { id: string; span: number; h?: number; hidden?: boolean };

const SPAN_CLASS: Record<number, string> = {
  1: "md:col-span-1 xl:col-span-1", 2: "md:col-span-2 xl:col-span-2", 3: "md:col-span-2 xl:col-span-3", 4: "md:col-span-2 xl:col-span-4",
};

/**
 * A customisable dashboard grid: drag the grip to reorder, use the arrows or drag the corner to resize,
 * hide widgets and bring them back. The layout is remembered per browser. Everything is keyboard reachable
 * through the buttons, so drag and drop is never the only way to rearrange.
 */
export function WidgetGrid({ storageKey, widgets }: { storageKey: string; widgets: WidgetDef[] }) {
  const defaults = useMemo<Slot[]>(() => widgets.map((w) => ({ id: w.id, span: w.span })), [widgets]);
  const [slots, setSlots] = useState<Slot[]>(defaults);
  const [editing, setEditing] = useState(false);
  const [drag, setDrag] = useState<string | null>(null);
  const [over, setOver] = useState<string | null>(null);
  const grid = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      const saved: Slot[] = JSON.parse(localStorage.getItem(storageKey) || "null");
      if (Array.isArray(saved)) {
        const known = new Set(widgets.map((w) => w.id));
        const kept = saved.filter((s) => known.has(s.id));
        const missing = defaults.filter((d) => !kept.some((k) => k.id === d.id));
        setSlots([...kept, ...missing]);
      }
    } catch {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey]);

  const commit = useCallback((next: Slot[]) => {
    setSlots(next);
    try { localStorage.setItem(storageKey, JSON.stringify(next)); } catch {}
  }, [storageKey]);

  const byId = useMemo(() => Object.fromEntries(widgets.map((w) => [w.id, w])), [widgets]);
  const patch = (id: string, p: Partial<Slot>) => commit(slots.map((s) => (s.id === id ? { ...s, ...p } : s)));
  const move = (id: string, dir: -1 | 1) => {
    const i = slots.findIndex((s) => s.id === id), j = i + dir;
    if (j < 0 || j >= slots.length) return;
    const next = [...slots];
    [next[i], next[j]] = [next[j], next[i]];
    commit(next);
  };
  const drop = (target: string) => {
    if (!drag || drag === target) return;
    const from = slots.findIndex((s) => s.id === drag), to = slots.findIndex((s) => s.id === target);
    const next = [...slots];
    const [m] = next.splice(from, 1);
    next.splice(to, 0, m);
    commit(next);
  };

  const startResize = (e: React.PointerEvent, s: Slot) => {
    e.preventDefault();
    const el = (e.currentTarget as HTMLElement).closest("[data-widget]") as HTMLElement;
    const colW = (grid.current?.clientWidth ?? 1200) / 4;
    const x0 = e.clientX, y0 = e.clientY, span0 = s.span, h0 = el.getBoundingClientRect().height;
    const mv = (ev: PointerEvent) => {
      const span = Math.max(1, Math.min(4, Math.round(span0 + (ev.clientX - x0) / colW)));
      const h = Math.max(120, Math.round(h0 + (ev.clientY - y0)));
      setSlots((cur) => cur.map((c) => (c.id === s.id ? { ...c, span, h } : c)));
    };
    const up = () => {
      window.removeEventListener("pointermove", mv); window.removeEventListener("pointerup", up);
      setSlots((cur) => { try { localStorage.setItem(storageKey, JSON.stringify(cur)); } catch {} return cur; });
    };
    window.addEventListener("pointermove", mv); window.addEventListener("pointerup", up);
  };

  const hidden = slots.filter((s) => s.hidden);
  return (
    <>
      <div className="mb-3 flex flex-wrap items-center justify-end gap-2">
        {editing && <button className="btn !py-1.5 text-[12px]" onClick={() => commit(defaults)}><RotateCcw size={13} />Reset layout</button>}
        <button className={cn("btn !py-1.5 text-[12px]", editing && "btn-primary")} onClick={() => setEditing((v) => !v)} aria-pressed={editing} data-testid="customize-layout">
          {editing ? <><Check size={13} />Done</> : <><LayoutGrid size={13} />Customize layout</>}
        </button>
      </div>
      <div ref={grid} className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4" data-testid="widget-grid">
        {slots.filter((s) => !s.hidden && byId[s.id]).map((s) => (
          <motion.div layout="position" transition={{ type: "spring", stiffness: 380, damping: 36 }} key={s.id} data-widget={s.id}
            className={cn("relative min-w-0", SPAN_CLASS[s.span], editing && "widget-editing", over === s.id && drag !== s.id && "widget-over")}
            style={s.h ? { height: s.h } : undefined}
            onDragOver={(e) => { if (editing && drag) { e.preventDefault(); setOver(s.id); } }} onDragLeave={() => setOver((o) => (o === s.id ? null : o))}
            onDrop={(e) => { e.preventDefault(); drop(s.id); setDrag(null); setOver(null); }}>
            {editing && (
              <div className="absolute inset-x-2 top-2 z-20 flex items-center gap-1 rounded-xl border hairline bg-ink-900/90 px-1.5 py-1 backdrop-blur" data-testid={`widget-bar-${s.id}`}>
                <span draggable onDragStart={(e) => { setDrag(s.id); e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", s.id); }} onDragEnd={() => { setDrag(null); setOver(null); }}
                  className="cursor-grab rounded-md p-1 text-slate-300 hover:bg-white/10 active:cursor-grabbing" title="Drag to reorder" aria-label={`Drag ${byId[s.id].title}`}><GripVertical size={14} /></span>
                <span className="min-w-0 flex-1 truncate text-[11.5px] font-medium text-slate-200">{byId[s.id].title}</span>
                <button className="rounded-md p-1 text-slate-300 hover:bg-white/10" onClick={() => move(s.id, -1)} aria-label={`Move ${byId[s.id].title} earlier`}><ChevronLeft size={14} /></button>
                <button className="rounded-md p-1 text-slate-300 hover:bg-white/10" onClick={() => move(s.id, 1)} aria-label={`Move ${byId[s.id].title} later`}><ChevronRight size={14} /></button>
                <button className="rounded-md px-1.5 py-0.5 text-[11px] text-slate-300 hover:bg-white/10" onClick={() => patch(s.id, { span: Math.max(1, s.span - 1) })} aria-label={`Narrower ${byId[s.id].title}`}>−</button>
                <span className="w-3 text-center text-[11px] text-slate-400">{s.span}</span>
                <button className="rounded-md px-1.5 py-0.5 text-[11px] text-slate-300 hover:bg-white/10" onClick={() => patch(s.id, { span: Math.min(4, s.span + 1) })} aria-label={`Wider ${byId[s.id].title}`}>+</button>
                <button className="rounded-md p-1 text-slate-300 hover:bg-white/10" onClick={() => patch(s.id, { hidden: true })} aria-label={`Hide ${byId[s.id].title}`}><EyeOff size={14} /></button>
              </div>
            )}
            <div className={cn("h-full", s.h && "overflow-auto", editing && "pt-11")}>{byId[s.id].node}</div>
            {editing && <div onPointerDown={(e) => startResize(e, s)} className="absolute bottom-1 right-1 z-20 h-5 w-5 cursor-nwse-resize rounded-md border hairline bg-ink-900/90 text-slate-300" title="Drag to resize" aria-hidden><svg viewBox="0 0 20 20" className="h-5 w-5"><path d="M7 15l8-8M11 15l4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg></div>}
          </motion.div>
        ))}
      </div>
      {editing && hidden.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2 rounded-2xl border border-dashed hairline p-3" data-testid="hidden-widgets">
          <span className="eyebrow mr-1"><Eye size={11} className="mr-1 inline" />Hidden</span>
          {hidden.map((s) => byId[s.id] && <button key={s.id} className="btn !py-1 text-[12px]" onClick={() => patch(s.id, { hidden: false })}><Plus size={12} />{byId[s.id].title}</button>)}
        </div>
      )}
    </>
  );
}
