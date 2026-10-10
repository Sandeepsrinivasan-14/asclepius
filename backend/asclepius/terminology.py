"""Embedded terminology subsets (ICD-10, SNOMED CT, LOINC, RxNorm) used by the demo.

These are small, hand-curated subsets so the platform runs offline. Codes were chosen for
common concepts; always verify against the official release before any real-world use.
"""

from __future__ import annotations

from typing import Any

SYS_ICD10 = "http://hl7.org/fhir/sid/icd-10"
SYS_SNOMED = "http://snomed.info/sct"
SYS_LOINC = "http://loinc.org"
SYS_RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"
SYS_UCUM = "http://unitsofmeasure.org"
SYS_LOCAL = "https://asclepius.example/codes"

# ---------------------------------------------------------------- conditions
CONDITIONS: dict[str, dict[str, Any]] = {
    "t2dm": {"display": "Type 2 diabetes mellitus", "icd10": "E11.9", "snomed": "44054006",
             "synonyms": ["type 2 diabetes", "type ii diabetes", "t2dm", "diabetes mellitus type 2", "niddm", "diabetes mellitus", "diabetes"]},
    "htn": {"display": "Essential hypertension", "icd10": "I10", "snomed": "38341003",
            "synonyms": ["hypertension", "high blood pressure", "htn", "raised blood pressure"]},
    "ckd3": {"display": "Chronic kidney disease, stage 3", "icd10": "N18.3", "snomed": "433144002",
             "synonyms": ["chronic kidney disease", "ckd", "ckd stage 3", "chronic renal failure", "ckd 3"]},
    "cap": {"display": "Community-acquired pneumonia", "icd10": "J18.9", "snomed": "385093006",
            "synonyms": ["pneumonia", "community acquired pneumonia", "cap", "lobar pneumonia", "chest infection", "lower respiratory tract infection"]},
    "hf": {"display": "Heart failure", "icd10": "I50.9", "snomed": "84114007",
           "synonyms": ["heart failure", "congestive heart failure", "chf", "cardiac failure", "hfref", "decompensated heart failure"]},
    "copd": {"display": "Chronic obstructive pulmonary disease", "icd10": "J44.9", "snomed": "13645005",
             "synonyms": ["copd", "chronic obstructive pulmonary disease", "chronic bronchitis", "emphysema", "copd exacerbation"]},
    "sepsis": {"display": "Sepsis", "icd10": "A41.9", "snomed": "91302008",
               "synonyms": ["sepsis", "septicaemia", "septicemia", "urosepsis", "septic shock"]},
    "mi": {"display": "Acute myocardial infarction", "icd10": "I21.9", "snomed": "57054005",
           "synonyms": ["myocardial infarction", "heart attack", "stemi", "nstemi", "acute coronary syndrome", "acs", "mi"]},
    "stroke": {"display": "Ischaemic stroke", "icd10": "I63.9", "snomed": "422504002",
               "synonyms": ["stroke", "ischemic stroke", "ischaemic stroke", "cva", "cerebrovascular accident"]},
    "asthma": {"display": "Asthma", "icd10": "J45.9", "snomed": "195967001",
               "synonyms": ["asthma", "bronchial asthma", "asthma exacerbation"]},
    "ida": {"display": "Iron deficiency anaemia", "icd10": "D50.9", "snomed": "87522002",
            "synonyms": ["iron deficiency anemia", "iron deficiency anaemia", "ida", "anemia", "anaemia"]},
    "uti": {"display": "Urinary tract infection", "icd10": "N39.0", "snomed": "68566005",
            "synonyms": ["urinary tract infection", "uti", "pyelonephritis", "cystitis", "urine infection"]},
    "dengue": {"display": "Dengue fever", "icd10": "A90", "snomed": "38362002",
               "synonyms": ["dengue", "dengue fever", "dengue viral infection"]},
    "af": {"display": "Atrial fibrillation", "icd10": "I48", "snomed": "49436004",
           "synonyms": ["atrial fibrillation", "af", "afib", "a fib"]},
    "pe": {"display": "Pulmonary embolism", "icd10": "I26.9", "snomed": "59282003",
           "synonyms": ["pulmonary embolism", "pe", "pulmonary thromboembolism"]},
    "hypothyroid": {"display": "Hypothyroidism", "icd10": "E03.9", "snomed": "40930008",
                    "synonyms": ["hypothyroidism", "underactive thyroid", "hypothyroid"]},
    "gastro": {"display": "Gastroenteritis", "icd10": "A09", "snomed": "25374005",
               "synonyms": ["gastroenteritis", "acute gastroenteritis", "stomach flu", "diarrhoeal illness"]},
    "dyslipidemia": {"display": "Dyslipidaemia", "icd10": "E78.5", "snomed": "55822004",
                     "synonyms": ["dyslipidemia", "dyslipidaemia", "hyperlipidemia", "high cholesterol", "hypercholesterolemia"]},
    "obesity": {"display": "Obesity", "icd10": "E66.9", "snomed": "414916001", "synonyms": ["obesity", "obese"]},
}

