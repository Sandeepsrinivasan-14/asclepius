"""Shift handoff: an SBAR note generated from the last 12 hours of chart activity (rule-based, fully explainable)."""

from __future__ import annotations

from typing import Any

from . import medrec
from . import terminology as T
from .chart import Chart
from .clinical import lab_flag
from .warning import RiskModel, chart_features, chart_news2, chart_vitals_at, news2_series, qsofa, risk_tier

TREND_VARS = [("hr", "Heart rate", "/min", 8), ("rr", "Respiratory rate", "/min", 3), ("spo2", "SpO2", "%", 2), ("sbp", "Systolic BP", "mmHg", 12), ("temp", "Temperature", "C", 0.6)]


def _arrow(delta: float, thr: float) -> str:
    return "rising" if delta > thr else "falling" if delta < -thr else "stable"


def build(chart: Chart, model: RiskModel | None = None, window_h: int = 12) -> dict[str, Any]:
    n2 = chart_news2(chart)
    series = news2_series(chart, window_h + 1)
    first_score = series[0]["score"] if series else None
    trend = []
    for key, label, unit, thr in TREND_VARS:
        s = chart.vitals.get(key, [])[-(window_h + 1):]
        if len(s) >= 2:
            d = s[-1][1] - s[0][1]
            trend.append({"key": key, "label": label, "unit": unit, "from": s[0][1], "to": s[-1][1], "delta": round(d, 1), "direction": _arrow(d, thr),
                          "concerning": (key in ("hr", "rr", "temp") and d > thr) or (key in ("spo2", "sbp") and d < -thr)})
    prob = None
    tier = None
    if model is not None:
        x = chart_features(chart)
        if x is not None:
            prob = model.predict_row(x)
            tier = risk_tier(prob)
    dx = [c["display"] for c in chart.conditions if c["category"] == "encounter-diagnosis"] or [c["display"] for c in chart.conditions][:2]
    chronic = [c["display"] for c in chart.conditions if c["category"] == "problem-list-item"]
    reason = (chart.encounter or {}).get("reasonCode", [{}])[0].get("text", "")
    v = chart.latest_vitals()
    q = qsofa(chart_vitals_at(chart) or {"rr": 16, "sbp": 120, "acvpu": "Alert"})
    new_labs = []
    for key, rows in chart.labs.items():
        if len(rows) >= 1:
            val = rows[-1][1]
            flag = lab_flag(key, val, chart.sex)
            prev = rows[-2][1] if len(rows) > 1 else None
            if flag != "normal" and key != "egfr":
                new_labs.append({"key": key, "label": T.LABS[key]["display"].split(" [")[0].split(" (")[0], "value": val, "unit": T.LABS[key]["unit"], "flag": flag, "previous": prev, "time": rows[-1][0]})
    new_labs.sort(key=lambda r: (0 if "critical" in r["flag"] else 1, r["label"]))
    mr = medrec.reconcile(chart, [])
    renal = [p for p in mr["problems"] if p["kind"] in ("renal", "allergy") and p["severity"] in ("major", "contraindicated")]
    situation = (f"{chart.name}, {chart.age}-year-old {chart.sex}, {chart.ward or 'outpatient'}{(' bed ' + chart.bed) if chart.bed else ''}. "
                 + (f"Admitted with {reason or ', '.join(dx)}. " if chart.inpatient else "")
                 + (f"NEWS2 is {n2['score']} ({n2['risk']} risk)" if n2 else "No recent observations")
                 + (f", was {first_score} {window_h} hours ago." if first_score is not None and n2 else "."))
    background = {"admitted": (chart.encounter or {}).get("period", {}).get("start"), "diagnoses": dx, "history": chronic,
                  "allergies": [a["display"] for a in chart.allergies] or ["No known drug allergies"], "medications": [f"{m['display']} {m['sig']}" for m in chart.meds if m["status"] == "active"]}
    recs: list[dict[str, str]] = []
    if n2:
        recs.append({"rule": "news2.response", "text": f"{n2['response']} Monitoring: {n2['frequency'].lower()}."})
        if first_score is not None and n2["score"] - first_score >= 2:
            recs.append({"rule": "news2.trend", "text": f"NEWS2 has risen by {n2['score'] - first_score} points in {window_h} hours: request senior review even if the current band looks acceptable."})
        if first_score is not None and first_score - n2["score"] >= 3:
            recs.append({"rule": "news2.improving", "text": "NEWS2 is falling steadily: consider step-down and review of IV therapy."})
    if q["score"] >= 2:
        recs.append({"rule": "qsofa", "text": "qSOFA is 2 or more: confirm sepsis screening and antimicrobial timing per local protocol."})
    for lab in new_labs:
        if lab["key"] == "lactate" and lab["flag"] != "normal":
            recs.append({"rule": "lactate", "text": f"Lactate {lab['value']:g} mmol/L: repeat as ordered and reassess perfusion."})
        if lab["key"] == "potassium" and lab["flag"] in ("high", "critical-high"):
            recs.append({"rule": "potassium", "text": f"Potassium {lab['value']:g} mmol/L: repeat, review ECG and potassium-raising drugs."})
        if lab["key"] == "potassium" and lab["flag"] in ("low", "critical-low"):
            recs.append({"rule": "potassium", "text": f"Potassium {lab['value']:g} mmol/L: replace per protocol and recheck."})
        if lab["key"] == "platelets" and lab["flag"] != "normal":
            recs.append({"rule": "platelets", "text": f"Platelets {lab['value']:g}: follow the daily count; review bleeding precautions and avoid NSAIDs."})
    for p in renal[:3]:
        recs.append({"rule": f"medrec.{p['kind']}", "text": f"{', '.join(p['drugs'])}: {p['message']}"})
    for r in chart.pending:
        recs.append({"rule": "pending.order", "text": f"Pending: {r['text']}."})
    if not recs:
        recs.append({"rule": "default", "text": "Continue routine care and monitoring."})
    assessment = {"news2": n2, "news2_first": first_score, "qsofa": q, "ml_risk": None if prob is None else {"probability": round(prob, 3), "tier": tier}, "vitals": {k: v[k] for k in ("hr", "rr", "spo2", "temp", "sbp", "dbp")} | {"acvpu": v["acvpu"], "o2_l_min": v["o2flow"]},
                  "trends": trend, "abnormal_labs": new_labs[:8]}
    return {"patient": chart.pid, "name": chart.name, "ward": chart.ward, "bed": chart.bed, "window_hours": window_h, "situation": situation, "background": background,
            "assessment": assessment, "recommendation": recs, "acuity": (n2["score"] if n2 else 0), "generated_from": "FHIR chart, last %d hours" % window_h}


