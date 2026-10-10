"""Medication reconciliation: normalisation to RxNorm, duplicates, interactions, allergy and renal dosing checks.

Educational decision support for a pharmacist or physician to review. Interaction and renal rules are a
small, hand-written teaching set; they are not a substitute for a licensed drug database.
"""

from __future__ import annotations

import re
from typing import Any

from . import terminology as T
from .chart import Chart
from .clinical import egfr_ckd_epi_2021

FREQ = [("four times daily", 4), ("three times daily", 3), ("twice daily", 2), ("twice a day", 2), ("once daily", 1), ("once a day", 1), ("at night", 1), ("every morning", 1),
        ("qid", 4), ("qds", 4), ("tds", 3), ("tid", 3), ("bid", 2), ("bd", 2), ("od", 1), ("qd", 1), ("hs", 1), ("daily", 1)]
SEV_RANK = {"contraindicated": 3, "major": 2, "moderate": 1, "info": 0}

# (a tokens, b tokens, severity, effect, recommendation); tokens are ingredient keys or drug classes
INTERACTIONS: list[tuple[set[str], set[str], str, str, str]] = [
    ({"warfarin"}, {"antiplatelet"}, "major", "Additive bleeding risk.", "Confirm the indication for both; add gastro-protection and monitor INR and bleeding."),
    ({"warfarin"}, {"nsaid"}, "major", "NSAIDs raise bleeding risk and can raise INR.", "Avoid NSAIDs; prefer paracetamol. Monitor INR if unavoidable."),
    ({"warfarin"}, {"ciprofloxacin", "azithromycin"}, "major", "Antibiotics can raise INR markedly.", "Check INR within 3-5 days of starting; consider dose adjustment."),
    ({"acei"}, {"arb"}, "major", "Dual RAAS blockade: hyperkalaemia and acute kidney injury.", "Avoid the combination; keep one agent."),
    ({"potassium_chloride"}, {"k_sparing", "acei", "arb"}, "major", "Hyperkalaemia.", "Check potassium before and after; avoid routine supplements with these agents."),
    ({"antiplatelet"}, {"anticoagulant"}, "major", "Bleeding risk with antiplatelet plus anticoagulant.", "Confirm intent (for example after ACS); review duration and gastro-protection."),
    ({"warfarin"}, {"enoxaparin"}, "moderate", "Two anticoagulants: valid only during planned bridging.", "Confirm bridging plan and stop date; monitor INR and platelets."),
    ({"nsaid"}, {"acei", "arb"}, "moderate", "NSAIDs blunt antihypertensive effect and can injure the kidney.", "Avoid NSAIDs; monitor creatinine and blood pressure."),
    ({"digoxin"}, {"loop_diuretic"}, "moderate", "Loop diuretics lower potassium and magnesium, increasing digoxin toxicity.", "Monitor potassium and digoxin level."),
    ({"digoxin"}, {"beta_blocker"}, "moderate", "Additive AV-nodal slowing: bradycardia or heart block.", "Monitor heart rate and ECG."),
    ({"clopidogrel"}, {"omeprazole"}, "moderate", "Omeprazole reduces clopidogrel activation (CYP2C19).", "Prefer pantoprazole if a PPI is needed."),
    ({"sildenafil"}, {"nitrate"}, "contraindicated", "Profound hypotension.", "Do not co-prescribe."),
    ({"ciprofloxacin"}, {"corticosteroid"}, "moderate", "Increased risk of tendon rupture.", "Counsel the patient; consider an alternative antibiotic."),
    ({"aspirin"}, {"clopidogrel"}, "info", "Dual antiplatelet therapy.", "Expected after acute coronary syndrome or stent; confirm duration and add a PPI."),
]


def _tokens(key: str) -> set[str]:
    m = T.MEDS[key]
    toks = {key, m["cls"]}
    if m["cls"] in ("acei", "arb", "k_sparing", "loop_diuretic"):
        toks.add("diuretic" if "diuretic" in m["cls"] or m["cls"] == "k_sparing" else m["cls"])
    if key == "aspirin" or m["cls"] == "antiplatelet":
        toks.add("antiplatelet")
    if m["cls"] == "anticoagulant":
        toks.add("anticoagulant")
    if m["cls"] == "nitrate":
        toks.add("nitrate")
    return toks


