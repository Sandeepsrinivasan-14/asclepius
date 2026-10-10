"use client";
import { Modal } from "./ui";

const ROWS: [string[], string][] = [
  [["Ctrl", "K"], "Open the command palette (patients, conditions, modules)"],
  [["?"], "Show this list"],
  [["G", "D"], "Go to Command center"],
  [["G", "P"], "Go to Patients"],
  [["G", "M"], "Go to Live monitor"],
  [["G", "I"], "Go to HL7 pipeline"],
  [["G", "T"], "Go to Terminology"],
  [["G", "C"], "Go to Calculators"],
  [["T"], "Cycle theme: Aurora night, Clinic day, ICU night"],
  [["H"], "Toggle high contrast"],
  [["Esc"], "Close dialogs, drawers and the tour"],
];

export function Shortcuts({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Modal open={open} onClose={onClose} title="Keyboard shortcuts">
      <ul className="space-y-1.5" data-testid="shortcuts">
        {ROWS.map(([keys, label]) => (
          <li key={label} className="flex items-center justify-between gap-4 rounded-xl px-2 py-1.5 text-[13px] text-slate-300">
            <span>{label}</span>
            <span className="flex shrink-0 items-center gap-1">{keys.map((k, i) => <span key={k} className="flex items-center gap-1">{i > 0 && <span className="text-[10px] text-slate-500">then</span>}<kbd className="kbd">{k}</kbd></span>)}</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[11.5px] text-slate-500">Single-key shortcuts are ignored while you are typing in a field.</p>
    </Modal>
  );
}