# ------------------------------------------------------------------ symptoms
SYMPTOMS: dict[str, dict[str, Any]] = {
    "fever": {"display": "Fever", "snomed": "386661006", "synonyms": ["fever", "febrile", "pyrexia", "high temperature", "chills and fever"]},
    "cough": {"display": "Cough", "snomed": "49727002", "synonyms": ["cough", "coughing"]},
    "productive_cough": {"display": "Productive cough", "snomed": "28743005", "synonyms": ["productive cough", "sputum", "phlegm", "cough with sputum", "purulent sputum"]},
    "dyspnea": {"display": "Dyspnoea", "snomed": "267036007", "synonyms": ["shortness of breath", "breathlessness", "dyspnea", "dyspnoea", "difficulty breathing", "sob", "breathless"]},
    "orthopnea": {"display": "Orthopnoea", "snomed": "62744007", "synonyms": ["orthopnea", "orthopnoea", "breathless lying flat", "needs extra pillows", "short of breath lying flat"]},
    "pleuritic_pain": {"display": "Pleuritic chest pain", "snomed": "4386001", "synonyms": ["pleuritic chest pain", "pleuritic pain", "pain on deep breathing", "pain worse on inspiration", "sharp chest pain on breathing"]},
    "chest_pain": {"display": "Chest pain", "snomed": "29857009", "synonyms": ["chest pain", "chest tightness", "chest discomfort", "retrosternal pain", "central chest pain"]},
    "radiating_pain": {"display": "Pain radiating to arm or jaw", "snomed": None, "synonyms": ["radiating to the left arm", "radiating to left arm", "radiating to the jaw", "radiation to arm", "radiates to the arm", "radiating to arm"]},
    "diaphoresis": {"display": "Diaphoresis", "snomed": "52613005", "synonyms": ["diaphoresis", "sweating", "profuse sweating", "diaphoretic", "cold sweat"]},
    "palpitations": {"display": "Palpitations", "snomed": "80313002", "synonyms": ["palpitations", "racing heart", "heart racing", "fluttering"]},
    "edema": {"display": "Peripheral oedema", "snomed": "267038008", "synonyms": ["leg swelling", "ankle swelling", "pedal edema", "pedal oedema", "swollen legs", "peripheral edema", "edema", "oedema"]},
    "wheeze": {"display": "Wheeze", "snomed": "56018004", "synonyms": ["wheeze", "wheezing", "wheezy"]},
    "headache": {"display": "Headache", "snomed": "25064002", "synonyms": ["headache", "head ache"]},
    "myalgia": {"display": "Myalgia", "snomed": "68962001", "synonyms": ["myalgia", "muscle pain", "body ache", "body aches", "bone pain", "myalgias"]},
    "retro_orbital_pain": {"display": "Retro-orbital pain", "snomed": None, "synonyms": ["retro-orbital pain", "retro orbital pain", "pain behind the eyes", "pain behind eyes"]},
    "rash": {"display": "Rash", "snomed": "271807003", "synonyms": ["rash", "skin rash", "erythematous rash", "petechiae"]},
    "vomiting": {"display": "Vomiting", "snomed": "422400008", "synonyms": ["vomiting", "emesis", "nausea and vomiting", "vomits"]},
    "diarrhea": {"display": "Diarrhoea", "snomed": "62315008", "synonyms": ["diarrhea", "diarrhoea", "loose stools", "loose motions", "watery stools"]},
    "dysuria": {"display": "Dysuria", "snomed": "49650001", "synonyms": ["dysuria", "burning micturition", "burning urination", "painful urination", "burning while passing urine"]},
    "flank_pain": {"display": "Flank pain", "snomed": None, "synonyms": ["flank pain", "loin pain", "pain in the flank", "costovertebral angle tenderness", "cva tenderness"]},
    "weakness_unilateral": {"display": "Unilateral weakness", "snomed": None, "synonyms": ["right sided weakness", "left sided weakness", "weakness on one side", "unilateral weakness", "hemiparesis", "weakness of the right arm", "weakness of the left arm", "facial droop"]},
    "speech_difficulty": {"display": "Speech difficulty", "snomed": "8011004", "synonyms": ["slurred speech", "difficulty speaking", "speech difficulty", "dysarthria", "aphasia", "trouble speaking"]},
    "fatigue": {"display": "Fatigue", "snomed": "84229001", "synonyms": ["fatigue", "tiredness", "tired", "lethargy", "weakness and tiredness", "easily tired"]},
    "pallor": {"display": "Pallor", "snomed": None, "synonyms": ["pallor", "pale", "looks pale"]},
    "weight_gain": {"display": "Weight gain", "snomed": None, "synonyms": ["weight gain", "gained weight", "gaining weight"]},
    "cold_intolerance": {"display": "Cold intolerance", "snomed": None, "synonyms": ["cold intolerance", "feels cold", "intolerance to cold"]},
    "polyuria": {"display": "Polyuria", "snomed": "28442001", "synonyms": ["polyuria", "passing urine frequently", "frequent urination", "increased urination"]},
    "polydipsia": {"display": "Polydipsia", "snomed": "17173007", "synonyms": ["polydipsia", "excessive thirst", "very thirsty", "increased thirst"]},
    "confusion": {"display": "Confusion", "snomed": "40917007", "synonyms": ["confusion", "confused", "disorientation", "disoriented", "altered sensorium", "drowsy", "drowsiness"]},
    "hemoptysis": {"display": "Haemoptysis", "snomed": "66857006", "synonyms": ["hemoptysis", "haemoptysis", "coughing up blood", "blood in sputum", "blood-stained sputum"]},
    "calf_swelling": {"display": "Unilateral calf swelling", "snomed": None, "synonyms": ["calf swelling", "swollen calf", "calf pain", "unilateral leg swelling", "calf tenderness"]},
    "smoker": {"display": "Tobacco smoker", "snomed": None, "synonyms": ["smoker", "smokes", "current smoker", "ex-smoker", "pack years", "pack-years", "smoking history"]},
}

