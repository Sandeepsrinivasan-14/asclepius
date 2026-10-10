"""Bedside clinical calculators. Pure functions; every result carries its inputs, components and a plain-language band."""

from __future__ import annotations

import math
from typing import Any


def _need(vals: dict[str, Any], *names: str) -> None:
    missing = [n for n in names if vals.get(n) is None]
    if missing:
        raise ValueError(f"Missing input: {', '.join(missing)}")


def cha2ds2_vasc(v: dict[str, Any]) -> dict[str, Any]:
    _need(v, "age", "sex")
    age = float(v["age"])
    parts = {
        "Congestive heart failure": 1 if v.get("chf") else 0,
        "Hypertension": 1 if v.get("hypertension") else 0,
        "Age 75 or older": 2 if age >= 75 else 0,
        "Diabetes": 1 if v.get("diabetes") else 0,
        "Stroke, TIA or thromboembolism": 2 if v.get("stroke") else 0,
        "Vascular disease": 1 if v.get("vascular") else 0,
        "Age 65 to 74": 1 if 65 <= age < 75 else 0,
        "Female sex": 1 if str(v["sex"]).lower().startswith("f") else 0,
    }
    score = sum(parts.values())
    female = parts["Female sex"] == 1
    threshold = 3 if female else 2
    band = "low" if score == (1 if female else 0) else "moderate" if score == (2 if female else 1) else "high"
    advice = "Oral anticoagulation is generally recommended." if score >= threshold else "Anticoagulation is not routinely indicated; consider individual factors."
    return {"name": "CHA2DS2-VASc", "score": score, "max": 9, "band": band, "components": parts, "interpretation": advice}


def curb65(v: dict[str, Any]) -> dict[str, Any]:
    _need(v, "age", "urea_mmol_l", "resp_rate", "sbp", "dbp")
    parts = {
        "Confusion": 1 if v.get("confusion") else 0,
        "Urea above 7 mmol/L": 1 if float(v["urea_mmol_l"]) > 7 else 0,
        "Respiratory rate 30 or more": 1 if float(v["resp_rate"]) >= 30 else 0,
        "Low blood pressure (SBP below 90 or DBP 60 or below)": 1 if float(v["sbp"]) < 90 or float(v["dbp"]) <= 60 else 0,
        "Age 65 or older": 1 if float(v["age"]) >= 65 else 0,
    }
    score = sum(parts.values())
    band, advice = (("low", "Consider home treatment."), ("moderate", "Consider hospital-supervised treatment."), ("high", "Severe pneumonia: urgent admission, consider critical care."))[0 if score <= 1 else 1 if score == 2 else 2]
    return {"name": "CURB-65", "score": score, "max": 5, "band": band, "components": parts, "interpretation": advice}


def cockcroft_gault(v: dict[str, Any]) -> dict[str, Any]:
    _need(v, "age", "sex", "weight_kg", "creatinine_mg_dl")
    if float(v["creatinine_mg_dl"]) <= 0:
        raise ValueError("Creatinine must be positive")
    crcl = (140 - float(v["age"])) * float(v["weight_kg"]) / (72 * float(v["creatinine_mg_dl"]))
    if str(v["sex"]).lower().startswith("f"):
        crcl *= 0.85
    crcl = round(crcl, 1)
    band = "normal" if crcl >= 90 else "mild" if crcl >= 60 else "moderate" if crcl >= 30 else "severe"
    return {"name": "Cockcroft-Gault creatinine clearance", "score": crcl, "unit": "mL/min", "band": band,
            "interpretation": "Used by many drug labels for renal dose adjustment; compare with eGFR before dosing."}


def bmi_bsa(v: dict[str, Any]) -> dict[str, Any]:
    _need(v, "height_cm", "weight_kg")
    h, w = float(v["height_cm"]), float(v["weight_kg"])
    if h <= 0 or w <= 0:
        raise ValueError("Height and weight must be positive")
    bmi = round(w / (h / 100) ** 2, 1)
    bsa = round(math.sqrt(h * w / 3600), 2)
    band = "underweight" if bmi < 18.5 else "healthy" if bmi < 25 else "overweight" if bmi < 30 else "obese"
    return {"name": "BMI and body surface area", "score": bmi, "unit": "kg/m2", "band": band, "bsa_m2": bsa, "interpretation": "Mosteller BSA. Asian-population cut-offs for BMI are lower; use clinical judgement."}


def corrected_calcium(v: dict[str, Any]) -> dict[str, Any]:
    _need(v, "calcium_mg_dl", "albumin_g_dl")
    ca = round(float(v["calcium_mg_dl"]) + 0.8 * (4.0 - float(v["albumin_g_dl"])), 2)
    band = "low" if ca < 8.5 else "high" if ca > 10.5 else "normal"
    return {"name": "Albumin-corrected calcium", "score": ca, "unit": "mg/dL", "band": band, "interpretation": "Payne correction; unreliable in critical illness, measure ionised calcium if in doubt."}


CALCULATORS: dict[str, Any] = {
    "cha2ds2-vasc": (cha2ds2_vasc, ["age", "sex", "chf", "hypertension", "diabetes", "stroke", "vascular"]),
    "curb65": (curb65, ["age", "confusion", "urea_mmol_l", "resp_rate", "sbp", "dbp"]),
    "cockcroft-gault": (cockcroft_gault, ["age", "sex", "weight_kg", "creatinine_mg_dl"]),
    "bmi-bsa": (bmi_bsa, ["height_cm", "weight_kg"]),
    "corrected-calcium": (corrected_calcium, ["calcium_mg_dl", "albumin_g_dl"]),
}


def catalog() -> list[dict[str, Any]]:
    return [{"id": k, "inputs": inputs} for k, (_, inputs) in CALCULATORS.items()]


def run(name: str, values: dict[str, Any]) -> dict[str, Any]:
    if name not in CALCULATORS:
        raise KeyError(name)
    return CALCULATORS[name][0](values)