def parse_line(raw: str, source: str) -> dict[str, Any]:
    text = raw.strip()
    low = text.lower()
    key = None
    for k, m in T.MEDS.items():
        names = [m["display"].split(" (")[0].lower(), *m["brands"]]
        if k == "insulin_glargine":
            names.append("insulin")
        for n in sorted(names, key=len, reverse=True):
            if re.search(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", low):
                key = k
                break
        if key:
            break
    strength = re.search(r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|units?|iu)\b", low)
    freq = None
    for token, n in FREQ:
        if re.search(r"(?<![a-z])" + re.escape(token) + r"(?![a-z])", low):
            freq = n
            break
    prn = bool(re.search(r"\bprn\b|as needed|sos", low))
    if strength is None:  # brand strength shorthand such as "Telma 40"
        m = re.search(r"\b(\d{2,4})\b", low)
        strength_val, unit = (float(m.group(1)), "mg") if m and key else (None, None)
    else:
        strength_val, unit = float(strength.group(1)), strength.group(2).lower().rstrip("s") if strength.group(2).lower().startswith("unit") else strength.group(2).lower()
    return {"raw": text, "source": source, "key": key, "display": T.MEDS[key]["display"] if key else None, "rxnorm": T.MEDS[key]["rxnorm"] if key else None,
            "strength": strength_val, "unit": unit, "freq_per_day": freq, "prn": prn, "resolved": key is not None}


RENAL: list[tuple[str, float, str, str]] = [
    ("metformin", 30, "contraindicated", "eGFR below 30: metformin is contraindicated (lactic acidosis risk). Stop and choose an alternative."),
    ("metformin", 45, "major", "eGFR 30-44: do not start; if continuing, reduce the dose (maximum about 1000 mg/day) and review benefit."),
    ("nitrofurantoin", 30, "major", "eGFR below 30: avoid nitrofurantoin (reduced efficacy and toxicity)."),
    ("enoxaparin", 30, "major", "eGFR below 30: reduce enoxaparin dose (for example 30 mg once daily for prophylaxis) and consider anti-Xa monitoring."),
    ("spironolactone", 30, "major", "eGFR below 30: high hyperkalaemia risk; avoid or monitor potassium closely."),
    ("ibuprofen", 30, "contraindicated", "eGFR below 30: avoid NSAIDs."),
    ("diclofenac", 30, "contraindicated", "eGFR below 30: avoid NSAIDs."),
    ("ibuprofen", 60, "moderate", "eGFR below 60: use NSAIDs with caution and for the shortest time."),
    ("diclofenac", 60, "moderate", "eGFR below 60: use NSAIDs with caution and for the shortest time."),
    ("digoxin", 50, "moderate", "eGFR below 50: reduce the digoxin dose and monitor levels."),
    ("ciprofloxacin", 30, "moderate", "eGFR below 30: reduce the ciprofloxacin dose."),
    ("potassium_chloride", 30, "major", "eGFR below 30: avoid potassium supplements unless monitored."),
    ("lisinopril", 30, "moderate", "eGFR below 30: start low and monitor creatinine and potassium."),
]


def context_from_chart(chart: Chart) -> dict[str, Any]:
    cr = chart.labs.get("creatinine")
    egfr = egfr_ckd_epi_2021(cr[-1][1], chart.age, chart.sex) if cr else None
    k = chart.latest_lab("potassium")
    return {"egfr": egfr, "potassium": k, "creatinine": cr[-1][1] if cr else None, "allergies": [a for a in chart.allergies if a["key"]], "age": chart.age}


def reconcile(chart: Chart, lists: list[dict[str, str]]) -> dict[str, Any]:
    ctx = context_from_chart(chart)
    lines: list[dict[str, Any]] = []
    # the hospital's own active orders are always a source
    for m in chart.meds:
        if m["status"] == "active" and m["key"]:
            lines.append({"raw": f"{m['display']} {m['sig']}", "source": "Hospital orders (FHIR)", **{k: v for k, v in parse_line(f"{m['display'].split(' (')[0]} {m['sig']}", "x").items() if k not in ('raw', 'source')}})
    for lst in lists:
        for raw in re.split(r"[\n;]+", lst.get("text", "")):
            if raw.strip():
                lines.append(parse_line(raw, lst.get("source", "Unspecified")))
    unresolved = [ln for ln in lines if not ln["resolved"]]
    by_key: dict[str, list[dict[str, Any]]] = {}
    for ln in lines:
        if ln["key"]:
            by_key.setdefault(ln["key"], []).append(ln)
    problems: list[dict[str, Any]] = []

    def add(kind: str, sev: str, drugs: list[str], msg: str, action: str) -> None:
        problems.append({"kind": kind, "severity": sev, "drugs": drugs, "message": msg, "action": action})

    # discrepancies and duplicate listings
    for key, items in by_key.items():
        sources = sorted({i["source"] for i in items})
        doses = {(i["strength"], i["freq_per_day"]) for i in items if i["strength"] and i["freq_per_day"]}
        if len(doses) > 1:
            desc = "; ".join(f"{i['source']}: {i['strength']:g} {i['unit']} x{i['freq_per_day']}/day" for i in items if i["strength"] and i["freq_per_day"])
            add("discrepancy", "major", [T.MEDS[key]["display"]], f"Dose or frequency differs between sources ({desc}).", "Verify the intended regimen with the patient and prescriber.")
        elif len(items) > len(sources):
            add("duplicate", "moderate", [T.MEDS[key]["display"]], "Listed more than once within a source (possible brand and generic duplicate).", "Remove the duplicate entry to avoid double dosing.")
    sources_all = sorted({ln["source"] for ln in lines})
    for key, items in by_key.items():
        present = {i["source"] for i in items}
        missing = [s for s in sources_all if s not in present and s != "Hospital orders (FHIR)"]
        if "Hospital orders (FHIR)" not in present and len(present) >= 1 and len(sources_all) > 1 and chart.inpatient:
            add("omission", "moderate", [T.MEDS[key]["display"]], f"On {', '.join(sorted(present))} but not among current hospital orders.", "Decide whether this is an intentional hold or an unintentional omission.")
        elif "Hospital orders (FHIR)" in present and missing:
            add("omission", "info", [T.MEDS[key]["display"]], f"Ordered in hospital but not on: {', '.join(missing)}.", "Confirm whether the community list is out of date.")
    # therapeutic duplication
    classes: dict[str, set[str]] = {}
    for key in by_key:
        classes.setdefault(T.MEDS[key]["cls"], set()).add(key)
    for cls, keys in classes.items():
        if len(keys) > 1 and cls in ("acei", "arb", "statin", "nsaid", "ppi", "beta_blocker", "ccb", "antiplatelet_x"):
            add("therapeutic_duplication", "major" if cls in ("acei", "arb", "nsaid") else "moderate", [T.MEDS[k]["display"] for k in sorted(keys)], f"Two agents from the same class ({cls}).", "Keep one agent unless a specialist intends both.")
    # interactions
    toks = {k: _tokens(k) for k in by_key}
    seen: set[tuple[str, ...]] = set()
    for a_set, b_set, sev, effect, action in INTERACTIONS:
        for ka, ta in toks.items():
            if not (ta & a_set):
                continue
            for kb, tb in toks.items():
                if ka == kb or not (tb & b_set):
                    continue
                pair = tuple(sorted((ka, kb)))
                if (pair, effect) in seen:  # type: ignore[comparison-overlap]
                    continue
                seen.add((pair, effect))  # type: ignore[arg-type]
                s = sev
                if {ka, kb} & {"spironolactone"} and ("acei" in ta | tb or "arb" in ta | tb):
                    pass
                add("interaction", s, [T.MEDS[ka]["display"], T.MEDS[kb]["display"]], effect, action)
    # RAAS + potassium-sparing escalation
    for ka in by_key:
        if T.MEDS[ka]["cls"] in ("acei", "arb"):
            for kb in by_key:
                if T.MEDS[kb]["cls"] == "k_sparing":
                    sev = "major" if (ctx["potassium"] and ctx["potassium"] > 5.0) or (ctx["egfr"] and ctx["egfr"] < 45) else "moderate"
                    add("interaction", sev, [T.MEDS[ka]["display"], T.MEDS[kb]["display"]], "Hyperkalaemia risk with RAAS blockade plus a potassium-sparing diuretic" + (f" (potassium {ctx['potassium']:g} mmol/L, eGFR {ctx['egfr']:g})." if ctx["potassium"] and ctx["egfr"] else "."), "Monitor potassium and creatinine within a week of any change.")
    # triple whammy
    for k in by_key:
        t = toks[k]
        if "nsaid" in t and any(T.MEDS[x]["cls"] in ("acei", "arb") for x in by_key) and any(T.MEDS[x]["cls"] in ("loop_diuretic", "k_sparing") for x in by_key):
            add("interaction", "major", [T.MEDS[k]["display"], "RAAS blocker", "diuretic"], "'Triple whammy' (NSAID + ACE inhibitor or ARB + diuretic): high risk of acute kidney injury.", "Stop the NSAID; use paracetamol; monitor creatinine.")
    # allergies
    for al in ctx["allergies"]:
        info = T.ALLERGENS[al["key"]]
        for key in by_key:
            cls = T.MEDS[key]["cls"]
            if cls in info["classes"]:
                add("allergy", "contraindicated", [T.MEDS[key]["display"]], f"Recorded allergy: {al['display']}. {T.MEDS[key]['display']} is in the same class.", "Do not give; choose a non-cross-reactive alternative and review the allergy record.")
            elif cls in info["cross"]:
                add("allergy", "moderate", [T.MEDS[key]["display"]], f"Recorded allergy: {al['display']}. {info['cross'][cls]}", "Document the risk assessment; monitor the first dose.")
    # renal dosing
    if ctx["egfr"] is not None:
        done: set[str] = set()
        for key, limit, sev, msg in RENAL:
            if key in by_key and ctx["egfr"] < limit and key not in done:
                done.add(key)
                add("renal", sev, [T.MEDS[key]["display"]], f"eGFR {ctx['egfr']:g} mL/min/1.73m2 (creatinine {ctx['creatinine']:g} mg/dL). {msg}", "Review dose or choose an alternative; recheck renal function.")
    problems.sort(key=lambda p: -SEV_RANK[p["severity"]])
    reconciled = []
    for key, items in by_key.items():
        related = [p for p in problems if T.MEDS[key]["display"] in p["drugs"]]
        worst = max((SEV_RANK[p["severity"]] for p in related), default=-1)
        action = "Avoid / hold pending review" if worst >= 3 else "Review before continuing" if worst == 2 else "Continue; monitor" if worst >= 0 else "Continue"
        reconciled.append({"key": key, "display": T.MEDS[key]["display"], "rxnorm": T.MEDS[key]["rxnorm"], "class": T.MEDS[key]["cls"], "sources": sorted({i["source"] for i in items}),
                           "regimens": [{"source": i["source"], "text": i["raw"], "strength": i["strength"], "unit": i["unit"], "per_day": i["freq_per_day"]} for i in items],
                           "suggested_action": action, "issues": len(related)})
    reconciled.sort(key=lambda r: (-{"Avoid / hold pending review": 3, "Review before continuing": 2, "Continue; monitor": 1, "Continue": 0}[r["suggested_action"]], r["display"]))
    counts = {s: sum(1 for p in problems if p["severity"] == s) for s in ("contraindicated", "major", "moderate", "info")}
    checklist = ["Confirm allergy history directly with the patient or carer."]
    if ctx["egfr"] is not None:
        checklist.append(f"Renal function: eGFR {ctx['egfr']:g} (CKD-EPI 2021); verify every renally cleared drug.")
    if unresolved:
        checklist.append(f"{len(unresolved)} line(s) could not be matched to a known drug; verify them manually.")
    checklist.append("Ask about over-the-counter medicines, herbal products and missed doses.")
    return {"patient": chart.pid, "context": {k: v for k, v in ctx.items() if k != "allergies"} | {"allergies": [a["display"] for a in ctx["allergies"]]},
            "reconciled": reconciled, "problems": problems, "unresolved": [u["raw"] for u in unresolved], "counts": counts, "checklist": checklist,
            "disclaimer": "Educational decision support using a small teaching rule set. A pharmacist must verify against a licensed drug database."}