# ----------------------------------------------------------------------- labs
LABS: dict[str, dict[str, Any]] = {
    "glucose": {"loinc": "2339-0", "display": "Glucose [Mass/volume] in Blood", "unit": "mg/dL", "low": 70, "high": 140, "crit_low": 40, "crit_high": 400, "synonyms": ["glucose", "blood sugar", "rbs", "random blood sugar", "fasting glucose", "fbs"]},
    "hba1c": {"loinc": "4548-4", "display": "Hemoglobin A1c", "unit": "%", "low": 4.0, "high": 5.6, "synonyms": ["hba1c", "a1c", "glycated hemoglobin", "glycosylated haemoglobin"]},
    "creatinine": {"loinc": "2160-0", "display": "Creatinine [Mass/volume] in Serum", "unit": "mg/dL", "low": 0.6, "high": 1.3, "crit_high": 7.0, "synonyms": ["creatinine", "serum creatinine", "scr"]},
    "egfr": {"loinc": "62238-1", "display": "eGFR (CKD-EPI)", "unit": "mL/min/1.73m2", "low": 90, "high": 200, "synonyms": ["egfr", "estimated gfr", "glomerular filtration rate"]},
    "potassium": {"loinc": "2823-3", "display": "Potassium [Moles/volume] in Serum", "unit": "mmol/L", "low": 3.5, "high": 5.1, "crit_low": 2.5, "crit_high": 6.5, "synonyms": ["potassium", "serum potassium", "k+"]},
    "sodium": {"loinc": "2951-2", "display": "Sodium [Moles/volume] in Serum", "unit": "mmol/L", "low": 135, "high": 145, "crit_low": 120, "crit_high": 160, "synonyms": ["sodium", "serum sodium", "na+"]},
    "wbc": {"loinc": "6690-2", "display": "Leukocytes [#/volume] in Blood", "unit": "10*3/uL", "low": 4.0, "high": 11.0, "crit_low": 2.0, "crit_high": 30.0, "synonyms": ["wbc", "white cell count", "white blood cell count", "total leucocyte count", "tlc", "leukocytes"]},
    "hemoglobin": {"loinc": "718-7", "display": "Hemoglobin [Mass/volume] in Blood", "unit": "g/dL", "low": 12.0, "high": 17.0, "crit_low": 7.0, "synonyms": ["hemoglobin", "haemoglobin", "hb", "hgb"]},
    "platelets": {"loinc": "777-3", "display": "Platelets [#/volume] in Blood", "unit": "10*3/uL", "low": 150, "high": 400, "crit_low": 20, "synonyms": ["platelets", "platelet count", "plt"]},
    "mcv": {"loinc": "787-2", "display": "MCV [Entitic volume]", "unit": "fL", "low": 80, "high": 100, "synonyms": ["mcv", "mean corpuscular volume"]},
    "crp": {"loinc": "1988-5", "display": "C reactive protein [Mass/volume] in Serum", "unit": "mg/L", "low": 0, "high": 5, "synonyms": ["crp", "c reactive protein", "c-reactive protein"]},
    "lactate": {"loinc": "2524-7", "display": "Lactate [Moles/volume] in Serum", "unit": "mmol/L", "low": 0.5, "high": 2.0, "crit_high": 4.0, "synonyms": ["lactate", "serum lactate", "lactic acid"]},
    "troponin": {"loinc": "10839-9", "display": "Troponin I cardiac [Mass/volume]", "unit": "ng/mL", "low": 0, "high": 0.04, "crit_high": 0.5, "synonyms": ["troponin", "troponin i", "trop i", "hs troponin", "cardiac troponin"]},
    "bnp": {"loinc": "30934-4", "display": "BNP [Mass/volume] in Serum", "unit": "pg/mL", "low": 0, "high": 100, "synonyms": ["bnp", "brain natriuretic peptide", "b-type natriuretic peptide"]},
    "ddimer": {"loinc": "48066-5", "display": "D-dimer [Mass/volume] FEU", "unit": "mg/L", "low": 0, "high": 0.5, "synonyms": ["d-dimer", "d dimer", "ddimer"]},
    "tsh": {"loinc": "3016-3", "display": "Thyrotropin [Units/volume] in Serum", "unit": "mIU/L", "low": 0.4, "high": 4.5, "synonyms": ["tsh", "thyroid stimulating hormone", "thyrotropin"]},
    "ldl": {"loinc": "13457-7", "display": "LDL cholesterol (calculated)", "unit": "mg/dL", "low": 0, "high": 100, "synonyms": ["ldl", "ldl cholesterol", "ldl-c"]},
    "inr": {"loinc": "6301-6", "display": "INR in Platelet poor plasma", "unit": "{INR}", "low": 0.8, "high": 1.2, "synonyms": ["inr", "international normalized ratio"]},
}

