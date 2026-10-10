"""Preventive-care and chronic-disease care gaps for one chart.

Rules are a small, documented teaching subset of common guideline items (screening, vaccination, monitoring). They are
deterministic functions of the chart, state their basis, and only ever suggest; nothing is ordered.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .chart import Chart
from .terminology import LABS

DUE, OVERDUE, MET = "due", "overdue", "met"


def _days_since(iso_ts: str | None, today: date) -> int | None:
    if not iso_ts:
        return None
    try:
        return (today - datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).date()).days
    except ValueError:
        return None


def _gap(gid: str, title: str, category: str, status: str, basis: str, detail: str) -> dict[str, Any]:
    return {"id": gid, "title": title, "category": category, "status": status, "basis": basis, "detail": detail}


def _monitoring(chart: Chart, today: date, lab: str, max_days: int, gid: str, title: str, why: str) -> dict[str, Any]:
    series = chart.labs.get(lab)
    age = _days_since(series[-1][0], today) if series else None
    name = LABS[lab]["display"].split(" [")[0]
    if age is None:
        return _gap(gid, title, "chronic", OVERDUE, why, f"No {name} on record.")
    if age > max_days:
        return _gap(gid, title, "chronic", OVERDUE, why, f"Last {name} {age} days ago (target every {max_days} days).")
    return _gap(gid, title, "chronic", MET, why, f"{name} checked {age} days ago.")


def care_gaps(chart: Chart, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    keys, a, female = chart.condition_keys(), chart.age, chart.sex.lower().startswith("f")
    gaps: list[dict[str, Any]] = []
    if a >= 65:
        gaps.append(_gap("imm-pneumococcal", "Pneumococcal vaccine", "immunisation", DUE, "Adults 65 and over", "Offer if no dose is documented."))
    if a >= 50:
        gaps.append(_gap("imm-zoster", "Recombinant zoster vaccine", "immunisation", DUE, "Adults 50 and over", "Two-dose series; confirm history."))
    if a >= 18:
        gaps.append(_gap("imm-influenza", "Seasonal influenza vaccine", "immunisation", DUE, "Annual for adults, priority if chronic disease", "Offer each season."))
    if a >= 18:
        gaps.append(_gap("imm-td", "Tetanus-diphtheria booster", "immunisation", DUE, "Every 10 years", "Confirm last booster date."))
    if 45 <= a <= 75:
        gaps.append(_gap("scr-colorectal", "Colorectal cancer screening", "screening", DUE, "Ages 45 to 75", "Stool-based test, colonoscopy or equivalent per local programme."))
    if female and 40 <= a <= 74:
        gaps.append(_gap("scr-breast", "Breast cancer screening", "screening", DUE, "Women 40 to 74", "Mammography interval per local programme."))
    if female and 21 <= a <= 65:
        gaps.append(_gap("scr-cervical", "Cervical cancer screening", "screening", DUE, "Women 21 to 65", "Cytology or HPV testing per local programme."))
    if a >= 40 and "dyslipidemia" not in keys:
        series = chart.labs.get("ldl")
        age = _days_since(series[-1][0], today) if series else None
        gaps.append(_gap("scr-lipids", "Lipid screening", "screening", MET if age is not None and age <= 1825 else DUE,
                         "Adults 40 and over, every 5 years", f"Last LDL {age} days ago." if age is not None else "No LDL on record."))
    if "t2dm" in keys:
        gaps.append(_monitoring(chart, today, "hba1c", 180, "chr-hba1c", "HbA1c monitoring", "Diabetes: at least twice yearly"))
        gaps.append(_monitoring(chart, today, "creatinine", 365, "chr-renal", "Kidney function check", "Diabetes: annual renal monitoring"))
        if not any(m.get("key") in {"atorvastatin", "rosuvastatin"} for m in chart.meds) and a >= 40:
            gaps.append(_gap("chr-statin", "Statin therapy review", "chronic", OVERDUE, "Diabetes aged 40 and over", "No statin on the active medication list."))
    if "htn" in keys and chart.latest_vital("sbp") is not None:
        sbp, dbp = chart.latest_vital("sbp"), chart.latest_vital("dbp") or 0
        ok = sbp < 140 and dbp < 90
        gaps.append(_gap("chr-bp", "Blood pressure control", "chronic", MET if ok else OVERDUE, "Hypertension: below 140/90",
                         f"Latest {sbp:g}/{dbp:g} mmHg."))
    if "af" in keys and not any(m.get("key") in {"warfarin", "enoxaparin"} for m in chart.meds):
        gaps.append(_gap("chr-anticoag", "Anticoagulation review", "chronic", OVERDUE, "Atrial fibrillation: stroke prevention", "No anticoagulant on the active list; assess CHA2DS2-VASc."))
    if keys & {"mi", "stroke"} and not any(m.get("key") in {"atorvastatin", "rosuvastatin"} for m in chart.meds):
        gaps.append(_gap("chr-secondary", "Secondary prevention statin", "chronic", OVERDUE, "Prior MI or stroke", "No statin on the active medication list."))
    if "hypothyroid" in keys:
        gaps.append(_monitoring(chart, today, "tsh", 365, "chr-tsh", "TSH monitoring", "Hypothyroidism: at least annual"))
    if "ckd3" in keys:
        gaps.append(_monitoring(chart, today, "egfr", 180, "chr-egfr", "eGFR monitoring", "CKD stage 3: at least twice yearly"))
    order = {OVERDUE: 0, DUE: 1, MET: 2}
    gaps.sort(key=lambda g: (order[g["status"]], g["category"], g["id"]))
    open_n = sum(1 for g in gaps if g["status"] != MET)
    return {"patient": chart.pid, "as_of": today.isoformat(), "open": open_n, "met": len(gaps) - open_n, "gaps": gaps,
            "note": "Teaching subset of guideline items. Vaccination history is not stored, so immunisations are listed as due to confirm."}
