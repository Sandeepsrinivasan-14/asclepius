"""Ambient scribe: turn a consultation transcript into a SOAP note and draft FHIR resources.

Nothing is written to the chart until a physician signs the draft. Audio transcription is optional and
runs locally if `faster-whisper` is installed; otherwise paste or dictate text.
"""

from __future__ import annotations

import re
from typing import Any

from . import coding
from . import terminology as T
from .db import Store, iso, utcnow
from .fhir import codeable, ref

DEMO_TRANSCRIPTS = {
    "chest_pain": ("Chest pain clinic visit",
                   "Doctor: Good morning. What brings you in today?\n"
                   "Patient: I have had chest pain since yesterday evening. It is a heavy pressure in the middle of my chest and it goes to my left arm.\n"
                   "Doctor: Any sweating or shortness of breath?\n"
                   "Patient: Yes, I was sweating a lot and I felt breathless when I climbed the stairs.\n"
                   "Doctor: Any fever or cough?\n"
                   "Patient: No fever and no cough.\n"
                   "Doctor: Do you have any medical problems? Are you on medicines?\n"
                   "Patient: I have high blood pressure and diabetes. I take Telma 40 and metformin 500 twice daily. I am allergic to penicillin.\n"
                   "Doctor: On examination your BP is 158/96, pulse 104, temperature 37.1, oxygen saturation 95. I think this is likely an acute coronary syndrome.\n"
                   "Doctor: I will order a troponin and an ECG now. Start aspirin 300 mg and continue your metformin. We will admit you to the cardiac unit for monitoring."),
    "urinary": ("Urinary symptoms",
                "Doctor: Tell me what is troubling you.\n"
                "Patient: I have burning urination for three days and pain in my left flank. I also have fever at night.\n"
                "Doctor: Any vomiting or confusion?\n"
                "Patient: I had vomiting once yesterday. No confusion.\n"
                "Doctor: Any known kidney problems or allergies?\n"
                "Patient: No kidney problems. I am allergic to sulfa drugs.\n"
                "Doctor: Temperature is 38.4, pulse 98, BP 118/74. This looks like a urinary tract infection, possibly pyelonephritis.\n"
                "Doctor: Order a urine culture and a creatinine. Start ceftriaxone 1 g daily and review in 48 hours. Advise plenty of oral fluids."),
    "diabetes_followup": ("Diabetes follow-up",
                          "Doctor: How have you been since the last visit?\n"
                          "Patient: I have been very thirsty and passing urine frequently for two weeks, and I feel tired.\n"
                          "Doctor: Any chest pain or blurred vision?\n"
                          "Patient: No chest pain.\n"
                          "Doctor: Are you taking metformin and amlodipine regularly?\n"
                          "Patient: I take metformin 500 twice daily and Amlong 5 once daily. Sometimes I miss the evening dose.\n"
                          "Doctor: BP is 148/92 today, pulse 82. Your diabetes is probably uncontrolled. Order HbA1c and creatinine, increase metformin to 1000 mg twice daily if kidney function allows, and refer to the dietitian."),
}

SPEAKER = re.compile(r"^\s*(doctor|dr|physician|clinician|d|patient|pt|p|nurse)\s*[:\-]\s*(.*)$", re.I)
DURATION = re.compile(r"\b(?:for|since)\s+((?:\d+|a|an|one|two|three|four|five|six|seven|few|several)\s+(?:hour|day|week|month|year)s?|yesterday(?: evening| morning)?|this morning|last night)", re.I)
PLAN_VERBS = re.compile(r"\b(start|order|prescribe|continue|stop|increase|decrease|refer|follow up|review|advise|admit|repeat|send|arrange|schedule|begin)\b", re.I)
ASSESS = re.compile(r"\b(i think|this looks like|likely|probably|suspect|impression|diagnosis|consistent with|appears to be)\b", re.I)
YES = re.compile(r"^\s*(yes|yeah|yep|i do|i have|a little|sometimes|mild(ly)?)\b", re.I)
NO = re.compile(r"^\s*(no|nope|not really|none|never|i do not|i don't)\b", re.I)


