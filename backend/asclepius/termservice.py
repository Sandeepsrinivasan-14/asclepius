"""Terminology service: code lookup, validation, expansion and translation over embedded subsets.

The clinical core uses the small curated sets in `terminology.py`. This module widens them with extra commonly
used ICD-10, SNOMED CT, LOINC and RxNorm codes and exposes FHIR-style operations ($lookup, $validate-code,
$expand, $translate). The sets are hand-curated subsets (not the licensed releases); verify before real use.
"""

from __future__ import annotations

from typing import Any

from . import terminology as T

ICD10_EXTRA: dict[str, str] = {
    "E10.9": "Type 1 diabetes mellitus without complications", "E11.65": "Type 2 diabetes mellitus with hyperglycaemia",
    "E11.22": "Type 2 diabetes mellitus with diabetic chronic kidney disease", "E05.9": "Thyrotoxicosis, unspecified",
    "E86.0": "Dehydration", "E87.1": "Hypo-osmolality and hyponatraemia", "E87.5": "Hyperkalaemia",
    "D64.9": "Anaemia, unspecified", "F32.9": "Depressive episode, unspecified", "F41.9": "Anxiety disorder, unspecified",
    "G43.9": "Migraine, unspecified", "I11.0": "Hypertensive heart disease with heart failure", "I20.9": "Angina pectoris, unspecified",
    "I25.10": "Atherosclerotic heart disease of native coronary artery without angina pectoris", "I48.91": "Unspecified atrial fibrillation",
    "I64": "Stroke, not specified as haemorrhage or infarction", "J06.9": "Acute upper respiratory infection, unspecified",
    "J20.9": "Acute bronchitis, unspecified", "J44.1": "COPD with acute exacerbation", "J45.909": "Unspecified asthma, uncomplicated",
    "K21.9": "Gastro-oesophageal reflux disease without oesophagitis", "K29.70": "Gastritis, unspecified, without bleeding",
    "K76.0": "Fatty (change of) liver, not elsewhere classified", "K92.2": "Gastrointestinal haemorrhage, unspecified",
    "M17.9": "Osteoarthritis of knee, unspecified", "M54.5": "Low back pain", "N10": "Acute pyelonephritis",
    "N17.9": "Acute kidney failure, unspecified", "R06.0": "Dyspnoea", "R07.4": "Chest pain, unspecified",
    "R50.9": "Fever, unspecified", "R55": "Syncope and collapse", "U07.1": "COVID-19, virus identified",
    "B54": "Unspecified malaria", "A15.0": "Tuberculosis of lung, confirmed",
}
SNOMED_EXTRA: dict[str, str] = {
    "73211009": "Diabetes mellitus", "46635009": "Diabetes mellitus type 1", "230690007": "Cerebrovascular accident",
    "233604007": "Pneumonia", "709044004": "Chronic kidney disease", "840539006": "COVID-19", "235595009": "Gastro-oesophageal reflux disease",
    "35489007": "Depressive disorder", "197480006": "Anxiety disorder", "37796009": "Migraine", "161891005": "Backache",
    "396275006": "Osteoarthritis", "128053003": "Deep venous thrombosis", "21522001": "Abdominal pain", "267102003": "Sore throat symptom",
    "195662009": "Acute viral pharyngitis", "271594007": "Syncope", "14760008": "Constipation",
}
LOINC_EXTRA: dict[str, str] = {
    "2345-7": "Glucose [Mass/volume] in Serum or Plasma", "1558-6": "Fasting glucose [Mass/volume] in Serum or Plasma",
    "2093-3": "Cholesterol [Mass/volume] in Serum or Plasma", "2085-9": "HDL cholesterol [Mass/volume]",
    "2571-8": "Triglyceride [Mass/volume] in Serum or Plasma", "1742-6": "Alanine aminotransferase [Enzymatic activity/volume]",
    "1920-8": "Aspartate aminotransferase [Enzymatic activity/volume]", "6768-6": "Alkaline phosphatase [Enzymatic activity/volume]",
    "1975-2": "Bilirubin.total [Mass/volume] in Serum or Plasma", "1751-7": "Albumin [Mass/volume] in Serum or Plasma",
    "3094-0": "Urea nitrogen [Mass/volume] in Serum or Plasma", "17861-6": "Calcium [Mass/volume] in Serum or Plasma",
    "2601-3": "Magnesium [Moles/volume] in Serum or Plasma", "3024-7": "Thyroxine (T4) free [Mass/volume] in Serum or Plasma",
    "2157-6": "Creatine kinase [Enzymatic activity/volume]", "5902-2": "Prothrombin time (PT)", "3173-2": "aPTT in Blood by Coagulation assay",
    "789-8": "Erythrocytes [#/volume] in Blood", "4544-3": "Hematocrit [Volume Fraction] of Blood",
    "85354-9": "Blood pressure panel", "29463-7": "Body weight", "8302-2": "Body height", "39156-5": "Body mass index (BMI)",
}
RXNORM_EXTRA: dict[str, str] = {
    "36567": "Simvastatin", "35296": "Ramipril", "19484": "Bisoprolol", "20352": "Carvedilol", "5487": "Hydrochlorothiazide",
    "25789": "Glimepiride", "593411": "Sitagliptin", "1545653": "Empagliflozin", "1488564": "Dapagliflozin", "1364430": "Apixaban",
    "1114195": "Rivaroxaban", "82122": "Levofloxacin", "3640": "Doxycycline", "26225": "Ondansetron", "88249": "Montelukast",
    "19831": "Budesonide", "20610": "Cetirizine", "703": "Amiodarone", "5224": "Heparin", "7052": "Morphine", "10689": "Tramadol",
    "114477": "Oseltamivir",
}