def to_text(s: dict[str, Any]) -> str:
    a = s["assessment"]
    lines = [f"SBAR HANDOFF: {s['name']} ({s['ward'] or 'OPD'} {s['bed'] or ''})".strip(), "", "S  " + s["situation"], "",
             "B  Diagnoses: " + "; ".join(s["background"]["diagnoses"] or ["none recorded"]), "   History: " + "; ".join(s["background"]["history"] or ["none"]),
             "   Allergies: " + "; ".join(s["background"]["allergies"]), "   Medications: " + "; ".join(s["background"]["medications"] or ["none"]), ""]
    if a["news2"]:
        v = a["vitals"]
        lines.append(f"A  NEWS2 {a['news2']['score']} ({a['news2']['risk']}). HR {v['hr']:.0f}, RR {v['rr']:.0f}, SpO2 {v['spo2']:.0f}%, BP {v['sbp']:.0f}/{v['dbp']:.0f}, T {v['temp']:.1f} C, {v['acvpu']}.")
    for t in a["trends"]:
        lines.append(f"   {t['label']}: {t['from']:g} -> {t['to']:g} {t['unit']} ({t['direction']})")
    lines.append("")
    for r in s["recommendation"]:
        lines.append("R  - " + r["text"])
    return "\n".join(lines)


def ward_handoff(charts: list[Chart], model: RiskModel | None, ward: str) -> dict[str, Any]:
    items = [build(c, model) for c in charts if c.ward == ward]
    items.sort(key=lambda s: -s["acuity"])
    return {"ward": ward, "patients": items, "count": len(items), "high_acuity": sum(1 for i in items if i["acuity"] >= 5)}