def transcribe_audio(path: str) -> str | None:
    """Local speech-to-text if faster-whisper is available. Returns None when it is not installed."""
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        return None
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(path)
    return " ".join(s.text.strip() for s in segments)


def _utterances(transcript: str) -> list[dict[str, str]]:
    out = []
    for line in transcript.splitlines():
        if not line.strip():
            continue
        m = SPEAKER.match(line)
        if m:
            who = "doctor" if m.group(1).lower() in ("doctor", "dr", "physician", "clinician", "d", "nurse") else "patient"
            out.append({"speaker": who, "text": m.group(2).strip()})
        else:
            out.append({"speaker": "unknown", "text": line.strip()})
    return out


def _vitals(text: str) -> dict[str, float]:
    v: dict[str, float] = {}
    if m := re.search(r"\b(?:bp|blood pressure)\s*(?:is|of|was)?\s*(\d{2,3})\s*(?:/|over)\s*(\d{2,3})", text, re.I):
        v["sbp"], v["dbp"] = float(m.group(1)), float(m.group(2))
    if m := re.search(r"\b(?:pulse|heart rate|hr)\s*(?:is|of|was)?\s*(\d{2,3})", text, re.I):
        v["hr"] = float(m.group(1))
    if m := re.search(r"\btemp(?:erature)?\s*(?:is|of|was)?\s*(\d{2,3}(?:\.\d)?)", text, re.I):
        v["temp"] = float(m.group(1))
    if m := re.search(r"\b(?:spo2|saturation|oxygen saturation|oxygen)\s*(?:is|of|was)?\s*(\d{2,3})", text, re.I):
        v["spo2"] = float(m.group(1))
    if m := re.search(r"\b(?:respiratory rate|resp rate|rr)\s*(?:is|of|was)?\s*(\d{2})", text, re.I):
        v["rr"] = float(m.group(1))
    return v


