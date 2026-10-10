"""Explainable differential-diagnosis copilot with a safety verifier.

How it works
1. Findings are extracted from the chart (note NLP, vitals, labs, problem list). The clinician's own
   impression and encounter diagnoses are ignored on purpose, to avoid anchoring and circular reasoning.
2. Each finding becomes a numbered piece of evidence that points to the FHIR resource it came from.
3. A transparent likelihood-ratio model ranks a knowledge base of conditions. Ratios are damped to
   limit over-confidence from correlated findings. Output is a *relative* likelihood, not a probability.
4. A narrative is composed with [E#] citations, then a verifier checks citations, numbers, contradictions,
   allergy conflicts and scope before anything is shown.

The knowledge base is a small, hand-written teaching set. It is not clinically validated.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from . import coding
from . import terminology as T
from .chart import Chart
from .clinical import lab_range
from .config import Settings
from .warning import chart_news2, chart_vitals_at, qsofa

DAMP = 0.75

KB: dict[str, dict[str, Any]] = {
    "cap": dict(name="Community-acquired pneumonia", prior=.06, cannot_miss=False,
                lr={"fever": 2.2, "cough": 1.6, "productive_cough": 2.8, "dyspnea": 1.6, "pleuritic_pain": 2.2, "tachypnea": 1.8, "hypoxia": 2.0, "leukocytosis": 2.3, "high_crp": 3.2, "tachycardia": 1.4},
                neg={"cough": .45, "fever": .6}, workup=[("Chest radiograph", None), ("C-reactive protein", "crp"), ("White cell count", "wbc"), ("Sputum culture", None), ("Blood cultures if severe", None)]),
    "sepsis": dict(name="Sepsis", prior=.04, cannot_miss=True,
                   lr={"fever": 1.8, "tachycardia": 1.9, "tachypnea": 2.0, "hypotension": 3.5, "high_lactate": 5.0, "leukocytosis": 2.0, "leukopenia": 1.8, "confusion": 2.6, "dysuria": 1.8, "flank_pain": 1.6, "high_creatinine": 1.8, "high_crp": 2.6, "thrombocytopenia": 2.0, "hypothermia": 2.0},
                   neg={}, workup=[("Serum lactate", "lactate"), ("Blood cultures x2 before antibiotics", None), ("Urine culture", None), ("White cell count", "wbc"), ("Creatinine", "creatinine")]),
    "uti": dict(name="Urinary tract infection / pyelonephritis", prior=.04, cannot_miss=False,
                lr={"dysuria": 6.0, "flank_pain": 4.0, "fever": 1.6, "leukocytosis": 1.6, "high_crp": 1.8}, neg={"dysuria": .35}, workup=[("Urinalysis", None), ("Urine culture", None), ("C-reactive protein", "crp")]),
    "hf": dict(name="Decompensated heart failure", prior=.04, cannot_miss=False,
               lr={"dyspnea": 2.2, "orthopnea": 5.0, "edema": 3.5, "high_bnp": 7.0, "known_hf": 6.0, "hypoxia": 1.7, "tachycardia": 1.2, "weight_gain": 2.0, "cough": 1.3, "fatigue": 1.4, "known_htn": 1.3},
               neg={"edema": .6, "orthopnea": .5}, workup=[("BNP", "bnp"), ("Echocardiogram", None), ("Chest radiograph", None), ("Creatinine and electrolytes", "creatinine")]),
    "copd": dict(name="COPD exacerbation", prior=.03, cannot_miss=False,
                 lr={"known_copd": 9.0, "wheeze": 3.0, "dyspnea": 1.8, "cough": 1.8, "productive_cough": 2.0, "smoker": 2.6, "hypoxia": 1.5, "tachypnea": 1.4},
                 neg={}, workup=[("Arterial blood gas", None), ("Chest radiograph", None), ("Sputum culture", None)]),
    "mi": dict(name="Acute coronary syndrome", prior=.04, cannot_miss=True,
               lr={"chest_pain": 4.0, "radiating_pain": 3.5, "diaphoresis": 3.5, "high_troponin": 14.0, "dyspnea": 1.4, "known_htn": 1.4, "known_diabetes": 1.5, "age_ge_55": 1.6, "tachycardia": 1.2},
               neg={"chest_pain": .25}, workup=[("12-lead ECG", None), ("Troponin (serial)", "troponin"), ("Chest radiograph", None), ("Lipid profile", "ldl")]),
    "pe": dict(name="Pulmonary embolism", prior=.015, cannot_miss=True,
               lr={"dyspnea": 2.0, "pleuritic_pain": 2.6, "tachycardia": 2.0, "hypoxia": 2.4, "high_ddimer": 4.0, "calf_swelling": 5.0, "hemoptysis": 3.0, "tachypnea": 1.8, "high_troponin": 1.5},
               neg={"calf_swelling": .8}, workup=[("D-dimer", "ddimer"), ("CT pulmonary angiogram", None), ("Leg Doppler", None), ("Wells score", None)]),
    "stroke": dict(name="Acute ischaemic stroke", prior=.02, cannot_miss=True,
                   lr={"weakness_unilateral": 14.0, "speech_difficulty": 10.0, "severe_htn": 2.0, "headache": 1.4, "confusion": 1.8, "known_af": 3.5, "age_ge_65": 1.5},
                   neg={"weakness_unilateral": .3}, workup=[("Urgent non-contrast CT head", None), ("Blood glucose", "glucose"), ("ECG for atrial fibrillation", None), ("Stroke scale (NIHSS)", None)]),
    "dengue": dict(name="Dengue fever", prior=.03, cannot_miss=False,
                   lr={"fever": 2.8, "myalgia": 3.0, "retro_orbital_pain": 5.0, "rash": 2.5, "headache": 1.8, "thrombocytopenia": 9.0, "leukopenia": 3.5, "vomiting": 1.4},
                   neg={"fever": .3}, workup=[("Dengue NS1 antigen / IgM", None), ("Platelet count", "platelets"), ("Haematocrit trend", "hemoglobin")]),
    "gastro": dict(name="Acute gastroenteritis", prior=.04, cannot_miss=False,
                   lr={"diarrhea": 8.0, "vomiting": 4.0, "fever": 1.4}, neg={"diarrhea": .2}, workup=[("Electrolytes", "sodium"), ("Stool routine", None)]),
    "ida": dict(name="Iron deficiency anaemia", prior=.03, cannot_miss=False,
                lr={"fatigue": 1.8, "pallor": 5.0, "anemia": 8.0, "microcytosis": 6.0, "dyspnea": 1.3}, neg={}, workup=[("Ferritin and iron studies", None), ("Peripheral smear", None), ("Haemoglobin", "hemoglobin")]),
    "hypothyroid": dict(name="Hypothyroidism", prior=.02, cannot_miss=False,
                        lr={"fatigue": 1.8, "weight_gain": 2.5, "cold_intolerance": 4.0, "high_tsh": 14.0}, neg={}, workup=[("TSH", "tsh"), ("Free T4", None)]),
    "asthma": dict(name="Asthma", prior=.03, cannot_miss=False,
                   lr={"wheeze": 5.0, "cough": 2.0, "dyspnea": 2.0}, neg={"wheeze": .3}, workup=[("Peak flow / spirometry", None), ("Chest radiograph if atypical", None)]),
    "hyperglycemia": dict(name="Uncontrolled diabetes mellitus", prior=.04, cannot_miss=False,
                          lr={"polyuria": 4.0, "polydipsia": 4.0, "hyperglycemia": 6.0, "high_hba1c": 7.0, "known_diabetes": 3.0, "fatigue": 1.4}, neg={}, workup=[("HbA1c", "hba1c"), ("Blood glucose", "glucose"), ("Renal function", "creatinine")]),
    "af": dict(name="Atrial fibrillation", prior=.02, cannot_miss=False,
               lr={"palpitations": 4.0, "known_af": 9.0, "tachycardia": 1.8, "dyspnea": 1.3, "fatigue": 1.2}, neg={}, workup=[("12-lead ECG", None), ("TSH", "tsh"), ("Echocardiogram", None)]),
}
SCENARIO_TO_KB = {"cap": {"cap"}, "sepsis": {"sepsis", "uti"}, "mi": {"mi"}, "hf": {"hf"}, "copd": {"copd"}, "stroke": {"stroke"}, "dengue": {"dengue"}, "gastro": {"gastro"},
                  "pe": {"pe"}, "chronic_dm_htn": {"hyperglycemia"}, "ida": {"ida"}, "asthma": {"asthma"}, "hypothyroid": {"hypothyroid"}, "af": {"af"}}

FINDING_LABEL = {
    "fever": "fever", "cough": "cough", "productive_cough": "productive cough", "dyspnea": "shortness of breath", "orthopnea": "orthopnoea", "pleuritic_pain": "pleuritic chest pain",
    "chest_pain": "chest pain", "radiating_pain": "pain radiating to the arm", "diaphoresis": "sweating", "palpitations": "palpitations", "edema": "leg swelling", "wheeze": "wheeze",
    "headache": "headache", "myalgia": "muscle aches", "retro_orbital_pain": "retro-orbital pain", "rash": "rash", "vomiting": "vomiting", "diarrhea": "diarrhoea", "dysuria": "dysuria",
    "flank_pain": "flank pain", "weakness_unilateral": "one-sided weakness", "speech_difficulty": "speech difficulty", "fatigue": "fatigue", "pallor": "pallor", "weight_gain": "weight gain",
    "cold_intolerance": "cold intolerance", "polyuria": "polyuria", "polydipsia": "polydipsia", "confusion": "confusion", "hemoptysis": "haemoptysis", "calf_swelling": "calf swelling", "smoker": "smoking history",
    "tachycardia": "tachycardia", "tachypnea": "tachypnoea", "hypoxia": "low oxygen saturation", "hypotension": "low blood pressure", "severe_htn": "severely raised blood pressure", "hypothermia": "low temperature",
    "leukocytosis": "raised white cell count", "leukopenia": "low white cell count", "thrombocytopenia": "low platelets", "anemia": "anaemia", "microcytosis": "microcytosis", "high_crp": "raised CRP",
    "high_troponin": "raised troponin", "high_bnp": "raised BNP", "high_lactate": "raised lactate", "high_creatinine": "raised creatinine", "hyperglycemia": "raised glucose", "high_hba1c": "raised HbA1c",
    "high_tsh": "raised TSH", "high_ddimer": "raised D-dimer", "known_hf": "known heart failure", "known_copd": "known COPD", "known_af": "known atrial fibrillation", "known_htn": "known hypertension",
    "known_diabetes": "known diabetes", "age_ge_55": "older age", "age_ge_65": "advanced age",
}


@dataclass
class Evidence:
    id: str
    kind: str
    ref: str
    text: str
    finding: str
    polarity: str  # present | absent

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class Findings:
    evidence: list[Evidence] = field(default_factory=list)
    present: dict[str, list[str]] = field(default_factory=dict)  # finding -> [evidence ids]
    absent: dict[str, list[str]] = field(default_factory=dict)

    def add(self, kind: str, ref: str, text: str, finding: str, polarity: str = "present") -> None:
        ev = Evidence(f"E{len(self.evidence) + 1}", kind, ref, text, finding, polarity)
        self.evidence.append(ev)
        (self.present if polarity == "present" else self.absent).setdefault(finding, []).append(ev.id)


def _hhmm(t: str) -> str:
    return t[11:16] + "Z"


def extract_findings(chart: Chart) -> Findings:
    f = Findings()
    # symptoms from notes (most recent two, impression ignored)
    for note in chart.notes[:2]:
        res = coding.symptom_findings(note["text"])
        for key, m in res["present"].items():
            f.add("note", f"DocumentReference/{note['id']}", f"“{m['sentence'][:150]}”", key)
        for key, m in res["absent"].items():
            f.add("note", f"DocumentReference/{note['id']}", f"“{m['sentence'][:150]}” (denied)", key, "absent")
    # vitals
    v = chart_vitals_at(chart)
    if v:
        obs_ref = f"Observation (vitals {_hhmm(v['time'])})"
        if v["hr"] > 100:
            f.add("vital", obs_ref, f"Heart rate {v['hr']:.0f}/min", "tachycardia")
        if v["rr"] > 20:
            f.add("vital", obs_ref, f"Respiratory rate {v['rr']:.0f}/min", "tachypnea")
        if v["spo2"] < 94:
            f.add("vital", obs_ref, f"SpO2 {v['spo2']:.0f}%", "hypoxia")
        if v["sbp"] < 100:
            f.add("vital", obs_ref, f"Systolic BP {v['sbp']:.0f} mmHg", "hypotension")
        if v["sbp"] >= 160:
            f.add("vital", obs_ref, f"Systolic BP {v['sbp']:.0f} mmHg", "severe_htn")
        if v["temp"] >= 38.0:
            f.add("vital", obs_ref, f"Temperature {v['temp']:.1f} C", "fever")
        if v["temp"] < 36.0:
            f.add("vital", obs_ref, f"Temperature {v['temp']:.1f} C", "hypothermia")
        if not str(v["acvpu"]).lower().startswith("a"):
            f.add("vital", obs_ref, f"Consciousness level {v['acvpu']} (ACVPU)", "confusion")
    # labs
    def lab(key: str) -> tuple[float, str, str] | None:
        s = chart.labs.get(key)
        return (s[-1][1], s[-1][2], s[-1][0]) if s else None

    def addlab(key: str, finding: str, cond: Any, fmt: str | None = None) -> None:
        r = lab(key)
        if r and cond(r[0]):
            spec = T.LABS[key]
            f.add("lab", f"Observation/{r[1]}", f"{spec['display'].split(' [')[0].split(' (')[0]} {r[0]:g} {spec['unit']} ({_hhmm(r[2])[:5] if False else r[2][:10]})", finding)

    addlab("wbc", "leukocytosis", lambda x: x > 11)
    addlab("wbc", "leukopenia", lambda x: x < 4)
    addlab("platelets", "thrombocytopenia", lambda x: x < 100)
    hb = lab("hemoglobin")
    if hb and hb[0] < lab_range("hemoglobin", chart.sex)[0]:  # type: ignore[index]
        f.add("lab", f"Observation/{hb[1]}", f"Haemoglobin {hb[0]:g} g/dL", "anemia")
    addlab("mcv", "microcytosis", lambda x: x < 80)
    addlab("crp", "high_crp", lambda x: x > 50)
    addlab("troponin", "high_troponin", lambda x: x > 0.04)
    addlab("bnp", "high_bnp", lambda x: x > 400)
    addlab("lactate", "high_lactate", lambda x: x > 2.0)
    addlab("creatinine", "high_creatinine", lambda x: x > 1.3)
    addlab("glucose", "hyperglycemia", lambda x: x > 200)
    addlab("hba1c", "high_hba1c", lambda x: x >= 6.5)
    addlab("tsh", "high_tsh", lambda x: x > 4.5)
    addlab("ddimer", "high_ddimer", lambda x: x > 0.5)
    # history: problem-list items only
    hist = {"hf": "known_hf", "copd": "known_copd", "af": "known_af", "htn": "known_htn", "t2dm": "known_diabetes"}
    for c in chart.conditions:
        if c["category"] == "problem-list-item" and c["key"] in hist:
            f.add("history", f"Condition/{c['id']}", f"Problem list: {c['display']}", hist[c["key"]])
    if chart.age >= 55:
        f.add("demographic", f"Patient/{chart.pid}", f"Age {chart.age} years", "age_ge_55")
    if chart.age >= 65:
        f.add("demographic", f"Patient/{chart.pid}", f"Age {chart.age} years", "age_ge_65")
    return f


def rank(findings: Findings) -> list[dict[str, Any]]:
    scored = []
    for key, d in KB.items():
        logit = math.log(d["prior"] / (1 - d["prior"]))
        support, against = [], []
        for fnd, lr in d["lr"].items():
            if fnd in findings.present:
                logit += DAMP * math.log(lr)
                support.append({"finding": fnd, "label": FINDING_LABEL.get(fnd, fnd), "lr": lr, "evidence": findings.present[fnd]})
        for fnd, lr in d["neg"].items():
            if fnd in findings.absent and fnd not in findings.present:
                logit += DAMP * math.log(lr)
                against.append({"finding": fnd, "label": FINDING_LABEL.get(fnd, fnd), "lr": lr, "evidence": findings.absent[fnd], "kind": "denied"})
        scored.append({"key": key, "name": d["name"], "odds": math.exp(logit), "cannot_miss": d["cannot_miss"], "support": sorted(support, key=lambda s: -s["lr"]), "against": against})
    total = sum(1.0 for _ in scored)  # normalise on p = odds/(1+odds)
    probs = [s["odds"] / (1 + s["odds"]) for s in scored]
    z = sum(probs) or 1.0
    for s, p in zip(scored, probs):
        s["share"] = round(p / z, 4)
        s["strength"] = "strong" if s["share"] >= .35 else "moderate" if s["share"] >= .15 else "weak"
        del s["odds"]
    del total
    return sorted(scored, key=lambda s: -s["share"])


def _unassessed(key: str, chart: Chart, findings: Findings) -> list[dict[str, Any]]:
    out = []
    d = KB[key]
    for fnd, lr in sorted(d["lr"].items(), key=lambda kv: -kv[1]):
        if lr < 4 or fnd in findings.present or fnd in findings.absent:
            continue
        if fnd.startswith("high_") or fnd in ("anemia", "thrombocytopenia", "hyperglycemia", "microcytosis"):
            labkey = {"high_troponin": "troponin", "high_bnp": "bnp", "high_lactate": "lactate", "high_ddimer": "ddimer", "high_tsh": "tsh", "high_hba1c": "hba1c", "high_crp": "crp",
                      "anemia": "hemoglobin", "thrombocytopenia": "platelets", "hyperglycemia": "glucose", "microcytosis": "mcv", "high_creatinine": "creatinine"}.get(fnd)
            if labkey and labkey in chart.labs:
                continue
        out.append({"finding": fnd, "label": FINDING_LABEL.get(fnd, fnd), "lr": lr})
    return out[:3]


def next_steps(ranked: list[dict[str, Any]], chart: Chart) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for r in ranked[:3]:
        if r["share"] < .08:
            continue
        for label, labkey in KB[r["key"]]["workup"]:
            if labkey and labkey in chart.labs:
                continue
            seen.setdefault(label, {"test": label, "for": []})["for"].append(r["name"])
    return list(seen.values())[:8]


def red_flags(ranked: list[dict[str, Any]], chart: Chart) -> list[dict[str, str]]:
    flags = []
    n2 = chart_news2(chart)
    if n2 and n2["score"] >= 5:
        flags.append({"level": "high" if n2["score"] >= 7 else "medium", "text": f"NEWS2 is {n2['score']} ({n2['risk']}). {n2['response']}"})
    v = chart_vitals_at(chart)
    if v:
        q = qsofa(v)
        if q["score"] >= 2:
            flags.append({"level": "high", "text": f"qSOFA is {q['score']}/3: screen for sepsis and consider early antimicrobials per local protocol."})
    for r in ranked:
        if r["cannot_miss"] and r["share"] >= .12:
            flags.append({"level": "medium", "text": f"Do not miss: {r['name']} carries {round(r['share'] * 100)}% relative likelihood; make sure it is actively excluded."})
    return flags


def compose_narrative(ranked: list[dict[str, Any]], evidence: dict[str, Evidence], steps: list[dict[str, Any]]) -> str:
    top = ranked[0]
    sent = []
    cites = lambda ids: " ".join(f"[{i}]" for i in ids[:2])  # noqa: E731
    sup = [f"{s['label']} {cites(s['evidence'])}" for s in top["support"][:5]]
    sent.append(f"The leading consideration is {top['name']} with a relative likelihood of {round(top['share'] * 100)}%, supported by " + (", ".join(sup) if sup else "very few findings") + ".")
    if len(ranked) > 1 and ranked[1]["share"] >= .08:
        alt = ranked[1]
        asup = [f"{s['label']} {cites(s['evidence'])}" for s in alt["support"][:3]]
        sent.append(f"{alt['name']} is the next consideration at {round(alt['share'] * 100)}% (" + (", ".join(asup) if asup else "limited support") + ").")
    if top["against"]:
        a = top["against"][0]
        sent.append(f"Against {top['name']}: {a['label']} was denied {cites(a['evidence'])}.")
    if steps:
        sent.append("Suggested next steps for clinician consideration: " + ", ".join(s["test"] for s in steps[:4]) + ".")
    sent.append("This is decision support for clinician review and not a diagnosis.")
    return " ".join(sent)


# -------------------------------------------------------------- verifier
NUM = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.]*\])")
CITE = re.compile(r"\[(E\d+)\]")
UNSAFE = re.compile(r"\b(diagnosed with|confirmed diagnosis|definitely has|certainly has|is definitely|prescribe|should (?:take|receive|be given) \d|give \d+\s?(?:mg|mcg|g|units)|start \w+ \d+\s?(?:mg|mcg|g))\b", re.I)
CLAIM_HINT = re.compile(r"\d|supported by|against|denied|findings?|likelihood", re.I)


def verify(narrative: str, chart: Chart, evidence: list[Evidence], *, allowed_numbers: set[str] | None = None) -> dict[str, Any]:
    ev = {e.id: e for e in evidence}
    allowed_numbers = allowed_numbers or set()
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", narrative.strip()) if s.strip()]
    rows, uncited, bad_cites, bad_nums, contradictions, unsafe = [], [], [], [], [], []
    all_ev_numbers = set(NUM.findall(" ".join(e.text for e in evidence)))
    present_keys = {e.finding for e in evidence if e.polarity == "present"}
    absent_keys = {e.finding for e in evidence if e.polarity == "absent"}
    for s in sentences:
        cites = CITE.findall(s)
        row: dict[str, Any] = {"text": s, "citations": cites, "issues": []}
        for c in cites:
            if c not in ev:
                bad_cites.append(c)
                row["issues"].append(f"unknown citation {c}")
        body = re.sub(r"\b\d+-lead\b|\bx\d+\b", "", CITE.sub("", s))
        needs_cite = bool(CLAIM_HINT.search(body)) and "decision support" not in body.lower()
        if needs_cite and not cites and "likelihood" not in body.lower():
            uncited.append(s)
            row["issues"].append("clinical statement without a citation")
        cited_text = " ".join(ev[c].text for c in cites if c in ev)
        pool = set(NUM.findall(cited_text)) if cites else all_ev_numbers
        for n in NUM.findall(body):
            if n in allowed_numbers or n in {"2", "3"} and "qsofa" in body.lower():
                continue
            if n not in pool and n not in all_ev_numbers:
                bad_nums.append(n)
                row["issues"].append(f"number {n} is not in the chart evidence")
            elif cites and n not in pool:
                bad_nums.append(n)
                row["issues"].append(f"number {n} is not in the cited evidence")
        res = coding.analyze(body)
        for m in res["mentions"]:
            if m["kind"] != "symptom" or m["match"] == "fuzzy":
                continue
            if m["assertion"] == "present" and m["key"] in absent_keys and m["key"] not in present_keys and "against" not in body.lower():
                contradictions.append(m["display"])
                row["issues"].append(f"asserts {m['display'].lower()} but the chart records it as denied")
            if m["assertion"] == "absent" and m["key"] in present_keys and m["key"] not in absent_keys:
                contradictions.append(m["display"])
                row["issues"].append(f"asserts no {m['display'].lower()} but the chart records it")
        if UNSAFE.search(body):
            unsafe.append(s)
            row["issues"].append("definitive diagnosis or dosing directive is out of scope")
        rows.append(row)
    # allergy conflicts
    allergy_hits = []
    classes = {c for a in chart.allergies if a["key"] for c in T.ALLERGENS[a["key"]]["classes"]}
    for m in coding.analyze(narrative)["mentions"]:
        if m["kind"] == "medication" and m["assertion"] != "absent" and T.MEDS[m["key"]]["cls"] in classes:
            allergy_hits.append(m["display"])
    checks = []

    def chk(name: str, status: str, details: str) -> None:
        checks.append({"name": name, "status": status, "details": details})

    cited_claims = sum(1 for r in rows if r["citations"])
    chk("Citation coverage", "Pass" if not uncited else ("Warn" if len(uncited) <= max(1, len(rows) // 4) else "Fail"),
        "Every clinical statement cites chart evidence." if not uncited else f"{len(uncited)} statement(s) make clinical claims without a citation.")
    chk("Citation validity", "Pass" if not bad_cites else "Fail", f"{cited_claims} statement(s) cite evidence; all citations resolve." if not bad_cites else f"Unknown citation(s): {', '.join(sorted(set(bad_cites)))}.")
    chk("Numeric fidelity", "Pass" if not bad_nums else "Fail", "Every number traces to chart evidence." if not bad_nums else f"Number(s) not found in evidence: {', '.join(sorted(set(bad_nums)))}.")
    chk("Chart consistency", "Pass" if not contradictions else "Fail", "No statement contradicts a documented finding." if not contradictions else f"Contradicts the chart on: {', '.join(sorted(set(contradictions)))}.")
    chk("Allergy safety", "Pass" if not allergy_hits else "Fail", "No mentioned drug conflicts with a recorded allergy." if not allergy_hits else f"Mentions {', '.join(sorted(set(allergy_hits)))} despite a recorded allergy to the same class.")
    has_disclaimer = bool(re.search(r"decision support|clinician", narrative, re.I))
    chk("Scope guard", "Fail" if unsafe else ("Pass" if has_disclaimer else "Warn"),
        "No definitive diagnosis or dosing directive." if not unsafe and has_disclaimer else ("Definitive wording or dosing found." if unsafe else "Missing the decision-support disclaimer."))
    rank_ = {"Pass": 0, "Warn": 1, "Fail": 2}
    overall = max(checks, key=lambda c: rank_[c["status"]])["status"]
    return {"status": overall, "checks": checks, "sentences": rows, "released": overall != "Fail"}


def llm_rewrite(settings: Settings, narrative: str) -> str | None:
    """Optionally ask a local Ollama-compatible model to polish the narrative. The result is only ever shown after verification."""
    if not settings.llm_url:
        return None
    prompt = ("Rewrite the clinical decision-support note below in plain, concise English. Keep every [E#] citation and every number exactly as written. "
              "Do not add facts, drugs, doses or diagnoses.\n\n" + narrative)
    try:
        r = httpx.post(settings.llm_url.rstrip("/") + "/api/generate", json={"model": settings.llm_model, "prompt": prompt, "stream": False}, timeout=20)
        r.raise_for_status()
        return (r.json().get("response") or "").strip() or None
    except Exception:  # noqa: BLE001 - any failure falls back to the deterministic narrative
        return None


def differential(chart: Chart, settings: Settings | None = None) -> dict[str, Any]:
    findings = extract_findings(chart)
    ranked = rank(findings)
    evid = {e.id: e for e in findings.evidence}
    steps = next_steps(ranked, chart)
    narrative = compose_narrative(ranked, evid, steps)
    pct = {str(round(r["share"] * 100)) for r in ranked}
    verification = verify(narrative, chart, findings.evidence, allowed_numbers=pct)
    source = "deterministic"
    if settings and settings.llm_url:
        alt = llm_rewrite(settings, narrative)
        if alt:
            v2 = verify(alt, chart, findings.evidence, allowed_numbers=pct)
            if v2["status"] != "Fail":
                narrative, verification, source = alt, v2, "llm (verified)"
            else:
                source = "deterministic (llm output blocked by verifier)"
    top = []
    for r in ranked[:6]:
        if r["share"] < .02:
            continue
        top.append({**r, "unassessed": _unassessed(r["key"], chart, findings)})
    return {"patient": chart.pid, "differential": top, "evidence": [e.to_dict() for e in findings.evidence], "next_steps": steps, "red_flags": red_flags(ranked, chart),
            "narrative": narrative, "narrative_source": source, "verification": verification,
            "method": {"model": "damped likelihood-ratio ranking (teaching knowledge base)", "damping": DAMP, "ignores": ["clinician impression", "encounter diagnoses"],
                       "disclaimer": "Relative likelihoods compare candidate conditions with each other; they are not probabilities. Not a medical device."}}
