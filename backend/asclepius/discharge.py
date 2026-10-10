"""Discharge summary draft assembled from the chart. Template-based and deterministic; a physician must sign it."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import terminology as T
from .chart import Chart
from .clinical import egfr_ckd_epi_2021, lab_flag

WARNING_SIGNS: dict[str, list[str]] = {
    "hf": ["Weight gain of more than 2 kg in 3 days", "Worsening breathlessness or swelling of the legs"],
    "copd": ["Increasing breathlessness or a change in sputum colour", "Blue lips or confusion"],
    "asthma": ["Reliever inhaler needed more often than every 4 hours", "Unable to speak a full sentence"],
    "cap": ["Fever returning after 48 hours of treatment", "Chest pain or coughing blood"],
    "t2dm": ["Blood sugar below 70 mg/dL or above 300 mg/dL", "Persistent vomiting or extreme thirst"],
    "htn": ["Severe headache with blurred vision", "Chest pain or sudden weakness"],
    "ckd3": ["Very little urine passed in 12 hours", "Sudden swelling or breathlessness"],
    "stroke": ["New weakness, facial droop or slurred speech: call emergency services at once"],
    "mi": ["Chest pain lasting more than 10 minutes: call emergency services at once"],
    "af": ["Fast, irregular heartbeat with dizziness or fainting"],
    "sepsis": ["Fever with shivering, confusion or very fast breathing"],
    "uti": ["Fever with back pain or blood in the urine"],
}
GENERIC_SIGNS = ["Fever above 38.5 °C that does not settle", "Severe pain, fainting or sudden confusion"]
FOLLOW_UP = {
    "hf": "Cardiology in 7 days", "mi": "Cardiology in 7 days", "af": "Cardiology in 14 days", "stroke": "Neurology in 14 days",
    "ckd3": "Nephrology in 4 weeks", "t2dm": "Diabetes clinic in 4 weeks", "htn": "Primary care blood pressure check in 2 weeks",
    "copd": "Pulmonology in 2 weeks", "asthma": "Pulmonology in 4 weeks",
}


def discharge_summary(chart: Chart, attending_names: list[str]) -> dict[str, Any]:
    keys = [c["key"] for c in chart.conditions if c.get("key")]
    abnormal = []
    for key, rows in chart.labs.items():
        t, v, _ = rows[-1]
        fl = lab_flag(key, v, chart.sex)
        if fl != "normal":
            abnormal.append({"name": T.LABS[key]["display"].split(" [")[0].split(" (")[0], "value": v, "unit": T.LABS[key]["unit"], "flag": fl, "time": t})
    abnormal.sort(key=lambda r: (not r["flag"].startswith("critical"), r["name"]))
    cr = chart.labs.get("creatinine")
    renal = {"egfr": egfr_ckd_epi_2021(cr[-1][1], chart.age, chart.sex)} if cr else None
    meds = [{"display": m["display"], "sig": m["sig"], "status": m["status"]} for m in chart.meds if m.get("status") in (None, "active")]
    signs: list[str] = []
    for k in keys:
        signs += WARNING_SIGNS.get(k, [])
    signs = list(dict.fromkeys(signs + GENERIC_SIGNS))
    follow = list(dict.fromkeys(FOLLOW_UP[k] for k in keys if k in FOLLOW_UP)) or ["Primary care review in 1 to 2 weeks"]
    enc = chart.encounter or {}
    return {
        "patient": {"id": chart.pid, "name": chart.name, "age": chart.age, "sex": chart.sex, "birth_date": chart.birth},
        "encounter": {"ward": chart.ward, "bed": chart.bed, "admitted": (enc.get("period") or {}).get("start"), "reason": ((enc.get("reasonCode") or [{}])[0]).get("text", ""), "status": enc.get("status")},
        "diagnoses": [{"display": c["display"], "onset": c["onset"]} for c in chart.conditions],
        "course_note": chart.notes[0]["text"].strip().split("\n")[0][:240] if chart.notes else "",
        "abnormal_results": abnormal[:10],
        "renal_function": renal,
        "medications_on_discharge": meds,
        "allergies": [a["display"] for a in chart.allergies] or ["No known drug allergies recorded"],
        "pending_tests": [p["text"] for p in chart.pending],
        "follow_up": follow,
        "warning_signs": signs,
        "attending": attending_names,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "DRAFT: requires physician review and signature",
        "disclaimer": "Synthetic data. This draft is assembled from the chart by templates and is not a medical document.",
    }