def draft(transcript: str, patient_id: str | None = None, patient_name: str | None = None) -> dict[str, Any]:
    utts = _utterances(transcript)
    present: dict[str, dict[str, Any]] = {}
    absent: dict[str, dict[str, Any]] = {}
    durations: dict[str, str] = {}
    history: dict[str, dict[str, Any]] = {}
    meds_current: dict[str, str] = {}
    allergies: list[str] = []
    # question and answer pairs, plus self-contained patient statements
    for i, u in enumerate(utts):
        if u["speaker"] == "doctor" and "?" in u["text"] and i + 1 < len(utts) and utts[i + 1]["speaker"] == "patient":
            ans = utts[i + 1]["text"]
            qs = coding.analyze(u["text"])["mentions"]
            for m in qs:
                if m["kind"] != "symptom":
                    continue
                if NO.match(ans) and not re.search(r"\b(?:no|not)\b[^.]*\b(?:" + re.escape(m["text"].split()[0].lower()) + r")", ans.lower() + " x") or re.match(r"^\s*(no|nope|not really)", ans, re.I):
                    absent.setdefault(m["key"], {"display": m["display"], "quote": f'Q: "{u["text"]}" A: "{ans}"'})
                elif YES.match(ans):
                    present.setdefault(m["key"], {"display": m["display"], "quote": f'Q: "{u["text"]}" A: "{ans}"'})
        if u["speaker"] in ("patient", "unknown"):
            res = coding.analyze(u["text"])
            for m in res["mentions"]:
                if m["kind"] == "symptom":
                    if m["assertion"] == "absent":
                        absent.setdefault(m["key"], {"display": m["display"], "quote": u["text"]})
                        present.pop(m["key"], None) if m["key"] not in present else None
                    elif m["assertion"] in ("present", "possible"):
                        present[m["key"]] = {"display": m["display"], "quote": u["text"]}
                        absent.pop(m["key"], None)
                        d = DURATION.search(u["text"])
                        if d:
                            durations[m["key"]] = d.group(1)
                elif m["kind"] == "condition" and m["assertion"] != "absent":
                    history[m["key"]] = {"display": m["display"], "quote": u["text"]}
                elif m["kind"] == "medication":
                    meds_current[m["key"]] = u["text"]
            for m in re.finditer(r"allergic to ([a-z ]+?)(?: drugs?)?(?:[.,]| and |$)", u["text"], re.I):
                allergies.append(m.group(1).strip())
    # a symptom both confirmed in a statement and "no" elsewhere keeps the explicit statement
    vitals: dict[str, float] = {}
    exam_lines, assessment, plan = [], [], []
    for u in utts:
        if u["speaker"] == "patient":
            continue
        vitals.update(_vitals(u["text"]))
        if re.search(r"\bon examination\b|\bi can hear\b|\bchest is\b|\babdomen\b", u["text"], re.I):
            exam_lines.append(u["text"])
        for sent in re.split(r"(?<=[.])\s+", u["text"]):
            if ASSESS.search(sent):
                res = coding.analyze(sent)
                for m in res["mentions"]:
                    if m["kind"] == "condition" and m["assertion"] != "absent":
                        assessment.append({"key": m["key"], "display": m["display"], "icd10": T.CONDITIONS[m["key"]]["icd10"], "snomed": T.CONDITIONS[m["key"]]["snomed"],
                                           "certainty": "possible" if (m["assertion"] == "possible" or re.search(r"likely|probably|possibly|suspect", sent, re.I)) else "stated", "quote": sent.strip()})
            elif PLAN_VERBS.search(sent) and u["speaker"] != "patient":
                plan.append(sent.strip())
    seen = set()
    assessment = [a for a in assessment if not (a["key"] in seen or seen.add(a["key"]))]  # type: ignore[func-returns-value]
    # plan items classified as orders
    plan_items: list[dict[str, Any]] = []
    for sent in plan:
        for clause in re.split(r",\s*(?:and\s+)?|\s+and\s+(?=(?:order|start|continue|stop|increase|refer|review|advise|admit|repeat|send|arrange))", sent):
            clause = clause.strip(" .")
            if not clause or not PLAN_VERBS.search(clause):
                continue
            item: dict[str, Any] = {"text": clause[0].upper() + clause[1:], "type": "advice"}
            verb = PLAN_VERBS.search(clause).group(1).lower()  # type: ignore[union-attr]
            labs = [k for k, spec in T.LABS.items() if any(re.search(r"(?<![a-z])" + re.escape(s) + r"(?![a-z])", clause.lower()) for s in spec["synonyms"])]
            medm = [m for m in coding.analyze(clause)["mentions"] if m["kind"] == "medication"]
            if verb in ("order", "send", "repeat", "arrange") or (labs and verb not in ("start", "continue", "stop", "increase")):
                item.update(type="order", labs=labs)
                if re.search(r"\becg\b|\bx-?ray\b|\bct\b|\bultrasound\b|\bmri\b", clause, re.I):
                    item["type"] = "order"
            if medm and verb in ("start", "prescribe", "begin", "increase", "continue", "stop", "decrease"):
                dose = re.search(r"\d+(?:\.\d+)?\s?(?:mg|mcg|g|units)", clause)
                item.update(type="medication", action=verb, drug=medm[0]["key"], dose=dose.group(0) if dose else None)
            elif verb == "admit":
                item["type"] = "disposition"
            elif verb in ("refer",):
                item["type"] = "referral"
            elif verb in ("review", "follow up"):
                item["type"] = "follow-up"
            plan_items.append(item)
    cc = next((u["text"] for u in utts if u["speaker"] in ("patient", "unknown") and any(k in present for k in [m["key"] for m in coding.analyze(u["text"])["mentions"] if m["kind"] == "symptom"])), "")
    hpi_parts = []
    for k, v in present.items():
        hpi_parts.append(f"{v['display']}" + (f" ({durations[k]})" if k in durations else ""))
    hpi = (f"Patient reports {', '.join(hpi_parts)}." if hpi_parts else "No symptoms captured.") + (f" Denies {', '.join(v['display'].lower() for v in absent.values())}." if absent else "")
    note = {
        "subjective": {"chief_complaint": cc, "hpi": hpi, "positives": [{"key": k, **v, "duration": durations.get(k)} for k, v in present.items()], "negatives": [{"key": k, **v} for k, v in absent.items()],
                       "history": list(history.values()), "medications": [{"key": k, "display": T.MEDS[k]["display"], "quote": q} for k, q in meds_current.items()], "allergies": sorted(set(allergies))},
        "objective": {"vitals": vitals, "exam": exam_lines},
        "assessment": assessment,
        "plan": plan_items,
    }
    fhir = _fhir_drafts(note, patient_id)
    confidence_flags = []
    if not any(u["speaker"] != "unknown" for u in utts):
        confidence_flags.append("No speaker labels found: patient and clinician statements could not be separated.")
    if not assessment:
        confidence_flags.append("No assessment statement detected; the clinician must add one.")
    return {"patient": patient_id, "patient_name": patient_name, "utterances": utts, "note": note, "fhir_draft": fhir, "review_flags": confidence_flags,
            "status": "draft", "summary": {"symptoms": len(present), "negatives": len(absent), "assessment": len(assessment), "plan_items": len(plan_items), "fhir_resources": len(fhir)},
            "disclaimer": "AI-drafted from the transcript. Nothing is saved to the chart until a physician reviews and signs."}