# Synthea and other EHR exports often use sibling codes for the same concept. These aliases map them onto
# the canonical codes the clinical modules understand, so imported charts light up the whole platform.
SNOMED_ALIASES: dict[str, str] = {  # code -> condition key in terminology.CONDITIONS
    "59621000": "htn", "44054006": "t2dm", "195967001": "asthma", "233604007": "cap", "385093006": "cap", "84114007": "hf",
    "49436004": "af", "13645005": "copd", "433144002": "ckd3", "431857002": "ckd3", "90708001": "ckd3", "38341003": "htn",
    "55822004": "dyslipidemia", "414916001": "obesity", "162864005": "obesity", "40930008": "hypothyroid", "87522002": "ida",
    "68566005": "uti", "38362002": "dengue", "25374005": "gastro", "59282003": "pe", "57054005": "mi", "401303003": "mi",
    "401314000": "mi", "230690007": "stroke", "422504002": "stroke", "91302008": "sepsis", "10509002": "gastro",
}
LOINC_ALIASES: dict[str, str] = {  # alias -> canonical LOINC used by terminology.LABS / VITALS
    "38483-4": "2160-0", "33914-3": "62238-1", "2947-0": "2951-2", "6298-4": "2823-3", "26464-8": "6690-2", "2708-6": "59408-5",
}

SYSTEM_URIS: dict[str, str] = {"icd10": T.SYS_ICD10, "snomed": T.SYS_SNOMED, "loinc": T.SYS_LOINC, "rxnorm": T.SYS_RXNORM}
_URI_TO_NAME = {v: k for k, v in SYSTEM_URIS.items()}
_ALT = {"icd-10": "icd10", "sct": "snomed", "snomed ct": "snomed", "snomed-ct": "snomed"}


def _build() -> dict[str, dict[str, str]]:
    icd = {c["icd10"]: c["display"] for c in T.CONDITIONS.values()} | ICD10_EXTRA
    sno = {c["snomed"]: c["display"] for c in T.CONDITIONS.values() if c.get("snomed")}
    sno |= {s["snomed"]: s["display"] for s in T.SYMPTOMS.values() if s.get("snomed")}
    sno |= {a["snomed"]: a["display"] for a in T.ALLERGENS.values()}
    sno |= SNOMED_EXTRA
    loinc = {v["loinc"]: v["display"] for v in T.LABS.values()} | {v["loinc"]: v["display"] for v in T.VITALS.values()} | LOINC_EXTRA
    rx = {m["rxnorm"]: m["display"] for m in T.MEDS.values()} | RXNORM_EXTRA
    return {"icd10": icd, "snomed": sno, "loinc": loinc, "rxnorm": rx}


CATALOG: dict[str, dict[str, str]] = _build()


def system_key(system: str) -> str | None:
    s = system.strip()
    low = s.lower()
    if low in CATALOG:
        return low
    return _URI_TO_NAME.get(s) or _ALT.get(low)


def stats() -> list[dict[str, Any]]:
    return [{"system": k, "uri": SYSTEM_URIS[k], "concepts": len(v)} for k, v in CATALOG.items()]


def lookup(system: str, code: str) -> dict[str, Any] | None:
    key = system_key(system)
    if key is None:
        return None
    display = CATALOG[key].get(code)
    return None if display is None else {"system": SYSTEM_URIS[key], "code": code, "display": display}


def validate_code(system: str, code: str, display: str | None = None) -> dict[str, Any]:
    found = lookup(system, code)
    if found is None:
        return {"result": False, "message": f"Code '{code}' was not found in the embedded {system} subset."}
    if display and display.strip().lower() != found["display"].lower():
        return {"result": True, "display": found["display"], "message": f"Valid code, but the display differs. Preferred display: {found['display']}."}
    return {"result": True, "display": found["display"], "message": "OK"}


def expand(system: str, q: str = "", limit: int = 20) -> list[dict[str, str]]:
    key = system_key(system)
    if key is None:
        return []
    ql = q.strip().lower()
    rows = [{"system": SYSTEM_URIS[key], "code": c, "display": d} for c, d in CATALOG[key].items() if not ql or ql in c.lower() or ql in d.lower()]
    return rows[:limit]


def translate(system: str, code: str) -> list[dict[str, str]]:
    """ICD-10 <-> SNOMED CT equivalence for the curated conditions (a tiny concept map)."""
    key = system_key(system)
    out: list[dict[str, str]] = []
    for c in T.CONDITIONS.values():
        if key == "icd10" and c["icd10"] == code:
            out.append({"system": T.SYS_SNOMED, "code": c["snomed"], "display": c["display"], "equivalence": "equivalent"})
        if key == "snomed" and c["snomed"] == code:
            out.append({"system": T.SYS_ICD10, "code": c["icd10"], "display": c["display"], "equivalence": "equivalent"})
    return out
