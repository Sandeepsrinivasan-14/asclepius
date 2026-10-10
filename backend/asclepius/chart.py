"""Assemble a patient 'chart' (a read model over FHIR resources) used by the clinical modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from . import terminology as T
from .clinical import age_years, obs_code, obs_value
from .db import Store
from .fhir import decode_text


@dataclass
class Chart:
    patient: dict[str, Any]
    pid: str
    name: str
    sex: str
    age: int
    birth: str
    conditions: list[dict[str, Any]] = field(default_factory=list)
    meds: list[dict[str, Any]] = field(default_factory=list)
    allergies: list[dict[str, Any]] = field(default_factory=list)
    vitals: dict[str, list[tuple[str, float]]] = field(default_factory=dict)  # name -> [(iso, value)] ascending
    acvpu: list[tuple[str, str]] = field(default_factory=list)
    labs: dict[str, list[tuple[str, float, str]]] = field(default_factory=dict)  # key -> [(iso, value, obs_id)]
    notes: list[dict[str, Any]] = field(default_factory=list)
    encounter: dict[str, Any] | None = None
    ward: str | None = None
    bed: str | None = None
    pending: list[dict[str, Any]] = field(default_factory=list)

    def latest_vital(self, name: str) -> float | None:
        s = self.vitals.get(name)
        return s[-1][1] if s else None

    def latest_vitals(self) -> dict[str, Any]:
        out: dict[str, Any] = {k: self.latest_vital(k) for k in ("hr", "rr", "spo2", "temp", "sbp", "dbp", "o2flow")}
        out["acvpu"] = self.acvpu[-1][1] if self.acvpu else "Alert"
        out["time"] = self.vitals["hr"][-1][0] if self.vitals.get("hr") else None
        return out

    def latest_lab(self, key: str) -> float | None:
        s = self.labs.get(key)
        return s[-1][1] if s else None

    def condition_keys(self) -> set[str]:
        return {c["key"] for c in self.conditions if c.get("key")}

    @property
    def inpatient(self) -> bool:
        return bool(self.encounter and self.encounter.get("status") == "in-progress")


def _cond_key(res: dict[str, Any]) -> str | None:
    for c in (res.get("code") or {}).get("coding", []):
        for key, spec in T.CONDITIONS.items():
            if c.get("code") in (spec["snomed"], spec["icd10"]):
                return key
    return None


def build_chart(store: Store, pid: str) -> Chart | None:
    p = store.get("Patient", pid)
    if not p:
        return None
    nm = (p.get("name") or [{}])[0]
    sex = p.get("gender", "unknown")
    chart = Chart(patient=p, pid=pid, name=nm.get("text", pid), sex=sex, age=age_years(p["birthDate"], date.today()), birth=p["birthDate"])
    for c in store.search("Condition", patient=pid):
        chart.conditions.append({"id": c["id"], "key": _cond_key(c), "display": (c.get("code") or {}).get("text", ""), "onset": c.get("onsetDateTime"),
                                 "category": ((c.get("category") or [{}])[0].get("coding") or [{}])[0].get("code"), "status": ((c.get("clinicalStatus") or {}).get("coding") or [{}])[0].get("code")})
    for m in store.search("MedicationRequest", patient=pid):
        coding = ((m.get("medicationCodeableConcept") or {}).get("coding") or [{}])[0]
        key = next((k for k, v in T.MEDS.items() if v["rxnorm"] == coding.get("code")), None)
        chart.meds.append({"id": m["id"], "key": key, "display": (m.get("medicationCodeableConcept") or {}).get("text", ""), "sig": ((m.get("dosageInstruction") or [{}])[0]).get("text", ""),
                           "status": m.get("status"), "since": m.get("authoredOn")})
    for a in store.search("AllergyIntolerance", patient=pid):
        text = (a.get("code") or {}).get("text", "")
        key = "penicillin" if "penicillin" in text.lower() else "sulfa" if "sulfon" in text.lower() else "nsaid" if "anti-inflammatory" in text.lower() else "aspirin" if "aspirin" in text.lower() else None
        chart.allergies.append({"id": a["id"], "key": key, "display": text})
    for o in store.search("Observation", patient=pid):
        code = obs_code(o)
        t = o.get("effectiveDateTime", "")
        if code == T.ACVPU_CODE:
            chart.acvpu.append((t, o.get("valueString", "Alert")))
            continue
        val = obs_value(o)
        if val is None:
            continue
        if code in T.LOINC_TO_VITAL:
            chart.vitals.setdefault(T.LOINC_TO_VITAL[code], []).append((t, val))
        elif code in T.LOINC_TO_LAB:
            chart.labs.setdefault(T.LOINC_TO_LAB[code], []).append((t, val, o["id"]))
    for series in chart.vitals.values():
        series.sort()
    chart.acvpu.sort()
    for series in chart.labs.values():
        series.sort()
    for d in store.search("DocumentReference", patient=pid, order="desc"):
        chart.notes.append({"id": d["id"], "title": d.get("description", "Note"), "date": d.get("date"), "text": decode_text(d),
                            "author": ((d.get("author") or [{}])[0]).get("reference")})
    encs = store.search("Encounter", patient=pid, order="desc")
    if encs:
        active = [e for e in encs if e.get("status") == "in-progress"]
        chart.encounter = (active or encs)[0]
        if active:
            loc = (active[0].get("location") or [{}])[0]
            bed = (loc.get("physicalType") or {}).get("text")
            chart.bed, chart.ward = bed, (bed or "").split("-")[0] or None
    for s in store.search("ServiceRequest", patient=pid, status="active"):
        chart.pending.append({"id": s["id"], "text": (s.get("code") or {}).get("text", ""), "since": s.get("authoredOn")})
    return chart


def parse_iso(t: str) -> datetime:
    return datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