def soap_text(note: dict[str, Any]) -> str:
    s, o = note["subjective"], note["objective"]
    v = o["vitals"]
    vit = ", ".join(f"{k.upper()} {val:g}" for k, val in v.items()) or "not stated"
    return "\n".join([
        "S: " + (s["chief_complaint"] or "(no complaint captured)"), "   " + s["hpi"],
        "   PMH: " + (", ".join(h["display"] for h in s["history"]) or "none stated") + "; Meds: " + (", ".join(m["display"] for m in s["medications"]) or "none stated") + "; Allergies: " + (", ".join(s["allergies"]) or "none stated"),
        "O: Vitals " + vit + ("; " + "; ".join(o["exam"]) if o["exam"] else ""),
        "A: " + ("; ".join(f"{a['display']} ({a['certainty']})" for a in note["assessment"]) or "(none stated)"),
        "P: " + ("; ".join(p["text"] for p in note["plan"]) or "(none stated)")])


def _fhir_drafts(note: dict[str, Any], pid: str | None) -> list[dict[str, Any]]:
    subj = ref("Patient", pid) if pid else {"display": "Unassigned patient"}
    tag = {"system": "https://asclepius.example/tags", "code": "ai-draft", "display": "AI-drafted, pending clinician review"}
    now = iso(utcnow())
    out: list[dict[str, Any]] = []
    for a in note["assessment"]:
        out.append({"resourceType": "Condition", "meta": {"tag": [tag]}, "subject": subj, "clinicalStatus": codeable("http://terminology.hl7.org/CodeSystem/condition-clinical", "active", "Active"),
                    "verificationStatus": codeable("http://terminology.hl7.org/CodeSystem/condition-ver-status", "provisional", "Provisional"), "code": T.condition_codeable(a["key"]), "recordedDate": now})
    v = note["objective"]["vitals"]
    for k, val in v.items():
        if k in T.VITALS:
            spec = T.VITALS[k]
            out.append({"resourceType": "Observation", "meta": {"tag": [tag]}, "status": "preliminary", "category": [codeable("http://terminology.hl7.org/CodeSystem/observation-category", "vital-signs", "Vital Signs")],
                        "code": {"coding": [{"system": T.SYS_LOINC, "code": spec["loinc"], "display": spec["display"]}], "text": spec["display"]}, "subject": subj, "effectiveDateTime": now,
                        "valueQuantity": {"value": val, "unit": spec["unit"], "system": T.SYS_UCUM, "code": spec["ucum"]}})
    for al in note["subjective"]["allergies"]:
        key = "penicillin" if "penicillin" in al.lower() else "sulfa" if "sulfa" in al.lower() else None
        if key:
            info = T.ALLERGENS[key]
            out.append({"resourceType": "AllergyIntolerance", "meta": {"tag": [tag]}, "patient": subj, "verificationStatus": codeable("http://terminology.hl7.org/CodeSystem/allergyintolerance-verification", "unconfirmed", "Unconfirmed"),
                        "code": codeable(T.SYS_SNOMED, info["snomed"], info["display"]), "recordedDate": now})
    for p in note["plan"]:
        if p["type"] == "medication" and p.get("action") in ("start", "prescribe", "begin", "increase"):
            out.append({"resourceType": "MedicationRequest", "meta": {"tag": [tag]}, "status": "draft", "intent": "proposal", "subject": subj, "medicationCodeableConcept": T.med_codeable(p["drug"]),
                        "authoredOn": now, "dosageInstruction": [{"text": p["text"]}]})
        elif p["type"] == "order":
            out.append({"resourceType": "ServiceRequest", "meta": {"tag": [tag]}, "status": "draft", "intent": "proposal", "subject": subj, "code": {"text": p["text"]}, "authoredOn": now})
    out.append({"resourceType": "Composition", "meta": {"tag": [tag]}, "status": "preliminary", "type": codeable(T.SYS_LOINC, "11488-4", "Consult note"), "subject": subj, "date": now,
                "author": [{"display": "Asclepius ambient scribe (draft)"}], "title": "Consultation note (AI-drafted)",
                "section": [{"title": "SOAP", "text": {"status": "generated", "div": "<div>" + soap_text(note).replace("\n", "<br/>") + "</div>"}}]})
    return out


