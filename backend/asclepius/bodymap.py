"""Organ-system view of a chart: which conditions, results, vitals and drugs relate to which organ."""

from __future__ import annotations

from typing import Any

from . import terminology as T
from .chart import Chart
from .clinical import lab_flag

ORGANS: dict[str, str] = {
    "brain": "Brain and nervous system", "thyroid": "Thyroid and endocrine", "lungs": "Lungs and airways", "heart": "Heart and vessels",
    "blood": "Blood and immune system", "pancreas": "Pancreas and metabolism", "gut": "Digestive tract", "kidneys": "Kidneys and urinary tract",
}
CONDITION_ORGAN = {
    "stroke": "brain", "hypothyroid": "thyroid", "cap": "lungs", "copd": "lungs", "asthma": "lungs", "pe": "lungs",
    "hf": "heart", "mi": "heart", "af": "heart", "htn": "heart", "dyslipidemia": "heart",
    "sepsis": "blood", "ida": "blood", "dengue": "blood", "t2dm": "pancreas", "obesity": "pancreas",
    "gastro": "gut", "ckd3": "kidneys", "uti": "kidneys",
}
LAB_ORGAN = {
    "glucose": "pancreas", "hba1c": "pancreas", "creatinine": "kidneys", "egfr": "kidneys", "potassium": "kidneys", "sodium": "kidneys",
    "wbc": "blood", "crp": "blood", "lactate": "blood", "hemoglobin": "blood", "platelets": "blood", "mcv": "blood", "inr": "blood", "ddimer": "blood",
    "troponin": "heart", "bnp": "heart", "ldl": "heart", "tsh": "thyroid",
}
VITAL_ORGAN = {"hr": "heart", "sbp": "heart", "dbp": "heart", "spo2": "lungs", "rr": "lungs", "o2flow": "lungs", "temp": "blood"}
CLASS_ORGAN = {
    "ccb": "heart", "acei": "heart", "arb": "heart", "statin": "heart", "beta_blocker": "heart", "antiplatelet": "heart", "anticoagulant": "heart",
    "loop_diuretic": "heart", "cardiac_glycoside": "heart", "nitrate": "heart", "saba": "lungs", "lama": "lungs", "corticosteroid": "lungs",
    "biguanide": "pancreas", "insulin": "pancreas", "ppi": "gut", "thyroid": "thyroid", "k_sparing": "kidneys", "nitrofuran": "kidneys",
}
VITAL_UNIT = {"hr": "/min", "rr": "/min", "spo2": "%", "temp": "°C", "sbp": "mmHg", "dbp": "mmHg", "o2flow": "L/min"}
VITAL_NAME = {"hr": "Heart rate", "rr": "Respiratory rate", "spo2": "SpO₂", "temp": "Temperature", "sbp": "Systolic BP", "dbp": "Diastolic BP", "o2flow": "Oxygen flow"}
VITAL_RANGE = {"hr": (51, 90), "rr": (12, 20), "spo2": (96, 100), "temp": (36.1, 38.0), "sbp": (111, 219), "dbp": (50, 100)}


def _vital_flag(name: str, v: float) -> str:
    if name not in VITAL_RANGE:
        return "normal"
    lo, hi = VITAL_RANGE[name]
    return "low" if v < lo else "high" if v > hi else "normal"


def body_map(chart: Chart) -> dict[str, Any]:
    organs: dict[str, dict[str, Any]] = {k: {"key": k, "label": lab, "conditions": [], "labs": [], "vitals": [], "meds": [], "status": "clear"} for k, lab in ORGANS.items()}
    for c in chart.conditions:
        organ = CONDITION_ORGAN.get(c.get("key") or "")
        if organ:
            organs[organ]["conditions"].append({"id": c["id"], "display": c["display"], "onset": c["onset"]})
    for key, rows in chart.labs.items():
        organ = LAB_ORGAN.get(key)
        if not organ:
            continue
        val = rows[-1][1]
        organs[organ]["labs"].append({"key": key, "name": T.LABS[key]["display"].split(" [")[0].split(" (")[0], "value": val, "unit": T.LABS[key]["unit"], "flag": lab_flag(key, val, chart.sex)})
    for name, series in chart.vitals.items():
        organ = VITAL_ORGAN.get(name)
        if organ and series:
            v = series[-1][1]
            organs[organ]["vitals"].append({"key": name, "name": VITAL_NAME[name], "value": v, "unit": VITAL_UNIT[name], "flag": _vital_flag(name, v)})
    if chart.acvpu:
        level = chart.acvpu[-1][1]
        organs["brain"]["vitals"].append({"key": "acvpu", "name": "Consciousness", "value": level, "unit": "", "flag": "normal" if level == "Alert" else "high"})
    for m in chart.meds:
        cls = T.MEDS.get(m.get("key") or "", {}).get("cls")
        organ = CLASS_ORGAN.get(cls or "")
        if organ:
            organs[organ]["meds"].append({"id": m["id"], "display": m["display"], "sig": m["sig"]})
    for o in organs.values():
        if any(x["flag"].startswith("critical") for x in o["labs"]):
            o["status"] = "critical"
        elif o["conditions"] or any(x["flag"] != "normal" for x in o["labs"] + o["vitals"]):
            o["status"] = "abnormal"
        elif o["meds"]:
            o["status"] = "watch"
    order = {"critical": 0, "abnormal": 1, "watch": 2, "clear": 3}
    return {"patient": chart.pid, "organs": list(organs.values()), "ranked": sorted(organs, key=lambda k: order[organs[k]["status"]])}