# --------------------------------------------------------------------- vitals
VITALS: dict[str, dict[str, Any]] = {
    "hr": {"loinc": "8867-4", "display": "Heart rate", "unit": "/min", "ucum": "/min"},
    "rr": {"loinc": "9279-1", "display": "Respiratory rate", "unit": "/min", "ucum": "/min"},
    "spo2": {"loinc": "59408-5", "display": "Oxygen saturation in Arterial blood by Pulse oximetry", "unit": "%", "ucum": "%"},
    "temp": {"loinc": "8310-5", "display": "Body temperature", "unit": "Cel", "ucum": "Cel"},
    "sbp": {"loinc": "8480-6", "display": "Systolic blood pressure", "unit": "mm[Hg]", "ucum": "mm[Hg]"},
    "dbp": {"loinc": "8462-4", "display": "Diastolic blood pressure", "unit": "mm[Hg]", "ucum": "mm[Hg]"},
    "o2flow": {"loinc": "3151-8", "display": "Inhaled oxygen flow rate", "unit": "L/min", "ucum": "L/min"},
    "gcs": {"loinc": "9269-2", "display": "Glasgow coma score total", "unit": "{score}", "ucum": "{score}"},
}
ACVPU_CODE = "acvpu"
LOINC_TO_VITAL = {v["loinc"]: k for k, v in VITALS.items()}
LOINC_TO_LAB = {v["loinc"]: k for k, v in LABS.items()}

