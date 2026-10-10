"""Import Synthea-style FHIR R4 transaction bundles into the store.

Synthea (https://github.com/synthetichealth/synthea) writes one FHIR bundle per synthetic patient using
`urn:uuid:` references and its own coding choices. This importer re-keys the resources, rewrites references,
normalises timestamps, flattens blood-pressure panels, adds the canonical codes the clinical modules rely on
and drops resource types the server does not support. Everything stays tagged as synthetic.

`demo_bundle()` builds a small Synthea-shaped bundle so the importer can be exercised without Java.
"""

from __future__ import annotations

import json
import random
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import abdm, fhir
from . import terminology as T
from . import termservice as TS
from .db import Store

KEEP = {"Patient", "Condition", "Observation", "MedicationRequest", "AllergyIntolerance", "Encounter", "DocumentReference"}
TAGS = [{"system": "https://asclepius.example/tags", "code": "synthetic", "display": "Synthetic record"},
        {"system": "https://asclepius.example/tags", "code": "synthea", "display": "Imported from Synthea"}]
BP_COMPONENTS = {"8480-6": "sbp", "8462-4": "dbp"}


def _norm_dt(value: Any) -> Any:
    """Return an ISO-8601 UTC timestamp (YYYY-MM-DDTHH:MM:SSZ); leave unparseable values untouched."""
    if not isinstance(value, str) or len(value) < 10:
        return value
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_name(s: str) -> str:
    return re.sub(r"\d+", "", s).strip()


def _walk_refs(node: Any, idmap: dict[str, str]) -> None:
    """Rewrite or drop every `reference` in-place."""
    if isinstance(node, dict):
        ref = node.get("reference")
        if isinstance(ref, str):
            if ref in idmap:
                node["reference"] = idmap[ref]
            else:
                node.pop("reference")
        for v in list(node.values()):
            _walk_refs(v, idmap)
    elif isinstance(node, list):
        for v in node:
            _walk_refs(v, idmap)


def _canonical_condition_codes(res: dict[str, Any]) -> bool:
    """Add the platform's SNOMED + ICD-10 codings when a known alias is present. Returns True if mapped."""
    for c in (res.get("code") or {}).get("coding", []):
        key = TS.SNOMED_ALIASES.get(str(c.get("code")))
        if key:
            res["code"] = T.condition_codeable(key) | {"text": T.CONDITIONS[key]["display"]}
            return True
    return False


def _map_loinc(code: str) -> str:
    return TS.LOINC_ALIASES.get(code, code)


def _convert_observation(res: dict[str, Any]) -> list[dict[str, Any]]:
    res["effectiveDateTime"] = _norm_dt(res.get("effectiveDateTime") or res.get("issued"))
    if not res.get("effectiveDateTime"):
        return []
    out: list[dict[str, Any]] = []
    for c in res.get("component", []):
        code = next((x.get("code") for x in (c.get("code") or {}).get("coding", []) if x.get("code") in BP_COMPONENTS), None)
        if code and c.get("valueQuantity"):
            sub = {k: v for k, v in res.items() if k not in ("component", "code", "id")}
            sub["code"] = {"coding": [{"system": T.SYS_LOINC, "code": code, "display": T.VITALS[BP_COMPONENTS[code]]["display"]}], "text": T.VITALS[BP_COMPONENTS[code]]["display"]}
            sub["valueQuantity"] = c["valueQuantity"]
            out.append(sub)
    if out:
        return out
    codings = (res.get("code") or {}).get("coding", [])
    if codings:
        for cd in codings:
            cd["code"] = _map_loinc(str(cd.get("code")))
    return [res] if res.get("valueQuantity") else []