def sign(store: Store, draft_obj: dict[str, Any], patient_id: str, practitioner: str | None, *, approve: list[str] | None = None) -> dict[str, Any]:
    """Persist approved draft resources. `approve` lists resource types to commit (default: all)."""
    if not store.get("Patient", patient_id):
        raise ValueError(f"Patient/{patient_id} not found")
    saved = []
    for res in draft_obj["fhir_draft"]:
        if approve is not None and res["resourceType"] not in approve:
            continue
        r = {k: v for k, v in res.items()}
        for key in ("subject", "patient"):
            if key in r or (key == "subject" and r["resourceType"] != "AllergyIntolerance"):
                if key == "subject" or r["resourceType"] == "AllergyIntolerance":
                    r["patient" if r["resourceType"] == "AllergyIntolerance" else "subject"] = ref("Patient", patient_id)
        if r["resourceType"] == "Composition":
            r["status"] = "final"
            r["author"] = [ref("Practitioner", practitioner)] if practitioner else r["author"]
        elif r["resourceType"] == "MedicationRequest":
            r["status"], r["intent"] = "active", "order"
            if practitioner:
                r["requester"] = ref("Practitioner", practitioner)
        elif r["resourceType"] == "Observation":
            r["status"] = "final"
        elif r["resourceType"] == "ServiceRequest":
            r["status"], r["intent"] = "active", "order"
        elif r["resourceType"] == "Condition":
            r["verificationStatus"] = codeable("http://terminology.hl7.org/CodeSystem/condition-ver-status", "provisional", "Provisional")
        r.setdefault("meta", {}).setdefault("tag", []).append({"system": "https://asclepius.example/tags", "code": "clinician-signed", "display": "Reviewed and signed by a clinician"})
        r["id"] = store.next_id(r["resourceType"])
        store.put(r)
        saved.append({"resourceType": r["resourceType"], "id": r["id"]})
    return {"saved": saved, "count": len(saved)}