# ---------------------------------------------------------------- medications
# class is used for duplication checks; brands are common Indian brand names (generic synthetic list).
MEDS: dict[str, dict[str, Any]] = {
    "metformin": {"rxnorm": "6809", "display": "Metformin", "cls": "biguanide", "brands": ["glucophage", "glycomet", "obimet"]},
    "amlodipine": {"rxnorm": "17767", "display": "Amlodipine", "cls": "ccb", "brands": ["amlong", "norvasc", "stamlo"]},
    "lisinopril": {"rxnorm": "29046", "display": "Lisinopril", "cls": "acei", "brands": ["listril", "zestril"]},
    "enalapril": {"rxnorm": "3827", "display": "Enalapril", "cls": "acei", "brands": ["envas", "vasotec"]},
    "telmisartan": {"rxnorm": "73494", "display": "Telmisartan", "cls": "arb", "brands": ["telma", "micardis"]},
    "losartan": {"rxnorm": "52175", "display": "Losartan", "cls": "arb", "brands": ["losar", "cozaar"]},
    "atorvastatin": {"rxnorm": "83367", "display": "Atorvastatin", "cls": "statin", "brands": ["atorva", "lipitor", "storvas"]},
    "rosuvastatin": {"rxnorm": "301542", "display": "Rosuvastatin", "cls": "statin", "brands": ["rosuvas", "crestor"]},
    "furosemide": {"rxnorm": "4603", "display": "Furosemide", "cls": "loop_diuretic", "brands": ["lasix"]},
    "spironolactone": {"rxnorm": "9997", "display": "Spironolactone", "cls": "k_sparing", "brands": ["aldactone"]},
    "aspirin": {"rxnorm": "1191", "display": "Aspirin", "cls": "antiplatelet", "brands": ["ecosprin", "disprin"]},
    "clopidogrel": {"rxnorm": "32968", "display": "Clopidogrel", "cls": "antiplatelet", "brands": ["plavix", "clopilet"]},
    "warfarin": {"rxnorm": "11289", "display": "Warfarin", "cls": "anticoagulant", "brands": ["warf", "coumadin"]},
    "enoxaparin": {"rxnorm": "67108", "display": "Enoxaparin", "cls": "anticoagulant", "brands": ["clexane", "lovenox"]},
    "metoprolol": {"rxnorm": "6918", "display": "Metoprolol", "cls": "beta_blocker", "brands": ["metolar", "betaloc", "lopressor"]},
    "salbutamol": {"rxnorm": "435", "display": "Salbutamol (albuterol)", "cls": "saba", "brands": ["asthalin", "ventolin"]},
    "tiotropium": {"rxnorm": "69120", "display": "Tiotropium", "cls": "lama", "brands": ["tiova", "spiriva"]},
    "prednisolone": {"rxnorm": "8638", "display": "Prednisolone", "cls": "corticosteroid", "brands": ["wysolone", "omnacortil"]},
    "insulin_glargine": {"rxnorm": "274783", "display": "Insulin glargine", "cls": "insulin", "brands": ["lantus", "basalog"]},
    "ceftriaxone": {"rxnorm": "2193", "display": "Ceftriaxone", "cls": "cephalosporin", "brands": ["monocef", "rocephin"]},
    "azithromycin": {"rxnorm": "18631", "display": "Azithromycin", "cls": "macrolide", "brands": ["azithral", "zithromax"]},
    "amoxicillin": {"rxnorm": "723", "display": "Amoxicillin", "cls": "penicillin", "brands": ["mox", "amoxil"]},
    "amox_clav": {"rxnorm": "19711", "display": "Amoxicillin-clavulanate", "cls": "penicillin", "brands": ["augmentin", "clavam"]},
    "ciprofloxacin": {"rxnorm": "2551", "display": "Ciprofloxacin", "cls": "fluoroquinolone", "brands": ["ciplox", "cifran"]},
    "nitrofurantoin": {"rxnorm": "7454", "display": "Nitrofurantoin", "cls": "nitrofuran", "brands": ["furadantin", "niftran"]},
    "ibuprofen": {"rxnorm": "5640", "display": "Ibuprofen", "cls": "nsaid", "brands": ["brufen", "combiflam", "advil"]},
    "diclofenac": {"rxnorm": "3355", "display": "Diclofenac", "cls": "nsaid", "brands": ["voveran", "voltaren"]},
    "paracetamol": {"rxnorm": "161", "display": "Paracetamol (acetaminophen)", "cls": "analgesic", "brands": ["dolo", "crocin", "calpol", "tylenol"]},
    "pantoprazole": {"rxnorm": "40790", "display": "Pantoprazole", "cls": "ppi", "brands": ["pan", "pantocid", "protonix"]},
    "omeprazole": {"rxnorm": "7646", "display": "Omeprazole", "cls": "ppi", "brands": ["omez", "prilosec"]},
    "levothyroxine": {"rxnorm": "10582", "display": "Levothyroxine", "cls": "thyroid", "brands": ["thyronorm", "eltroxin", "synthroid"]},
    "digoxin": {"rxnorm": "3407", "display": "Digoxin", "cls": "cardiac_glycoside", "brands": ["lanoxin", "digoxin"]},
    "potassium_chloride": {"rxnorm": "8591", "display": "Potassium chloride", "cls": "electrolyte", "brands": ["kcl", "potklor"]},
    "sildenafil": {"rxnorm": "136411", "display": "Sildenafil", "cls": "pde5", "brands": ["viagra", "manforce"]},
    "isosorbide": {"rxnorm": "6058", "display": "Isosorbide mononitrate", "cls": "nitrate", "brands": ["monotrate", "imdur"]},
}

