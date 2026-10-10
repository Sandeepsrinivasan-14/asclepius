"""Deterministic synthetic cohort generator (FHIR R4 resources).

Everything produced here is fabricated. Names are random combinations, identifiers are
generated, and no real person, hospital or organisation is represented.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from . import abdm
from . import terminology as T
from .clinical import age_years, egfr_ckd_epi_2021
from .db import Store, iso
from .fhir import codeable, encode_text, ref

FIRST_M = ["Arjun", "Karthik", "Ravi", "Suresh", "Vikram", "Mohan", "Rajesh", "Harish", "Naveen", "Imran", "Joseph", "Gurpreet", "Anil", "Sanjay", "Prakash", "Dinesh", "Faisal", "Manoj"]
FIRST_F = ["Priya", "Meena", "Lakshmi", "Anitha", "Divya", "Kavya", "Sneha", "Pooja", "Deepa", "Fatima", "Mary", "Simran", "Sunita", "Revathi", "Nandini", "Shalini", "Aisha", "Geetha"]
LAST = ["Iyer", "Nair", "Reddy", "Sharma", "Khan", "Pillai", "Das", "Menon", "Gupta", "Singh", "Rao", "Kumar", "Fernandes", "Naidu", "Bose", "Joshi", "Thomas", "Mehta"]
CITIES = ["Chennai", "Coimbatore", "Madurai", "Bengaluru", "Hyderabad", "Kochi", "Pune", "Visakhapatnam"]

WARDS = {
    "ICU": {"name": "Intensive Care Unit", "beds": 12},
    "CCU": {"name": "Cardiac Care Unit", "beds": 8},
    "MED": {"name": "General Medicine Ward", "beds": 24},
    "NEURO": {"name": "Neurology Ward", "beds": 10},
}

PRACTITIONERS = [
    {"id": "prac-rao", "name": "Dr. Meera Rao", "dept": "medicine", "role": "physician"},
    {"id": "prac-chandran", "name": "Dr. Arvind Chandran", "dept": "cardiology", "role": "physician"},
    {"id": "prac-fernandes", "name": "Dr. Lena Fernandes", "dept": "neurology", "role": "physician"},
    {"id": "prac-devi", "name": "Devi Subramanian, RN", "dept": "ICU", "role": "nurse"},
    {"id": "prac-meena", "name": "Meena Joseph, RN", "dept": "MED", "role": "nurse"},
    {"id": "prac-iyer", "name": "Ramesh Iyer, PharmD", "dept": "pharmacy", "role": "pharmacist"},
]
ATTENDING_BY_DEPT = {"medicine": "prac-rao", "cardiology": "prac-chandran", "neurology": "prac-fernandes"}


@dataclass
class Scenario:
    key: str
    label: str
    conditions: list[str]
    pos: list[tuple[str, float]]  # (symptom, probability)
    neg: list[str]
    meds: list[tuple[str, str]]
    dept: str
    age: tuple[int, int]
    sick: dict[str, float]
    well: dict[str, float]
    labs: dict[str, tuple[float, float]] = field(default_factory=dict)  # well, sick
    impression: str = ""
    pending: list[str] = field(default_factory=list)


V_WELL = {"hr": 76, "rr": 16, "spo2": 97, "sbp": 122, "dbp": 78, "temp": 36.8}


def S(**kw: Any) -> Scenario:
    return Scenario(**kw)


SCENARIOS: dict[str, Scenario] = {s.key: s for s in [
    S(key="cap", label="Community-acquired pneumonia", conditions=["cap"], pos=[("fever", 1), ("cough", 1), ("productive_cough", .8), ("dyspnea", .8), ("pleuritic_pain", .5), ("fatigue", .5)],
      neg=["hemoptysis", "edema", "calf_swelling"], meds=[("ceftriaxone", "1 g IV once daily"), ("azithromycin", "500 mg PO once daily"), ("paracetamol", "650 mg PO TDS PRN")],
      dept="medicine", age=(35, 82), sick={"hr": 112, "rr": 26, "spo2": 90, "sbp": 108, "dbp": 66, "temp": 38.9}, well=V_WELL,
      labs={"wbc": (8, 17.5), "crp": (4, 165), "creatinine": (.9, 1.1), "sodium": (139, 133), "lactate": (1.0, 2.3)},
      impression="Right lower zone consolidation, features of community-acquired pneumonia.", pending=["Sputum culture", "Repeat chest radiograph"]),
    S(key="sepsis", label="Sepsis (urinary source)", conditions=["sepsis", "uti"], pos=[("fever", 1), ("confusion", .7), ("dysuria", .6), ("fatigue", .6), ("flank_pain", .4)],
      neg=["cough", "chest_pain"], meds=[("ceftriaxone", "2 g IV once daily"), ("paracetamol", "650 mg PO TDS PRN"), ("enoxaparin", "40 mg SC once daily")],
      dept="medicine", age=(45, 85), sick={"hr": 128, "rr": 28, "spo2": 91, "sbp": 84, "dbp": 48, "temp": 39.4}, well=V_WELL,
      labs={"wbc": (8, 22), "crp": (4, 215), "lactate": (1.0, 4.6), "creatinine": (.9, 2.5), "platelets": (250, 95), "potassium": (4.2, 5.1), "sodium": (139, 132), "glucose": (100, 168), "hemoglobin": (13.5, 10.6)},
      impression="Sepsis, probable urinary source; organ dysfunction (renal, hypotension).", pending=["Blood cultures x2", "Urine culture", "Repeat lactate in 6 hours"]),
    S(key="mi", label="Acute myocardial infarction", conditions=["mi", "htn"], pos=[("chest_pain", 1), ("radiating_pain", .8), ("diaphoresis", .8), ("dyspnea", .5)],
      neg=["fever", "cough"], meds=[("aspirin", "75 mg PO once daily"), ("clopidogrel", "75 mg PO once daily"), ("atorvastatin", "80 mg PO at night"), ("metoprolol", "25 mg PO BD"), ("pantoprazole", "40 mg PO once daily"), ("enoxaparin", "60 mg SC BD")],
      dept="cardiology", age=(42, 80), sick={"hr": 104, "rr": 22, "spo2": 94, "sbp": 150, "dbp": 92, "temp": 37.2}, well=V_WELL,
      labs={"troponin": (.01, 2.1), "ldl": (110, 150), "creatinine": (1.0, 1.2), "glucose": (110, 150), "potassium": (4.3, 4.4)},
      impression="Acute coronary syndrome, troponin positive; for angiography.", pending=["Serial troponin", "Echocardiogram"]),
    S(key="hf", label="Decompensated heart failure", conditions=["hf", "htn"], pos=[("dyspnea", 1), ("orthopnea", .8), ("edema", .9), ("fatigue", .8), ("cough", .4), ("weight_gain", .5)],
      neg=["chest_pain", "fever"], meds=[("furosemide", "40 mg IV BD"), ("spironolactone", "25 mg PO once daily"), ("metoprolol", "12.5 mg PO BD"), ("lisinopril", "5 mg PO once daily"), ("enoxaparin", "40 mg SC once daily")],
      dept="cardiology", age=(55, 88), sick={"hr": 102, "rr": 24, "spo2": 90, "sbp": 134, "dbp": 82, "temp": 36.9}, well=V_WELL,
      labs={"bnp": (90, 1850), "creatinine": (1.0, 1.7), "sodium": (139, 131), "potassium": (4.2, 4.9), "hemoglobin": (13.5, 11.4)},
      impression="Acute decompensated heart failure with volume overload.", pending=["Daily weights", "Echocardiogram"]),
    S(key="copd", label="COPD exacerbation", conditions=["copd"], pos=[("dyspnea", 1), ("wheeze", .9), ("productive_cough", .8), ("smoker", 1)],
      neg=["chest_pain", "edema"], meds=[("salbutamol", "2.5 mg nebulised QID"), ("tiotropium", "18 mcg inhaled once daily"), ("prednisolone", "40 mg PO once daily"), ("azithromycin", "500 mg PO once daily"), ("pantoprazole", "40 mg PO once daily")],
      dept="medicine", age=(55, 84), sick={"hr": 108, "rr": 27, "spo2": 87, "sbp": 138, "dbp": 82, "temp": 37.4}, well={**V_WELL, "spo2": 92},
      labs={"wbc": (8, 12.8), "crp": (4, 42), "hemoglobin": (14.5, 16)},
      impression="Acute exacerbation of COPD; target saturations 88-92%.", pending=["Arterial blood gas"]),
    S(key="stroke", label="Ischaemic stroke", conditions=["stroke", "htn", "af"], pos=[("weakness_unilateral", 1), ("speech_difficulty", .85), ("headache", .5), ("confusion", .4)],
      neg=["chest_pain", "fever"], meds=[("aspirin", "300 mg PO once daily"), ("atorvastatin", "40 mg PO at night"), ("amlodipine", "5 mg PO once daily")],
      dept="neurology", age=(52, 88), sick={"hr": 92, "rr": 18, "spo2": 95, "sbp": 176, "dbp": 100, "temp": 37.1}, well={**V_WELL, "sbp": 140, "dbp": 85},
      labs={"glucose": (100, 168), "ldl": (110, 145), "creatinine": (1.0, 1.1)},
      impression="Acute ischaemic stroke, left MCA territory; outside thrombolysis window.", pending=["MRI brain", "Carotid Doppler"]),
    S(key="dengue", label="Dengue fever", conditions=["dengue"], pos=[("fever", 1), ("myalgia", .9), ("retro_orbital_pain", .7), ("headache", .8), ("rash", .5), ("vomiting", .4)],
      neg=["cough", "dysuria"], meds=[("paracetamol", "650 mg PO QID")],
      dept="medicine", age=(18, 60), sick={"hr": 104, "rr": 20, "spo2": 96, "sbp": 104, "dbp": 66, "temp": 39.2}, well=V_WELL,
      labs={"platelets": (250, 42), "wbc": (7, 2.8), "hemoglobin": (13.5, 16.2), "crp": (4, 28)},
      impression="Dengue fever, critical phase; monitor platelets and haematocrit.", pending=["Daily platelet count"]),
    S(key="ckd_dm", label="Diabetic CKD", conditions=["t2dm", "htn", "ckd3"], pos=[("fatigue", .9), ("edema", .6), ("polyuria", .4)],
      neg=["chest_pain", "fever"], meds=[("insulin_glargine", "10 units SC at night"), ("amlodipine", "5 mg PO once daily"), ("furosemide", "20 mg PO once daily"), ("metformin", "500 mg PO BD")],
      dept="medicine", age=(55, 80), sick={"hr": 88, "rr": 18, "spo2": 96, "sbp": 156, "dbp": 92, "temp": 36.9}, well={**V_WELL, "sbp": 140},
      labs={"creatinine": (1.4, 2.0), "potassium": (4.4, 5.4), "hemoglobin": (13, 10.2), "glucose": (130, 215), "hba1c": (6.8, 8.6)},
      impression="Diabetic kidney disease; review renally cleared drugs.", pending=["Urine albumin-creatinine ratio"]),
    S(key="gastro", label="Acute gastroenteritis", conditions=["gastro"], pos=[("diarrhea", 1), ("vomiting", .8), ("fever", .5)],
      neg=["dysuria", "chest_pain"], meds=[("pantoprazole", "40 mg PO once daily")],
      dept="medicine", age=(20, 70), sick={"hr": 108, "rr": 20, "spo2": 97, "sbp": 98, "dbp": 62, "temp": 38.0}, well=V_WELL,
      labs={"sodium": (139, 131), "potassium": (4.1, 3.1), "creatinine": (.9, 1.6), "wbc": (7, 13)},
      impression="Acute gastroenteritis with dehydration; oral and IV rehydration.", pending=["Stool routine"]),
    S(key="pe", label="Pulmonary embolism", conditions=["pe"], pos=[("dyspnea", 1), ("pleuritic_pain", .8), ("calf_swelling", .7), ("hemoptysis", .3)],
      neg=["fever", "cough"], meds=[("enoxaparin", "80 mg SC BD"), ("warfarin", "5 mg PO once daily")],
      dept="medicine", age=(30, 78), sick={"hr": 118, "rr": 26, "spo2": 89, "sbp": 112, "dbp": 70, "temp": 37.3}, well=V_WELL,
      labs={"ddimer": (.2, 3.9), "troponin": (.01, .09), "wbc": (7, 11)},
      impression="Acute pulmonary embolism, intermediate risk; anticoagulated.", pending=["CT pulmonary angiogram report"]),
    S(key="chronic_dm_htn", label="Diabetes with hypertension", conditions=["t2dm", "htn", "dyslipidemia"], pos=[("polyuria", .7), ("polydipsia", .6), ("fatigue", .5), ("headache", .3)],
      neg=["chest_pain"], meds=[("metformin", "500 mg PO BD"), ("amlodipine", "5 mg PO once daily"), ("telmisartan", "40 mg PO once daily"), ("atorvastatin", "10 mg PO at night"), ("aspirin", "75 mg PO once daily")],
      dept="medicine", age=(40, 75), sick={"hr": 82, "rr": 16, "spo2": 98, "sbp": 150, "dbp": 92, "temp": 36.8}, well=V_WELL,
      labs={"hba1c": (6.5, 8.6), "glucose": (110, 195), "creatinine": (.9, 1.1), "ldl": (100, 142)},
      impression="Type 2 diabetes with suboptimal control; hypertension above target."),
    S(key="ida", label="Iron deficiency anaemia", conditions=["ida"], pos=[("fatigue", 1), ("pallor", .9), ("dyspnea", .4)],
      neg=["chest_pain"], meds=[], dept="medicine", age=(20, 55), sick={"hr": 96, "rr": 18, "spo2": 98, "sbp": 108, "dbp": 68, "temp": 36.7}, well=V_WELL,
      labs={"hemoglobin": (13, 7.9), "mcv": (88, 68)}, impression="Microcytic anaemia, probable iron deficiency."),
    S(key="asthma", label="Asthma", conditions=["asthma"], pos=[("wheeze", 1), ("cough", .8), ("dyspnea", .7)],
      neg=["fever"], meds=[("salbutamol", "2 puffs inhaled PRN")], dept="medicine", age=(12, 55), sick={"hr": 96, "rr": 20, "spo2": 96, "sbp": 118, "dbp": 74, "temp": 36.8}, well=V_WELL,
      impression="Mild persistent asthma."),
    S(key="hypothyroid", label="Hypothyroidism", conditions=["hypothyroid"], pos=[("fatigue", 1), ("weight_gain", .8), ("cold_intolerance", .7)],
      neg=["palpitations"], meds=[("levothyroxine", "75 mcg PO once daily")], dept="medicine", age=(30, 70), sick={"hr": 58, "rr": 15, "spo2": 98, "sbp": 124, "dbp": 82, "temp": 36.4}, well=V_WELL,
      labs={"tsh": (2.0, 12.5)}, impression="Primary hypothyroidism, under-replaced."),
    S(key="af", label="Atrial fibrillation on anticoagulation", conditions=["af", "htn"], pos=[("palpitations", 1), ("fatigue", .6), ("dyspnea", .4)],
      neg=["chest_pain"], meds=[("warfarin", "3 mg PO once daily"), ("metoprolol", "50 mg PO BD"), ("digoxin", "0.125 mg PO once daily")], dept="cardiology", age=(55, 85), sick={"hr": 112, "rr": 17, "spo2": 97, "sbp": 132, "dbp": 80, "temp": 36.8}, well={**V_WELL, "hr": 84},
      labs={"inr": (2.4, 2.6)}, impression="Atrial fibrillation, rate control suboptimal."),
    S(key="healthy", label="Routine check-up", conditions=[], pos=[], neg=["chest_pain", "fever", "cough"], meds=[], dept="medicine", age=(20, 60), sick=V_WELL, well=V_WELL,
      labs={"glucose": (92, 92), "hba1c": (5.3, 5.3), "ldl": (95, 95), "hemoglobin": (14, 14), "creatinine": (.9, .9)}, impression="No acute concerns."),
]}

INPATIENT_PLAN: list[tuple[str, str, str]] = [
    # scenario, ward, trajectory
    ("sepsis", "ICU", "critical"), ("sepsis", "ICU", "deteriorating"), ("cap", "ICU", "deteriorating"), ("copd", "ICU", "stable"),
    ("cap", "ICU", "improving"), ("pe", "ICU", "stable"),
    ("mi", "CCU", "stable"), ("mi", "CCU", "improving"), ("hf", "CCU", "deteriorating"), ("hf", "CCU", "improving"), ("mi", "CCU", "stable"), ("hf", "CCU", "stable"),
    ("cap", "MED", "stable"), ("cap", "MED", "improving"), ("dengue", "MED", "deteriorating"), ("dengue", "MED", "stable"), ("dengue", "MED", "improving"),
    ("ckd_dm", "MED", "stable"), ("ckd_dm", "MED", "deteriorating"), ("gastro", "MED", "improving"), ("gastro", "MED", "stable"), ("copd", "MED", "improving"),
    ("sepsis", "MED", "improving"), ("cap", "MED", "stable"), ("gastro", "MED", "improving"),
    ("stroke", "NEURO", "stable"), ("stroke", "NEURO", "improving"),
]
OUTPATIENT_CYCLE = ["chronic_dm_htn", "ida", "asthma", "hypothyroid", "af", "chronic_dm_htn", "healthy", "ckd_dm", "chronic_dm_htn", "asthma", "hypothyroid", "healthy", "ida", "af"]


def _smooth(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def severity(traj: str, frac: float) -> float:
    if traj == "improving":
        return 1.0 - 0.85 * frac
    if traj == "stable":
        return 0.5
    if traj == "deteriorating":
        return 0.3 + 0.7 * _smooth((frac - 0.35) / 0.65)
    return 0.5 + 0.4 * frac  # critical


def _ack(rng: random.Random, value: float, sd: float, lo: float, hi: float, nd: int = 0) -> float:
    return round(max(lo, min(hi, value + rng.gauss(0, sd))), nd)


@dataclass
class Cohort:
    truth: dict[str, str] = field(default_factory=dict)  # patient id -> scenario key (never exposed via API)
    trajectory: dict[str, str] = field(default_factory=dict)
    ward: dict[str, str] = field(default_factory=dict)
    bed: dict[str, str] = field(default_factory=dict)
    inpatients: list[str] = field(default_factory=list)
    restricted: list[str] = field(default_factory=list)
    now: str = ""


def make_note(rng: random.Random, *, age: int, sex: str, sc: Scenario, pos: list[str], neg: list[str], comorb: list[str],
              vit: dict[str, float], allergies: list[str], meds: list[tuple[str, str]], kind: str, day: int, typo: bool) -> str:
    who = f"{age}-year-old {'male' if sex == 'male' else 'female'}"
    pos_text = []
    for k in pos:
        syn = T.SYMPTOMS[k]["synonyms"]
        phrase = syn[0] if k not in ("smoker",) else "smoker, 20 pack-years"
        if k == "radiating_pain":
            phrase = "pain radiating to the left arm"
        pos_text.append(phrase)
    parts = []
    if kind == "admission":
        dur = rng.choice(["for 2 days", "for 3 days", "for 5 days", "for 1 week", "since this morning"])
        parts.append(f"{who} presenting with {', '.join(pos_text) if pos_text else 'a routine check-up request'}"
                     + (f" {dur}." if pos_text else "."))
    elif kind == "progress":
        parts.append(f"Day {day} of admission. {who}. Reports {pos_text[0] if pos_text else 'no new complaints'}; overall {rng.choice(['unchanged', 'slightly better', 'slightly worse'])}.")
    else:
        parts.append(f"Follow-up visit. {who}. Complains of {', '.join(pos_text) if pos_text else 'no symptoms'}.")
    if neg:
        parts.append("Denies " + ", ".join(T.SYMPTOMS[k]["synonyms"][0] for k in neg[:3]) + ".")
    if comorb:
        parts.append("Past history: " + ", ".join(T.CONDITIONS[c]["synonyms"][0] for c in comorb) + ".")
    parts.append("Allergies: " + (", ".join(allergies) if allergies else "no known drug allergies") + ".")
    if meds:
        parts.append("Current medication: " + ", ".join(f"{T.MEDS[m]['display'].split(' (')[0]} {sig}" for m, sig in meds[:6]) + ".")
    parts.append(f"On examination: temperature {vit['temp']:.1f} C, pulse {vit['hr']:.0f}/min, respiratory rate {vit['rr']:.0f}/min, "
                 f"BP {vit['sbp']:.0f}/{vit['dbp']:.0f} mmHg, SpO2 {vit['spo2']:.0f}%.")
    imp = sc.impression
    if typo and sc.key == "cap":
        imp = "? pnemonia, right lower zone crackles."
    elif typo and sc.key == "hf":
        imp = "Probable cardiac failure, possible decompensation."
    parts.append("Impression: " + imp)
    return " ".join(parts)


def generate(store: Store, *, seed: int = 2026, n_patients: int = 64, now: datetime | None = None) -> Cohort:
    rng = random.Random(seed)
    now = (now or datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0)
    cohort = Cohort(now=iso(now))
    synth_tag = {"system": "https://asclepius.example/tags", "code": "synthetic", "display": "Synthetic record"}

    # practitioners and locations
    for p in PRACTITIONERS:
        store.put({"resourceType": "Practitioner", "id": p["id"], "meta": {"tag": [synth_tag]}, "name": [{"text": p["name"]}],
                   "qualification": [{"code": {"text": p["role"]}}], "extension": [{"url": "https://asclepius.example/ext/dept", "valueString": p["dept"]}]})
    for code, w in WARDS.items():
        store.put({"resourceType": "Location", "id": f"loc-{code.lower()}", "meta": {"tag": [synth_tag]}, "name": w["name"], "identifier": [{"value": code}], "status": "active",
                   "extension": [{"url": "https://asclepius.example/ext/beds", "valueInteger": w["beds"]}]})

    plan: list[tuple[str, str | None, str]] = [(s, w, t) for s, w, t in INPATIENT_PLAN]
    while len(plan) < n_patients:
        plan.append((OUTPATIENT_CYCLE[(len(plan) - len(INPATIENT_PLAN)) % len(OUTPATIENT_CYCLE)], None, "stable"))
    plan = plan[:n_patients]
    bed_counter = {w: 0 for w in WARDS}
    restricted_idx = {len(INPATIENT_PLAN) + 2, len(INPATIENT_PLAN) + 7, 14}

    resources: list[dict[str, Any]] = []
    for idx, (skey, ward, traj) in enumerate(plan):
        sc = SCENARIOS[skey]
        sex = rng.choice(["male", "female"])
        first = rng.choice(FIRST_M if sex == "male" else FIRST_F)
        last = rng.choice(LAST)
        age = rng.randint(*sc.age)
        birth = (now - timedelta(days=age * 365 + rng.randint(0, 364))).date().isoformat()
        pid = f"pat-{idx + 1:03d}"
        cohort.truth[pid] = skey
        cohort.trajectory[pid] = traj
        abha = abdm.make_abha(rng)
        attending = ATTENDING_BY_DEPT[sc.dept]
        if skey in ("sepsis", "cap", "copd", "pe") and ward == "ICU":
            attending = "prac-rao"
        meta: dict[str, Any] = {"tag": [synth_tag], "profile": [abdm.ABHA_PROFILE]}
        if idx in restricted_idx:
            meta["security"] = [{"system": "http://terminology.hl7.org/CodeSystem/v3-Confidentiality", "code": "R", "display": "restricted"}]
            cohort.restricted.append(pid)
        patient: dict[str, Any] = {
            "resourceType": "Patient", "id": pid, "meta": meta,
            "identifier": [
                {"system": abdm.ABHA_SYSTEM, "value": abha, "type": {"text": "ABHA number"}},
                {"system": "https://asclepius.example/mrn", "value": f"MRN-{100200 + idx * 7}", "type": {"text": "MRN"}},
                {"system": "https://asclepius.example/abha-address", "value": abdm.make_address(first, last, rng), "type": {"text": "ABHA address"}},
            ],
            "active": True, "name": [{"family": last, "given": [first], "text": f"{first} {last}"}],
            "gender": sex, "birthDate": birth,
            "address": [{"city": rng.choice(CITIES), "country": "IN"}],
            "generalPractitioner": [ref("Practitioner", attending)],
        }
        resources.append(patient)

        # chronic comorbidity conditions
        conds = list(sc.conditions)
        if age > 60 and skey not in ("healthy", "ida", "asthma") and "htn" not in conds and rng.random() < .45:
            conds.append("htn")
        if age > 55 and "t2dm" not in conds and skey in ("hf", "mi", "cap", "stroke") and rng.random() < .35:
            conds.append("t2dm")
        comorb = [c for c in conds if c not in sc.conditions]
        # allergies
        allergies: list[str] = []
        if rng.random() < .2:
            allergies.append("penicillin")
        if rng.random() < .05:
            allergies.append("sulfa")
        for a in allergies:
            info = T.ALLERGENS[a]
            resources.append({"resourceType": "AllergyIntolerance", "patient": ref("Patient", pid), "clinicalStatus": codeable("http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical", "active", "Active"),
                              "code": codeable(T.SYS_SNOMED, info["snomed"], info["display"]), "recordedDate": iso(now - timedelta(days=rng.randint(200, 3000))),
                              "reaction": [{"manifestation": [{"text": rng.choice(["rash", "urticaria", "facial swelling"])}]}]})

        # encounters
        enc_id = f"enc-{idx + 1:03d}"
        sym_pos = [k for k, p in sc.pos if rng.random() <= p] or ([sc.pos[0][0]] if sc.pos else [])
        sym_neg = [k for k in sc.neg if k not in sym_pos]
        hours = 0
        if ward:
            bed_counter[ward] += 1
            bed = f"{ward}-{bed_counter[ward]:02d}"
            cohort.ward[pid], cohort.bed[pid] = ward, bed
            cohort.inpatients.append(pid)
            hours = rng.randint(26, 47)
            start = now - timedelta(hours=hours)
            resources.append({"resourceType": "Encounter", "id": enc_id, "status": "in-progress", "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "IMP", "display": "inpatient encounter"},
                              "subject": ref("Patient", pid), "period": {"start": iso(start)},
                              "location": [{"location": ref("Location", f"loc-{ward.lower()}", WARDS[ward]["name"]), "physicalType": {"text": bed}}],
                              "reasonCode": [{"text": sc.label}]})
        else:
            for j in range(rng.randint(1, 3)):
                st = now - timedelta(days=rng.randint(20, 400) if j else rng.randint(1, 12))
                resources.append({"resourceType": "Encounter", "id": f"{enc_id}-{j}", "status": "finished", "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "ambulatory"},
                                  "subject": ref("Patient", pid), "period": {"start": iso(st), "end": iso(st + timedelta(minutes=25))}, "reasonCode": [{"text": sc.label}]})

        # conditions
        for c in conds:
            onset = now - timedelta(hours=hours) if (ward and c in sc.conditions) else now - timedelta(days=rng.randint(60, 2500))
            cat = "encounter-diagnosis" if (ward and c in sc.conditions) else "problem-list-item"
            resources.append({"resourceType": "Condition", "subject": ref("Patient", pid), "encounter": ref("Encounter", enc_id) if ward else None,
                              "clinicalStatus": codeable("http://terminology.hl7.org/CodeSystem/condition-clinical", "active", "Active"),
                              "verificationStatus": codeable("http://terminology.hl7.org/CodeSystem/condition-ver-status", "confirmed", "Confirmed"),
                              "category": [codeable("http://terminology.hl7.org/CodeSystem/condition-category", cat, cat)],
                              "code": T.condition_codeable(c), "onsetDateTime": iso(onset)})
            if resources[-1]["encounter"] is None:
                resources[-1].pop("encounter")

        # medications
        for m, sig in sc.meds:
            if m in ("metformin",) and skey == "ckd_dm" and idx % 2 == 0:
                continue
            resources.append({"resourceType": "MedicationRequest", "status": "active", "intent": "order", "subject": ref("Patient", pid),
                              "medicationCodeableConcept": T.med_codeable(m), "authoredOn": iso(now - timedelta(hours=hours or rng.randint(48, 900))),
                              "dosageInstruction": [{"text": sig}], "requester": ref("Practitioner", attending)})

        # vitals
        sick, well = sc.sick, sc.well
        last_vit: dict[str, float] = {}
        if ward:
            for k in range(hours, -1, -1):
                t = now - timedelta(hours=k)
                frac = (hours - k) / hours
                s = severity(traj, frac)
                v = {name: well[name] + s * (sick[name] - well[name]) for name in ("hr", "rr", "spo2", "sbp", "dbp", "temp")}
                v["hr"] = _ack(rng, v["hr"], 3, 38, 190)
                v["rr"] = _ack(rng, v["rr"], 1, 7, 42)
                v["spo2"] = _ack(rng, v["spo2"], 1, 70, 100)
                v["sbp"] = _ack(rng, v["sbp"], 4, 60, 230)
                v["dbp"] = _ack(rng, v["dbp"], 3, 35, 130)
                v["temp"] = _ack(rng, v["temp"], .15, 34.5, 41.2, 1)
                flow = 0 if s < .45 else 2 if s < .75 else 4 if s < 1.0 else 6
                if skey == "copd" and flow:
                    flow = 2
                acvpu = "Alert"
                if skey in ("sepsis", "stroke") and s > 1.05 and rng.random() < .6:
                    acvpu = "Confusion"
                if skey == "sepsis" and traj == "critical" and k < 3:
                    acvpu = "Voice"
                for name in ("hr", "rr", "spo2", "temp", "sbp", "dbp"):
                    resources.append(_vital(pid, enc_id, name, v[name], t))
                resources.append(_vital(pid, enc_id, "o2flow", flow, t))
                resources.append({"resourceType": "Observation", "status": "final", "category": [codeable("http://terminology.hl7.org/CodeSystem/observation-category", "vital-signs", "Vital Signs")],
                                  "code": {"coding": [{"system": T.SYS_LOCAL, "code": T.ACVPU_CODE, "display": "ACVPU consciousness level"}], "text": "ACVPU"},
                                  "subject": ref("Patient", pid), "encounter": ref("Encounter", enc_id), "effectiveDateTime": iso(t), "valueString": acvpu})
                last_vit = v
        else:
            n_visits = rng.randint(3, 6)
            for j in range(n_visits):
                t = now - timedelta(days=(j * rng.randint(25, 70) + rng.randint(0, 5)))
                mix = .8 if skey not in ("healthy",) else 0
                v = {name: well[name] + mix * (sick[name] - well[name]) for name in ("hr", "rr", "spo2", "sbp", "dbp", "temp")}
                v = {"hr": _ack(rng, v["hr"], 5, 45, 150), "rr": _ack(rng, v["rr"], 1, 10, 30), "spo2": _ack(rng, v["spo2"], 1, 88, 100),
                     "sbp": _ack(rng, v["sbp"], 7, 85, 200), "dbp": _ack(rng, v["dbp"], 4, 50, 120), "temp": _ack(rng, v["temp"], .2, 35.5, 39.5, 1)}
                for name in ("hr", "rr", "spo2", "temp", "sbp", "dbp"):
                    resources.append(_vital(pid, f"{enc_id}-0", name, v[name], t))
                if j == 0:
                    last_vit = v

        # labs
        sexl = sex
        lab_times: list[tuple[datetime, float]] = []
        if ward:
            lab_times = [(now - timedelta(hours=hours - 1), severity(traj, 0.02)), (now - timedelta(hours=max(hours // 2, 2)), severity(traj, .5)), (now - timedelta(hours=3), severity(traj, .93))]
        else:
            lab_times = [(now - timedelta(days=d), .85 + rng.uniform(-.1, .1) if skey != "healthy" else 0) for d in (rng.randint(2, 9), rng.randint(90, 130), rng.randint(190, 260))]
        for t, s in lab_times:
            for lab, (wv, sv) in sc.labs.items():
                val = wv + s * (sv - wv)
                val *= 1 + rng.uniform(-.04, .04)
                if lab == "hemoglobin" and sexl == "female":
                    val -= 1.2
                nd = 2 if lab in ("troponin", "ddimer", "lactate", "creatinine", "inr") else 1 if lab in ("hba1c", "potassium", "tsh", "hemoglobin") else 0
                val = round(val, nd)
                resources.append(_lab(pid, enc_id if ward else f"{enc_id}-0", lab, val, t))
                if lab == "creatinine":
                    pass
            # egfr derived from creatinine at that moment
            ce = [r for r in resources[-40:] if r.get("resourceType") == "Observation" and (r.get("code", {}).get("coding") or [{}])[0].get("code") == "2160-0" and r.get("effectiveDateTime") == iso(t) and r["subject"]["reference"] == f"Patient/{pid}"]
            if ce:
                cv = ce[-1]["valueQuantity"]["value"]
                resources.append(_lab(pid, enc_id if ward else f"{enc_id}-0", "egfr", egfr_ckd_epi_2021(cv, age_years(birth, now.date()), sex), t))
        # notes
        note_meds = [(m, sig) for m, sig in sc.meds]
        typo = rng.random() < .12
        resources.append(_note(pid, enc_id if ward else f"{enc_id}-0", "Admission note" if ward else "Clinic note", make_note(
            rng, age=age, sex=sex, sc=sc, pos=sym_pos, neg=sym_neg, comorb=comorb, vit=last_vit or sc.well, allergies=allergies, meds=note_meds,
            kind="admission" if ward else "clinic", day=1, typo=typo), now - timedelta(hours=hours - 1 if ward else rng.randint(24, 200)), attending))
        if ward and hours > 30:
            resources.append(_note(pid, enc_id, "Progress note", make_note(
                rng, age=age, sex=sex, sc=sc, pos=sym_pos[:1], neg=[], comorb=comorb, vit=last_vit, allergies=allergies, meds=note_meds, kind="progress", day=2, typo=False),
                now - timedelta(hours=4), attending))
        # pending orders
        if ward:
            for text in sc.pending:
                resources.append({"resourceType": "ServiceRequest", "status": "active", "intent": "order", "subject": ref("Patient", pid), "code": {"text": text},
                                  "authoredOn": iso(now - timedelta(hours=rng.randint(1, 10))), "requester": ref("Practitioner", attending)})
    # drop None values produced by optional fields
    store.put_many(_clean(r) for r in resources)
    return cohort


def _clean(res: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in res.items() if v is not None}


def _vital(pid: str, enc: str, name: str, value: float, t: datetime) -> dict[str, Any]:
    spec = T.VITALS[name]
    return {"resourceType": "Observation", "status": "final",
            "category": [codeable("http://terminology.hl7.org/CodeSystem/observation-category", "vital-signs", "Vital Signs")],
            "code": {"coding": [{"system": T.SYS_LOINC, "code": spec["loinc"], "display": spec["display"]}], "text": spec["display"]},
            "subject": ref("Patient", pid), "encounter": ref("Encounter", enc), "effectiveDateTime": iso(t),
            "valueQuantity": {"value": value, "unit": spec["unit"], "system": T.SYS_UCUM, "code": spec["ucum"]}}


def _lab(pid: str, enc: str, key: str, value: float, t: datetime) -> dict[str, Any]:
    spec = T.LABS[key]
    return {"resourceType": "Observation", "status": "final",
            "category": [codeable("http://terminology.hl7.org/CodeSystem/observation-category", "laboratory", "Laboratory")],
            "code": {"coding": [{"system": T.SYS_LOINC, "code": spec["loinc"], "display": spec["display"]}], "text": spec["display"]},
            "subject": ref("Patient", pid), "encounter": ref("Encounter", enc), "effectiveDateTime": iso(t),
            "valueQuantity": {"value": value, "unit": spec["unit"], "system": T.SYS_UCUM, "code": spec["unit"]}}


def _note(pid: str, enc: str, title: str, text: str, t: datetime, author: str) -> dict[str, Any]:
    return {"resourceType": "DocumentReference", "status": "current", "type": codeable(T.SYS_LOINC, "11506-3", "Progress note"),
            "subject": ref("Patient", pid), "date": iso(t), "author": [ref("Practitioner", author)], "description": title,
            "content": [{"attachment": {"contentType": "text/plain", "data": encode_text(text), "title": title}}],
            "context": {"encounter": [ref("Encounter", enc)]}}


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))