def import_bundle(store: Store, bundle: dict[str, Any], *, attending: str = "prac-rao") -> dict[str, Any]:
    """Import a single Synthea bundle. Returns a report; raises ValueError for non-bundles."""
    if bundle.get("resourceType") != "Bundle":
        raise ValueError("Expected a FHIR Bundle.")
    entries = [e for e in bundle.get("entry", []) if isinstance(e.get("resource"), dict)]
    idmap: dict[str, str] = {}
    keep: list[dict[str, Any]] = []
    skipped: dict[str, int] = {}
    for e in entries:
        res = e["resource"]
        rt = res.get("resourceType", "?")
        if rt not in KEEP:
            skipped[rt] = skipped.get(rt, 0) + 1
            continue
        raw = str(res.get("id") or uuid.uuid4())
        new_id = f"syn-{rt[:3].lower()}-{raw.replace('-', '')[:10]}"
        idmap[e.get("fullUrl", f"{rt}/{raw}")] = f"{rt}/{new_id}"
        idmap[f"{rt}/{raw}"] = f"{rt}/{new_id}"
        idmap[f"urn:uuid:{raw}"] = f"{rt}/{new_id}"
        res["id"] = new_id
        keep.append(res)
    _walk_refs(keep, idmap)

    out: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    mapped = {"conditions": 0, "observations": 0}
    dropped_invalid = 0
    for res in keep:
        rt = res["resourceType"]
        res.setdefault("meta", {})["tag"] = list(TAGS)
        items: list[dict[str, Any]] = [res]
        if rt == "Patient":
            nm = (res.get("name") or [{}])[0]
            text = " ".join(_clean_name(g) for g in (nm.get("given") or [])) + " " + _clean_name(nm.get("family", ""))
            text = text.strip() or res["id"]
            rng = random.Random(res["id"])
            mrn = next((i.get("value") for i in res.get("identifier", []) if (i.get("type") or {}).get("coding", [{}])[0].get("code") == "MR"), None) or f"SYN{rng.randint(100000, 999999)}"
            first = (text.split() or ["x"])[0]
            last = (text.split() or ["x"])[-1]
            res["name"] = [{"text": text, "family": _clean_name(nm.get("family", "")), "given": [_clean_name(g) for g in nm.get("given", [])]}]
            res["identifier"] = [
                {"type": {"text": "MRN"}, "value": mrn},
                {"type": {"text": "ABHA number"}, "value": abdm.make_abha(rng)},
                {"type": {"text": "ABHA address"}, "value": abdm.make_address(first, last, rng)},
            ]
            res["generalPractitioner"] = [{"reference": f"Practitioner/{attending}"}]
            for k in ("address", "telecom", "extension", "communication", "maritalStatus", "text"):
                res.pop(k, None)
        elif rt == "Condition":
            res["onsetDateTime"] = _norm_dt(res.get("onsetDateTime") or res.get("recordedDate"))
            if _canonical_condition_codes(res):
                mapped["conditions"] += 1
            else:
                codings = (res.get("code") or {}).get("coding", [])
                res["code"] = {"coding": codings, "text": re.sub(r"\s*\((disorder|finding|situation)\)$", "", (res.get("code") or {}).get("text") or (codings[0].get("display", "") if codings else ""))}
            res.setdefault("clinicalStatus", {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]})
            res.setdefault("category", [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-category", "code": "encounter-diagnosis"}]}])
        elif rt == "Observation":
            items = _convert_observation(res)
            mapped["observations"] += sum(1 for i in items if (T.LOINC_TO_VITAL.get(str(i["code"]["coding"][0].get("code"))) or T.LOINC_TO_LAB.get(str(i["code"]["coding"][0].get("code")))))
            for n, it in enumerate(items):
                if it is not res:
                    it["id"] = f"{res['id']}-{n}"
                it["status"] = "final"
        elif rt == "MedicationRequest":
            res["authoredOn"] = _norm_dt(res.get("authoredOn"))
            res.setdefault("intent", "order")
            res["status"] = res.get("status") if res.get("status") in ("active", "completed", "stopped") else "active"
            if not res.get("dosageInstruction"):
                res["dosageInstruction"] = [{"text": "As directed"}]
        elif rt == "Encounter":
            if isinstance(res.get("class"), list):
                res["class"] = res["class"][0]
            per = res.get("period") or {}
            res["period"] = {"start": _norm_dt(per.get("start")) or "1970-01-01T00:00:00Z", **({"end": _norm_dt(per["end"])} if per.get("end") else {})}
            res["status"] = "finished"
        elif rt == "DocumentReference":
            res["date"] = _norm_dt(res.get("date"))
        for it in items:
            if fhir.validate_resource(it):
                dropped_invalid += 1
                continue
            out.append(it)
            counts[it["resourceType"]] = counts.get(it["resourceType"], 0) + 1
    store.put_many(out)
    return {"imported": counts, "skipped": skipped, "dropped_invalid": dropped_invalid, "mapped": mapped, "total": len(out)}


def import_files(store: Store, paths: list[str], *, attending: str = "prac-rao") -> dict[str, Any]:
    """Import every `*.json` bundle under the given files/directories (skipping Synthea's hospital/practitioner info files)."""
    files: list[Path] = []
    for p in paths:
        pp = Path(p)
        files += sorted(pp.glob("*.json")) if pp.is_dir() else [pp]
    total: dict[str, Any] = {"files": 0, "imported": {}, "skipped": {}, "dropped_invalid": 0}
    for f in files:
        if f.name.startswith(("hospitalInformation", "practitionerInformation")):
            continue
        rep = import_bundle(store, json.loads(f.read_text(encoding="utf-8")), attending=attending)
        total["files"] += 1
        total["dropped_invalid"] += rep["dropped_invalid"]
        for k in ("imported", "skipped"):
            for rt, n in rep[k].items():
                total[k][rt] = total[k].get(rt, 0) + n
    return total


def demo_bundle(seed: int = 7) -> dict[str, Any]:
    """A tiny Synthea-shaped bundle: one patient with hypertension, T2DM, vitals, labs and a medication."""
    rng = random.Random(seed)
    pid, enc = str(uuid.UUID(int=rng.getrandbits(128))), str(uuid.UUID(int=rng.getrandbits(128)))
    pref = f"urn:uuid:{pid}"
    eref = f"urn:uuid:{enc}"

    def entry(res: dict[str, Any]) -> dict[str, Any]:
        rid = res.get("id") or str(uuid.UUID(int=rng.getrandbits(128)))
        res["id"] = rid
        return {"fullUrl": f"urn:uuid:{rid}", "resource": res, "request": {"method": "POST", "url": res["resourceType"]}}

    def obs(loinc: str, display: str, value: float, unit: str, when: str) -> dict[str, Any]:
        return {"resourceType": "Observation", "status": "final", "category": [{"coding": [{"code": "laboratory"}]}],
                "code": {"coding": [{"system": T.SYS_LOINC, "code": loinc, "display": display}], "text": display},
                "subject": {"reference": pref}, "encounter": {"reference": eref}, "effectiveDateTime": when,
                "valueQuantity": {"value": value, "unit": unit, "system": T.SYS_UCUM, "code": unit}}

    return {"resourceType": "Bundle", "type": "transaction", "entry": [
        entry({"resourceType": "Patient", "id": pid, "name": [{"use": "official", "family": "Hartmann123", "given": ["Elena45"]}], "gender": "female", "birthDate": "1961-04-12",
               "identifier": [{"type": {"coding": [{"code": "MR"}]}, "value": "SYN-MR-1042"}], "address": [{"city": "Chennai"}]}),
        entry({"resourceType": "Encounter", "id": enc, "status": "finished", "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
               "subject": {"reference": pref}, "period": {"start": "2025-11-02T09:00:00+05:30", "end": "2025-11-02T09:40:00+05:30"}}),
        entry({"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "active"}]}, "code": {"coding": [{"system": T.SYS_SNOMED, "code": "59621000", "display": "Essential hypertension (disorder)"}], "text": "Essential hypertension (disorder)"},
               "subject": {"reference": pref}, "encounter": {"reference": eref}, "onsetDateTime": "2015-06-01T10:00:00+05:30"}),
        entry({"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "active"}]}, "code": {"coding": [{"system": T.SYS_SNOMED, "code": "44054006", "display": "Diabetes mellitus type 2 (disorder)"}], "text": "Diabetes mellitus type 2 (disorder)"},
               "subject": {"reference": pref}, "encounter": {"reference": eref}, "onsetDateTime": "2018-09-14T10:00:00+05:30"}),
        entry({"resourceType": "Condition", "code": {"coding": [{"system": T.SYS_SNOMED, "code": "65363002", "display": "Otitis media (disorder)"}], "text": "Otitis media (disorder)"},
               "subject": {"reference": pref}, "onsetDateTime": "2019-01-20T10:00:00+05:30"}),
        entry({"resourceType": "Observation", "status": "final", "category": [{"coding": [{"code": "vital-signs"}]}],
               "code": {"coding": [{"system": T.SYS_LOINC, "code": "85354-9", "display": "Blood pressure panel"}], "text": "Blood pressure"},
               "subject": {"reference": pref}, "encounter": {"reference": eref}, "effectiveDateTime": "2025-11-02T09:10:00+05:30",
               "component": [{"code": {"coding": [{"system": T.SYS_LOINC, "code": "8480-6"}]}, "valueQuantity": {"value": 148, "unit": "mm[Hg]"}},
                             {"code": {"coding": [{"system": T.SYS_LOINC, "code": "8462-4"}]}, "valueQuantity": {"value": 92, "unit": "mm[Hg]"}}]}),
        entry(obs("8867-4", "Heart rate", 78, "/min", "2025-11-02T09:10:00+05:30")),
        entry(obs("38483-4", "Creatinine [Mass/volume] in Blood", 1.5, "mg/dL", "2025-11-02T09:20:00+05:30")),
        entry(obs("4548-4", "Hemoglobin A1c", 8.1, "%", "2025-11-02T09:20:00+05:30")),
        entry({"resourceType": "MedicationRequest", "status": "active", "intent": "order", "medicationCodeableConcept": {"coding": [{"system": T.SYS_RXNORM, "code": "6809", "display": "Metformin"}], "text": "Metformin 500 MG"},
               "subject": {"reference": pref}, "encounter": {"reference": eref}, "authoredOn": "2025-11-02T09:30:00+05:30"}),
        entry({"resourceType": "Claim", "status": "active", "patient": {"reference": pref}}),
        entry({"resourceType": "Organization", "name": "Synthea Demo Clinic"}),
    ]}