ALLERGENS: dict[str, dict[str, Any]] = {
    "penicillin": {"snomed": "91936005", "display": "Allergy to penicillin", "classes": ["penicillin"], "cross": {"cephalosporin": "Low cross-reactivity (about 1-2%); proceed with caution and monitoring."}},
    "sulfa": {"snomed": "91939003", "display": "Allergy to sulfonamide", "classes": ["sulfonamide"], "cross": {"loop_diuretic": "Possible cross-sensitivity with sulfonamide non-antibiotics is uncommon; monitor."}},
    "nsaid": {"snomed": "293586001", "display": "Allergy to non-steroidal anti-inflammatory agent", "classes": ["nsaid"], "cross": {}},
    "aspirin": {"snomed": "293586001", "display": "Allergy to aspirin", "classes": ["antiplatelet_aspirin"], "cross": {"nsaid": "Aspirin-sensitive patients often react to other NSAIDs."}},
}

INGREDIENT_TO_CLASS = {k: v["cls"] for k, v in MEDS.items()}


def coding(system: str, code: str, display: str) -> dict[str, str]:
    return {"system": system, "code": code, "display": display}


def condition_codeable(key: str) -> dict[str, Any]:
    c = CONDITIONS[key]
    codings = [coding(SYS_SNOMED, c["snomed"], c["display"]), coding(SYS_ICD10, c["icd10"], c["display"])]
    return {"coding": codings, "text": c["display"]}


def med_codeable(key: str) -> dict[str, Any]:
    m = MEDS[key]
    return {"coding": [coding(SYS_RXNORM, m["rxnorm"], m["display"])], "text": m["display"]}


def search_concepts(q: str, limit: int = 12) -> list[dict[str, Any]]:
    """Substring and synonym search across all embedded vocabularies."""
    ql = q.strip().lower()
    if not ql:
        return []
    out: list[dict[str, Any]] = []

    def hit(texts: list[str]) -> bool:
        return any(ql in t.lower() for t in texts)

    for key, c in CONDITIONS.items():
        if hit([c["display"], c["icd10"], c["snomed"], *c["synonyms"]]):
            out.append({"kind": "condition", "key": key, "display": c["display"],
                        "codes": {"ICD-10": c["icd10"], "SNOMED CT": c["snomed"]}})
    for key, s in SYMPTOMS.items():
        if hit([s["display"], *s["synonyms"]]):
            codes = {"SNOMED CT": s["snomed"]} if s.get("snomed") else {}
            out.append({"kind": "symptom", "key": key, "display": s["display"], "codes": codes})
    for key, lab in LABS.items():
        if hit([lab["display"], lab["loinc"], *lab["synonyms"]]):
            out.append({"kind": "lab", "key": key, "display": lab["display"], "codes": {"LOINC": lab["loinc"]}})
    for key, m in MEDS.items():
        if hit([m["display"], m["rxnorm"], *m["brands"]]):
            out.append({"kind": "medication", "key": key, "display": m["display"], "codes": {"RxNorm": m["rxnorm"]}})
    return out[:limit]
