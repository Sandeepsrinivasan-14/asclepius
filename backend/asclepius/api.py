"""HTTP API: FHIR R4 endpoints, SMART on FHIR (mock), ABDM mock and the clinical application routes."""

from __future__ import annotations

import asyncio
import json
import secrets
import tempfile
from typing import Any

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import (
    __version__,
    abdm,
    bodymap,
    calculators,
    cds,
    coding,
    copilot,
    discharge,
    fhir,
    hl7,
    imaging,
    medrec,
    portal,
    sbar,
    scribe,
    synthea,
    warning,
)
from . import governance as gov
from . import terminology as T
from . import termservice as TS
from .clinical import egfr_ckd_epi_2021, lab_flag, lab_range
from .db import iso, utcnow
from .security import AccessDenied, Principal, Security
from .state import AppState

router = APIRouter()
fhir_router = APIRouter()
cds_router = APIRouter()


# ------------------------------------------------------------------ plumbing
def get_state(request: Request) -> AppState:
    return request.app.state.asc


def get_principal(request: Request, state: AppState = Depends(get_state)) -> Principal:
    header = request.headers.get("authorization", "")
    token = header[7:] if header.lower().startswith("bearer ") else request.query_params.get("access_token", "")
    if not token:
        raise AccessDenied("not_authenticated", "Authentication required.", 401)
    return state.sec.verify(token)


def guard_patient(state: AppState, p: Principal, perm: str, pid: str, resource: str | None = None) -> None:
    state.sec.authorize_patient(p, perm, pid, resource=resource)


def clamp(v: float | None, lo: float, hi: float) -> float | None:
    return None if v is None else max(lo, min(hi, v))


def patient_summary(state: AppState, pid: str) -> dict[str, Any]:
    ch = state.chart(pid)
    assert ch is not None
    p = ch.patient
    ident = {i.get("type", {}).get("text"): i.get("value") for i in p.get("identifier", [])}
    n2 = warning.chart_news2(ch) if ch.inpatient else None
    tier = None
    if ch.inpatient:
        x = warning.chart_features(ch)
        tier = warning.risk_tier(state.model.predict_row(x)) if x is not None else None
    attrs = state.sec.attrs[pid]
    return {"id": pid, "name": ch.name, "age": ch.age, "sex": ch.sex, "birth_date": ch.birth, "mrn": ident.get("MRN"), "abha": ident.get("ABHA number"), "abha_address": ident.get("ABHA address"),
            "status": "inpatient" if ch.inpatient else "outpatient", "ward": ch.ward, "bed": ch.bed, "attending": attrs["attending"], "restricted": attrs["restricted"],
            "conditions": [c["display"] for c in ch.conditions][:4], "news2": None if not n2 else {"score": n2["score"], "risk": n2["risk"]}, "ml_tier": tier,
            "allergies": [a["display"] for a in ch.allergies]}


# ------------------------------------------------------------------ public
@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/meta")
def meta(state: AppState = Depends(get_state)) -> dict[str, Any]:
    s = state.store
    return {"name": "Asclepius", "version": __version__, "synthetic": True, "notice": "Every record is fabricated. Not a medical device. Not for clinical use.",
            "counts": {t: s.count(t) for t in ("Patient", "Observation", "Condition", "MedicationRequest", "Encounter", "DocumentReference")}, "inpatients": len(state.cohort.inpatients),
            "demo_auth": state.settings.demo_auth, "standards": ["HL7 FHIR R4", "SMART App Launch (PKCE)", "HL7 v2.5.1", "ABDM-aligned (mock)", "ICD-10", "SNOMED CT", "LOINC", "RxNorm", "UCUM"]}


@router.get("/auth/personas")
def personas() -> list[dict[str, Any]]:
    from .security import USERS
    return [{"username": u, "name": v["name"], "role": v["role"], "title": v["title"]} for u, v in USERS.items()]


class LoginBody(BaseModel):
    username: str
    password: str | None = None


@router.post("/auth/login")
def login(body: LoginBody, state: AppState = Depends(get_state)) -> dict[str, Any]:
    token, p = state.sec.login(body.username, body.password)
    return {"token": token, "user": p.public()}


@router.get("/auth/me")
def me(p: Principal = Depends(get_principal)) -> dict[str, Any]:
    return p.public()


# ------------------------------------------------------------------ patients
@router.get("/patients")
def patients(state: AppState = Depends(get_state), p: Principal = Depends(get_principal), q: str | None = None, status: str | None = None) -> dict[str, Any]:
    state.sec.require(p, "patient:read")
    ids = state.sec.listed_patients(p)
    rows = [patient_summary(state, pid) for pid in ids]
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in r["name"].lower() or ql in (r["mrn"] or "").lower() or ql in (r["abha"] or "") or any(ql in c.lower() for c in r["conditions"])]
    if status:
        rows = [r for r in rows if r["status"] == status]
    rows.sort(key=lambda r: (-(r["news2"]["score"] if r["news2"] else -1), r["name"]))
    state.store.audit(actor=p.username, role=p.role, action="patient:list", detail=f"{len(rows)} returned")
    return {"patients": rows, "total": len(rows)}


@router.get("/patients/lookup")
def lookup(q: str, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    """Find a patient by MRN, ABHA number or name. Inaccessible matches return minimal, non-clinical data."""
    state.sec.require(p, "patient:read")
    ql = q.strip().lower()
    if len(ql) < 3:
        raise AccessDenied("bad_request", "Enter at least 3 characters.", 422)
    out = []
    for pat in state.store.all_of("Patient"):
        ident = {i.get("type", {}).get("text"): i.get("value", "") for i in pat.get("identifier", [])}
        nm = (pat.get("name") or [{}])[0].get("text", "")
        if ql in nm.lower() or ql == ident.get("MRN", "").lower() or ql == ident.get("ABHA number", "").lower():
            ok, reason = state.sec.can_access_patient(p, pat["id"])
            if ok:
                out.append({**patient_summary(state, pat["id"]), "access": "granted", "reason": reason})
            else:
                initials = ".".join(w[0] for w in nm.split()) + "."
                out.append({"id": pat["id"], "name": initials, "mrn": ident.get("MRN"), "access": "break_glass_required" if state.sec.has(p, "break_glass") else "denied", "reason": reason})
    state.store.audit(actor=p.username, role=p.role, action="patient:lookup", detail=f"{len(out)} match(es)")
    return {"results": out[:10]}


@router.get("/patients/{pid}")
def patient(pid: str, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    reason = state.sec.authorize_patient(p, "patient:read", pid, resource="chart")
    ch = state.chart(pid)
    assert ch is not None
    labs = []
    for key, rows in ch.labs.items():
        t, val, _ = rows[-1]
        lo, hi = lab_range(key, ch.sex)
        labs.append({"key": key, "name": T.LABS[key]["display"].split(" [")[0].split(" (")[0], "value": val, "unit": T.LABS[key]["unit"], "time": t, "low": lo, "high": hi, "flag": lab_flag(key, val, ch.sex),
                     "previous": rows[-2][1] if len(rows) > 1 else None})
    cr = ch.labs.get("creatinine")
    n2 = warning.chart_news2(ch) if ch.inpatient else None
    x = warning.chart_features(ch) if ch.inpatient else None
    return {**patient_summary(state, pid), "access_reason": reason, "conditions_detail": ch.conditions, "medications": ch.meds, "allergies_detail": ch.allergies, "vitals": ch.latest_vitals(),
            "labs": sorted(labs, key=lambda r: (r["flag"] == "normal", r["name"])), "news2": n2, "ml_risk": None if x is None else round(state.model.predict_row(x), 3), "pending": ch.pending,
            "egfr": egfr_ckd_epi_2021(cr[-1][1], ch.age, ch.sex) if cr else None, "encounter": ch.encounter}


@router.get("/patients/{pid}/vitals")
def vitals(pid: str, hours: int = 48, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    guard_patient(state, p, "patient:read", pid, "vitals")
    ch = state.chart(pid)
    assert ch is not None
    series = {k: [{"t": t, "v": v} for t, v in rows][-max(hours, 1):] if ch.inpatient else [{"t": t, "v": v} for t, v in rows] for k, rows in ch.vitals.items()}
    return {"patient": pid, "series": series, "acvpu": [{"t": t, "v": v} for t, v in ch.acvpu][-hours:], "news2": warning.news2_series(ch, hours) if ch.inpatient else []}


@router.get("/patients/{pid}/labs")
def labs(pid: str, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    guard_patient(state, p, "patient:read", pid, "labs")
    ch = state.chart(pid)
    assert ch is not None
    out = []
    for key, rows in ch.labs.items():
        lo, hi = lab_range(key, ch.sex)
        out.append({"key": key, "name": T.LABS[key]["display"].split(" [")[0].split(" (")[0], "loinc": T.LABS[key]["loinc"], "unit": T.LABS[key]["unit"], "low": lo, "high": hi,
                    "series": [{"t": t, "v": v, "flag": lab_flag(key, v, ch.sex)} for t, v, _ in rows]})
    return {"patient": pid, "labs": sorted(out, key=lambda r: r["name"])}


@router.get("/patients/{pid}/timeline")
def timeline(pid: str, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    guard_patient(state, p, "patient:read", pid, "timeline")
    ch = state.chart(pid)
    assert ch is not None
    ev: list[dict[str, Any]] = []
    for e in state.store.search("Encounter", patient=pid):
        ev.append({"t": e["period"]["start"], "type": "encounter", "title": f"{e['class']['display'] if 'display' in e['class'] else e['class']['code']} encounter {e['status']}", "detail": (e.get("reasonCode") or [{}])[0].get("text", "")})
    for c in ch.conditions:
        ev.append({"t": c["onset"], "type": "condition", "title": c["display"], "detail": c["category"]})
    for m in ch.meds:
        ev.append({"t": m["since"], "type": "medication", "title": f"Started {m['display']}", "detail": m["sig"]})
    for key, rows in ch.labs.items():
        for t, v, _ in rows:
            fl = lab_flag(key, v, ch.sex)
            if fl != "normal" and key != "egfr":
                ev.append({"t": t, "type": "lab", "title": f"{T.LABS[key]['display'].split(' [')[0]} {v:g} {T.LABS[key]['unit']}", "detail": fl})
    if state.sec.has(p, "notes:read"):
        for n in ch.notes:
            ev.append({"t": n["date"], "type": "note", "title": n["title"], "detail": n["text"][:120]})
    ev = [e for e in ev if e["t"]]
    ev.sort(key=lambda e: e["t"], reverse=True)
    return {"patient": pid, "events": ev[:80]}


@router.get("/patients/{pid}/bodymap")
def patient_bodymap(pid: str, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    guard_patient(state, p, "patient:read", pid, "bodymap")
    ch = state.chart(pid)
    assert ch is not None
    return bodymap.body_map(ch)


@router.get("/patients/{pid}/discharge")
def patient_discharge(pid: str, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "notes:read")
    guard_patient(state, p, "patient:read", pid, "discharge-summary")
    ch = state.chart(pid)
    assert ch is not None
    names = []
    for prac in state.sec.attrs[pid]["attending"]:
        r = state.store.get("Practitioner", prac)
        if r:
            names.append((r.get("name") or [{}])[0].get("text", prac))
    return discharge.discharge_summary(ch, names)


@router.get("/calculators")
def calculator_catalog(p: Principal = Depends(get_principal)) -> dict[str, Any]:
    return {"calculators": calculators.catalog(), "note": "Decision support only; verify against current guidelines."}


@router.post("/calculators/{name}")
def calculator_run(name: str, body: dict[str, Any], p: Principal = Depends(get_principal)) -> dict[str, Any]:
    try:
        return calculators.run(name, body)
    except KeyError as e:
        raise AccessDenied("not_found", f"Unknown calculator '{name}'.", 404) from e
    except (ValueError, TypeError) as e:
        raise AccessDenied("bad_request", str(e), 422) from e


@router.get("/patients/{pid}/notes")
def notes(pid: str, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "notes:read")
    guard_patient(state, p, "notes:read", pid, "notes")
    ch = state.chart(pid)
    assert ch is not None
    return {"patient": pid, "notes": ch.notes}


# ------------------------------------------------------------------ terminology / coding
@router.get("/terminology/search")
def term_search(q: str, p: Principal = Depends(get_principal)) -> dict[str, Any]:
    return {"results": T.search_concepts(q)}


@router.get("/terminology/systems")
def term_systems(p: Principal = Depends(get_principal)) -> dict[str, Any]:
    return {"systems": TS.stats(), "note": "Hand-curated subsets, not the licensed releases."}


@router.get("/terminology/lookup")
def term_lookup(system: str, code: str, p: Principal = Depends(get_principal)) -> dict[str, Any]:
    found = TS.lookup(system, code)
    if found is None:
        raise AccessDenied("not_found", f"Code '{code}' not found in the embedded {system} subset.", 404)
    return {**found, "translations": TS.translate(system, code)}


@router.get("/terminology/validate")
def term_validate(system: str, code: str, display: str | None = None, p: Principal = Depends(get_principal)) -> dict[str, Any]:
    return TS.validate_code(system, code, display)


@router.get("/terminology/expand")
def term_expand(system: str, q: str = "", limit: int = 20, p: Principal = Depends(get_principal)) -> dict[str, Any]:
    if TS.system_key(system) is None:
        raise AccessDenied("bad_request", f"Unknown code system '{system}'. Use icd10, snomed, loinc or rxnorm.", 422)
    return {"system": system, "concepts": TS.expand(system, q, max(1, min(limit, 100)))}


class TextBody(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


@router.post("/coding/analyze")
def coding_analyze(body: TextBody, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "coding:read" if p.role == "nurse" else "coding:use")
    state.stats["coder_calls"] += 1
    return coding.analyze(body.text)


@router.get("/patients/{pid}/coding")
def patient_coding(pid: str, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "notes:read")
    guard_patient(state, p, "coding:read" if p.role == "nurse" else "coding:use", pid, "coding")
    ch = state.chart(pid)
    assert ch is not None
    out = []
    for n in ch.notes:
        out.append({"note": {"id": n["id"], "title": n["title"], "date": n["date"], "text": n["text"]}, **coding.analyze(n["text"])})
    return {"patient": pid, "notes": out, "threshold": coding.REVIEW_THRESHOLD}


class DecisionBody(BaseModel):
    patient_id: str | None = None
    model: str
    action: str
    reason: str | None = None


@router.post("/governance/feedback")
def feedback(body: DecisionBody, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "governance:feedback") if p.role not in ("nurse",) else None
    if body.patient_id:
        guard_patient(state, p, "patient:read", body.patient_id, "feedback")
    try:
        row = state.feedback.add(user=p.username, model=body.model, patient=body.patient_id, action=body.action, reason=body.reason)
    except ValueError as exc:
        raise AccessDenied("bad_request", str(exc), 422) from exc
    state.store.audit(actor=p.username, role=p.role, action="governance:feedback", patient=body.patient_id, detail=f"{body.model}:{body.action}")
    return row


# ------------------------------------------------------------------ copilot
@router.get("/patients/{pid}/copilot")
def patient_copilot(pid: str, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    guard_patient(state, p, "copilot:use", pid, "copilot")
    d = state.differential(pid)
    assert d is not None
    state.stats["verified" if d["verification"]["released"] else "blocked"] += 1
    return d


class VerifyBody(BaseModel):
    patient_id: str
    narrative: str = Field(min_length=1, max_length=8000)


@router.post("/copilot/verify")
def copilot_verify(body: VerifyBody, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    guard_patient(state, p, "copilot:use", body.patient_id, "copilot.verify")
    ch = state.chart(body.patient_id)
    assert ch is not None
    findings = copilot.extract_findings(ch)
    ranked = copilot.rank(findings)
    pct = {str(round(r["share"] * 100)) for r in ranked}
    res = copilot.verify(body.narrative, ch, findings.evidence, allowed_numbers=pct)
    state.stats["verified" if res["released"] else "blocked"] += 1
    return {**res, "evidence": [e.to_dict() for e in findings.evidence]}


# ------------------------------------------------------------------ early warning and monitor
@router.get("/patients/{pid}/warning")
def patient_warning(pid: str, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    guard_patient(state, p, "warning:read", pid, "warning")
    ch = state.chart(pid)
    assert ch is not None
    if not ch.inpatient:
        raise AccessDenied("not_inpatient", "Early-warning scores apply to inpatients with continuous observations.", 409)
    n2 = warning.chart_news2(ch)
    x = warning.chart_features(ch)
    prob = state.model.predict_row(x) if x is not None else None
    v = warning.chart_vitals_at(ch)
    return {"patient": pid, "news2": n2, "series": warning.news2_series(ch, 48), "qsofa": warning.qsofa(v) if v else None,
            "ml": None if prob is None else {"probability": round(prob, 4), "tier": warning.risk_tier(prob), "base_rate": round(state.model.base_rate(), 4), "explanation": state.model.explain_row(x)},
            "model": {k: v for k, v in state.model.metrics.items() if k != "calibration"}}


@router.get("/warning/overview")
def warning_overview(state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "warning:read")
    rows = []
    for pid in state.sec.visible_patients(p):
        ch = state.chart(pid)
        if not ch or not ch.inpatient:
            continue
        n2 = warning.chart_news2(ch)
        series = warning.news2_series(ch, 13)
        x = warning.chart_features(ch)
        prob = state.model.predict_row(x) if x is not None else None
        v = warning.chart_vitals_at(ch)
        rows.append({"id": pid, "name": ch.name, "age": ch.age, "sex": ch.sex, "ward": ch.ward, "bed": ch.bed, "news2": n2["score"] if n2 else None, "risk": n2["risk"] if n2 else None,
                     "news2_12h_ago": series[0]["score"] if series else None, "spark": [s["score"] for s in series], "qsofa": warning.qsofa(v)["score"] if v else None,
                     "ml_probability": None if prob is None else round(prob, 3), "ml_tier": None if prob is None else warning.risk_tier(prob), "dx": [c["display"] for c in ch.conditions if c["category"] == "encounter-diagnosis"][:2]})
    rows.sort(key=lambda r: -(r["news2"] or 0))
    return {"patients": rows, "counts": {"high": sum(1 for r in rows if r["risk"] == "high"), "medium": sum(1 for r in rows if r["risk"] in ("medium", "low-medium")), "low": sum(1 for r in rows if r["risk"] == "low")},
            "rising": sum(1 for r in rows if r["news2_12h_ago"] is not None and r["news2"] is not None and r["news2"] - r["news2_12h_ago"] >= 2)}


@router.get("/monitor/snapshot")
def monitor_snapshot(state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "monitor:read")
    ids = set(state.sec.visible_patients(p))
    live = state.sim.step()
    out = []
    for pid, v in live.items():
        if pid in ids:
            ch = state.chart(pid)
            assert ch is not None
            out.append({"id": pid, "name": ch.name, "age": ch.age, "sex": ch.sex, "ward": ch.ward, "bed": ch.bed, **v})
    out.sort(key=lambda r: -r["news2"])
    return {"patients": out, "t": iso(utcnow())}


@router.get("/monitor/stream")
async def monitor_stream(request: Request, interval: float = 1.0, limit: int | None = None, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> StreamingResponse:
    state.sec.require(p, "monitor:read")
    ids = set(state.sec.visible_patients(p))
    state.store.audit(actor=p.username, role=p.role, action="monitor:stream", detail=f"{len(ids)} patients")
    interval = max(0.2, min(interval, 10))

    async def gen():
        n = 0
        last_risk: dict[str, str] = {}
        while True:
            if await request.is_disconnected():
                break
            live = state.sim.step()
            data = {pid: v for pid, v in live.items() if pid in ids}
            alarms = []
            for pid, v in data.items():
                if last_risk.get(pid) and last_risk[pid] != v["risk"] and v["risk"] in ("medium", "high", "low-medium"):
                    alarms.append({"id": pid, "risk": v["risk"], "news2": v["news2"]})
                last_risk[pid] = v["risk"]
            yield f"data: {json.dumps({'t': iso(utcnow()), 'patients': data, 'alarms': alarms})}\n\n"
            n += 1
            if limit and n >= limit:
                break
            await asyncio.sleep(interval)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ------------------------------------------------------------------ medication reconciliation
class MedListBody(BaseModel):
    lists: list[dict[str, str]] = Field(default_factory=list, max_length=8)


@router.post("/patients/{pid}/medrec")
def patient_medrec(pid: str, body: MedListBody, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    guard_patient(state, p, "medrec:use" if state.sec.has(p, "medrec:use") else "medrec:read", pid, "medrec")
    ch = state.chart(pid)
    assert ch is not None
    return medrec.reconcile(ch, body.lists)


@router.get("/medrec/examples")
def medrec_examples(p: Principal = Depends(get_principal)) -> dict[str, Any]:
    return {"lists": [{"source": "Patient's own list", "text": "Glucophage 500 BD\nTelma 40 OD\nAmlong 5\nBrufen 400 TDS prn\nEcosprin 75 OD"},
                      {"source": "Discharge letter (other hospital)", "text": "Metformin 1000 mg twice daily; Amoxicillin 500 mg TDS; Atorvastatin 20 mg at night; Enalapril 5 mg OD"}]}


# ------------------------------------------------------------------ handoff
@router.get("/patients/{pid}/handoff")
def patient_handoff(pid: str, format: str = "json", state: AppState = Depends(get_state), p: Principal = Depends(get_principal)):
    guard_patient(state, p, "handoff:read", pid, "handoff")
    ch = state.chart(pid)
    assert ch is not None
    s = sbar.build(ch, state.model)
    if format == "text":
        return Response(sbar.to_text(s), media_type="text/plain")
    return s


@router.get("/handoff/ward/{ward}")
def ward_handoff(ward: str, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "handoff:read")
    ward = ward.upper()
    charts = [c for c in (state.chart(pid) for pid in state.sec.visible_patients(p)) if c]
    state.store.audit(actor=p.username, role=p.role, action="handoff:ward", detail=ward)
    return sbar.ward_handoff(charts, state.model, ward)


# ------------------------------------------------------------------ scribe
@router.get("/scribe/demos")
def scribe_demos(p: Principal = Depends(get_principal)) -> dict[str, Any]:
    return {"demos": [{"id": k, "title": t, "transcript": tx} for k, (t, tx) in scribe.DEMO_TRANSCRIPTS.items()]}


class DraftBody(BaseModel):
    transcript: str = Field(min_length=5, max_length=20000)
    patient_id: str | None = None


@router.post("/scribe/draft")
def scribe_draft(body: DraftBody, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "scribe:use")
    name = None
    if body.patient_id:
        guard_patient(state, p, "scribe:use", body.patient_id, "scribe.draft")
        name = state.chart(body.patient_id).name  # type: ignore[union-attr]
    return scribe.draft(body.transcript, body.patient_id, name)


class SignBody(BaseModel):
    patient_id: str
    transcript: str
    approve: list[str] | None = None


@router.post("/scribe/sign")
def scribe_sign(body: SignBody, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "patient:write")
    guard_patient(state, p, "patient:write", body.patient_id, "scribe.sign")
    d = scribe.draft(body.transcript, body.patient_id)
    res = scribe.sign(state.store, d, body.patient_id, p.practitioner, approve=body.approve)
    state.invalidate(body.patient_id)
    state.store.audit(actor=p.username, role=p.role, action="scribe:sign", patient=body.patient_id, detail=f"{res['count']} resources")
    state.feedback.add(user=p.username, model="scribe", patient=body.patient_id, action="accepted" if body.approve is None else "modified", reason=None)
    return res


@router.post("/scribe/audio")
async def scribe_audio(file: UploadFile = File(...), p: Principal = Depends(get_principal), state: AppState = Depends(get_state)) -> dict[str, Any]:
    state.sec.require(p, "scribe:use")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
        tmp.write(await file.read())
        tmp.flush()
        text = scribe.transcribe_audio(tmp.name)
    if text is None:
        raise AccessDenied("stt_unavailable", "Local speech-to-text is not installed. Install 'faster-whisper' or paste the transcript.", 501)
    return {"transcript": text}


# ------------------------------------------------------------------ portal
@router.get("/patients/{pid}/portal")
def patient_portal(pid: str, lang: str = "en", level: str = "simple", state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    guard_patient(state, p, "portal:read", pid, "portal")
    ch = state.chart(pid)
    assert ch is not None
    try:
        return portal.build(ch, lang, level)
    except ValueError as exc:
        raise AccessDenied("bad_request", str(exc), 422) from exc


# ------------------------------------------------------------------ interoperability
@router.post("/interop/hl7")
async def hl7_receive(request: Request, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "interop:use")
    raw = (await request.body()).decode("utf-8", errors="replace")
    a = state.pipeline.receive(raw)
    state.store.audit(actor=p.username, role=p.role, action="interop:hl7", detail=a.split("\r")[1][:60] if "\r" in a else "")
    return {"ack": a.replace("\r", "\n")}


@router.post("/interop/process")
def hl7_process(passes: int = 3, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "interop:use")
    res = state.pipeline.process(max_passes=max(1, min(passes, 5)))
    state.invalidate()
    return {**res, **state.pipeline.snapshot()}


@router.get("/interop/queue")
def hl7_queue(state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "interop:use")
    return state.pipeline.snapshot()


@router.get("/interop/demo")
def hl7_demo(state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "interop:use")
    pat = state.store.get("Patient", "pat-003")
    mrn = next(i["value"] for i in pat["identifier"] if i.get("type", {}).get("text") == "MRN")
    nm = pat["name"][0]
    return {"messages": [{**m, "raw": m["raw"].replace("\r", "\n")} for m in hl7.demo_messages(mrn, f"{nm['family']}^{nm['given'][0]}")]}


@router.post("/interop/dlq/{job_id}/replay")
def hl7_replay(job_id: int, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "interop:use")
    if not state.pipeline.replay(job_id):
        raise AccessDenied("not_found", "Dead-letter item not found.", 404)
    return {"replayed": job_id}


@router.get("/abdm/validate")
def abdm_validate(abha: str | None = None, address: str | None = None, p: Principal = Depends(get_principal)) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if abha:
        out["abha"] = abdm.validate_abha(abha)
    if address:
        out["address"] = abdm.validate_abha_address(address)
    return out


class ConsentBody(BaseModel):
    abha: str
    requester: str = "Asclepius Clinic (demo HIU)"
    purpose: str = "CAREMGT"
    hi_types: list[str]
    date_from: str = "2025-01-01"
    date_to: str = "2026-12-31"


@router.get("/abdm/catalog")
def abdm_catalog(p: Principal = Depends(get_principal)) -> dict[str, Any]:
    return {"purposes": abdm.PURPOSES, "hi_types": abdm.HI_TYPES}


@router.post("/abdm/consent-requests")
def abdm_consent_create(body: ConsentBody, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "interop:use")
    try:
        c = state.consents.create(abha=body.abha, requester=body.requester, purpose=body.purpose, hi_types=body.hi_types, date_from=body.date_from, date_to=body.date_to)
    except ValueError as exc:
        raise AccessDenied("bad_request", str(exc), 422) from exc
    state.store.audit(actor=p.username, role=p.role, action="abdm:consent.request", detail=f"{c.purpose} {','.join(c.hi_types)}")
    return c.to_dict()


@router.get("/abdm/consent-requests")
def abdm_consent_list(state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "interop:use")
    return {"items": [c.to_dict() for c in state.consents.items.values()]}


class DecideBody(BaseModel):
    grant: bool
    granted_types: list[str] | None = None


@router.post("/abdm/consent-requests/{cid}/decision")
def abdm_consent_decide(cid: str, body: DecideBody, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "interop:use")
    if cid not in state.consents.items:
        raise AccessDenied("not_found", "Consent request not found.", 404)
    try:
        c = state.consents.decide(cid, body.grant, body.granted_types)
    except ValueError as exc:
        raise AccessDenied("bad_request", str(exc), 409) from exc
    state.store.audit(actor=p.username, role=p.role, action="abdm:consent.decision", detail=f"{cid[:8]} {c.status}")
    return c.to_dict()


@router.post("/abdm/consents/{cid}/revoke")
def abdm_consent_revoke(cid: str, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "interop:use")
    if cid not in state.consents.items:
        raise AccessDenied("not_found", "Consent not found.", 404)
    return state.consents.revoke(cid).to_dict()


HI_TO_RESOURCES = {"Prescription": ["MedicationRequest"], "DiagnosticReport": ["Observation"], "OPConsultation": ["Condition", "Encounter", "DocumentReference"], "DischargeSummary": ["Composition", "DocumentReference"],
                   "ImmunizationRecord": [], "HealthDocumentRecord": ["DocumentReference"], "WellnessRecord": ["Observation"]}


@router.get("/abdm/health-information/{cid}")
def abdm_fetch(cid: str, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "interop:use")
    c = state.consents.items.get(cid)
    if not c:
        raise AccessDenied("not_found", "Consent not found.", 404)
    if c.status != "GRANTED":
        raise AccessDenied("consent_not_granted", f"Consent is {c.status}; health information cannot be released.", 403)
    pat = next((x for x in state.store.all_of("Patient") if any(i.get("value") == c.abha for i in x.get("identifier", []))), None)
    if not pat:
        raise AccessDenied("not_found", "No patient with this ABHA number.", 404)
    types = sorted({t for hi in c.granted_types for t in HI_TO_RESOURCES.get(hi, [])})
    entries = [pat]
    for t in types:
        for r in state.store.search(t, patient=pat["id"]):
            when = (r.get("effectiveDateTime") or r.get("authoredOn") or r.get("date") or r.get("onsetDateTime") or r.get("period", {}).get("start") or "")[:10]
            if not when or (c.date_from <= when <= c.date_to):
                entries.append(r)
    state.store.audit(actor=p.username, role=p.role, action="abdm:fetch", patient=pat["id"], detail=f"consent {cid[:8]} {len(entries)} resources")
    return {"consent": c.to_dict(), "released_resource_types": ["Patient", *types], "bundle": fhir.bundle(entries[:200], btype="collection", total=len(entries))}


# ------------------------------------------------------------------ access, audit
class BTGBody(BaseModel):
    patient_id: str
    reason: str


@router.post("/access/break-glass")
def break_glass(body: BTGBody, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    return state.sec.break_glass(p, body.patient_id, body.reason)


@router.get("/access/grants")
def my_grants(state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    now = utcnow()
    return {"grants": [{"patient": pid, "expires": iso(exp)} for (u, pid), exp in state.sec.grants.items() if u == p.username and exp > now]}


@router.get("/access/reviews")
def reviews(state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "access:review")
    return {"reviews": sorted(state.sec.reviews, key=lambda r: r["granted_at"], reverse=True)}


class ReviewBody(BaseModel):
    decision: str
    note: str = ""


@router.post("/access/reviews/{rid}")
def review(rid: str, body: ReviewBody, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    return state.sec.review(p, rid, body.decision, body.note)


@router.get("/audit")
def audit(limit: int = 100, break_glass_only: bool = False, patient: str | None = None, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "audit:read")
    return {"entries": state.store.audit_rows(min(limit, 500), break_glass_only=break_glass_only, patient=patient)}


@router.get("/audit/verify")
def audit_verify(state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "audit:read")
    return state.store.verify_audit()


# ------------------------------------------------------------------ governance
@router.get("/governance/models")
def gov_models(state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "governance:read")
    cev = state.copilot_eval()
    cev = {**cev, "blocked": state.stats["blocked"] or cev["blocked"]}
    sample = coding.analyze(" ".join(n["text"] for pid in list(state.cohort.truth)[:20] for n in (state.chart(pid).notes[:1])))  # type: ignore[union-attr]
    coder_eval = {"mentions": sample["summary"]["mentions"], "auto": sample["summary"]["auto_codes"], "review": sample["summary"]["review_codes"]}
    return {"models": gov.model_cards(state.model, cev, coder_eval), "calibration": state.model.metrics["calibration"], "verifier": state.stats}


@router.get("/governance/drift")
def gov_drift(state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "governance:read")
    return gov.drift_report(state.model, state.current_feature_matrix())


@router.get("/governance/fairness")
def gov_fairness(threshold: float = 0.15, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "governance:read")
    return gov.fairness_report(state.model, clamp(threshold, 0.02, 0.9) or 0.15)


@router.get("/governance/overrides")
def gov_overrides(state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "governance:read")
    return state.feedback.stats()


# ------------------------------------------------------------------ operations
@router.get("/ops/overview")
def ops_overview(state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "ops:read")
    return state.ops.overview()


@router.get("/ops/forecast")
def ops_forecast(horizon: int = 7, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "ops:read")
    return state.ops.forecast(max(3, min(horizon, 14)))


@router.get("/ops/opd")
def ops_opd(extra: str = "", state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "ops:read")
    add: dict[str, int] = {}
    for part in [x for x in extra.split("|") if x]:
        name, _, n = part.rpartition(":")
        try:
            add[name] = max(0, min(int(n), 4))
        except ValueError:
            continue
    return state.ops.opd(add)


class LosBody(BaseModel):
    age: float = Field(ge=0, le=120)
    ward: str
    acuity: float = Field(ge=0, le=20)
    comorbidities: int = Field(ge=0, le=15)
    emergency: bool = True


@router.post("/ops/los")
def ops_los(body: LosBody, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "ops:read")
    try:
        pred = state.ops.predict_los(age=body.age, ward=body.ward, acuity=body.acuity, comorbidities=body.comorbidities, emergency=body.emergency)
    except ValueError as exc:
        raise AccessDenied("bad_request", str(exc), 422) from exc
    return {**pred, "model": {"mae_days": state.ops.los_model["mae_days"], "r2_log": state.ops.los_model["r2_log"], "n_train": state.ops.los_model["n_train"]}}


@router.get("/ops/flow")
def ops_flow(state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "ops:read")
    return state.ops.flow()


@router.get("/ops/census")
def ops_census(state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    """Bed-level census with predicted remaining stay. Pseudonymous: no names."""
    state.sec.require(p, "ops:read")
    rows = []
    for pid in state.cohort.inpatients:
        ch = state.chart(pid)
        assert ch is not None
        n2 = warning.chart_news2(ch)
        comorb = len([c for c in ch.conditions if c["category"] == "problem-list-item"])
        pred = state.ops.predict_los(age=ch.age, ward=ch.ward or "MED", acuity=float(n2["score"] if n2 else 2), comorbidities=comorb, emergency=True)
        start = ch.encounter["period"]["start"] if ch.encounter else None
        elapsed = 0.0
        if start:
            from .chart import parse_iso
            elapsed = (utcnow() - parse_iso(start)).total_seconds() / 86400
        rows.append({"bed": ch.bed, "ward": ch.ward, "age_band": "65+" if ch.age >= 65 else "40-64" if ch.age >= 40 else "18-39", "news2": n2["score"] if n2 else None,
                     "elapsed_days": round(elapsed, 1), "predicted_total_days": pred["median_days"], "predicted_remaining_days": round(max(pred["median_days"] - elapsed, 0.3), 1)})
    rows.sort(key=lambda r: r["predicted_remaining_days"])
    return {"beds": rows, "expected_discharges_24h": sum(1 for r in rows if r["predicted_remaining_days"] <= 1.0), "expected_discharges_48h": sum(1 for r in rows if r["predicted_remaining_days"] <= 2.0)}


# ------------------------------------------------------------------ imaging
def _study(sid: str) -> imaging.Study:
    if sid not in imaging.STUDIES:
        raise AccessDenied("not_found", "Study not found.", 404)
    return imaging.STUDIES[sid]


_analysis_cache: dict[str, dict[str, Any]] = {}


@router.get("/imaging/studies")
def imaging_list(state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "imaging:read")
    return {"studies": [{"id": s.id, "title": s.title, "modality": s.modality, "slices": s.slices, "note": s.note} for s in imaging.STUDIES.values()]}


@router.get("/imaging/studies/{sid}")
def imaging_study(sid: str, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "imaging:read")
    s = _study(sid)
    if sid not in _analysis_cache:
        _analysis_cache[sid] = imaging.analyse(s)
    return {"metadata": imaging.metadata(s), "analysis": _analysis_cache[sid], "study": {"id": s.id, "title": s.title, "slices": s.slices, "note": s.note}}


@router.get("/imaging/studies/{sid}/slice/{i}.png")
def imaging_slice(sid: str, i: int, wl: float = 0.5, ww: float = 1.0, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> Response:
    state.sec.require(p, "imaging:read")
    s = _study(sid)
    if not 0 <= i < s.slices:
        raise AccessDenied("not_found", "Slice out of range.", 404)
    ww = max(0.05, min(ww, 2.0))
    return Response(imaging.to_png(imaging.render(s, i), (wl - ww / 2, wl + ww / 2)), media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


@router.get("/imaging/studies/{sid}/overlay/{i}.png")
def imaging_overlay(sid: str, i: int, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> Response:
    state.sec.require(p, "imaging:read")
    s = _study(sid)
    if not 0 <= i < s.slices:
        raise AccessDenied("not_found", "Slice out of range.", 404)
    d = imaging.detect(imaging.render(s, i), imaging.atlas(s, i), imaging.roi_mask(s, i))
    return Response(imaging.overlay_png(d["heat"]), media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


# ------------------------------------------------------------------ Synthea import
@router.get("/import/synthea/sample")
def synthea_sample(state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    state.sec.require(p, "interop:use")
    return synthea.demo_bundle()


@router.post("/import/synthea")
async def synthea_import(request: Request, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    """Import a Synthea FHIR transaction bundle (one patient per bundle). Imported patients join Dr. Rao's panel by default."""
    state.sec.require(p, "interop:use")
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise AccessDenied("bad_request", "Body is not valid JSON.", 400) from exc
    try:
        report = synthea.import_bundle(state.store, body, attending=request.query_params.get("attending", "prac-rao"))
    except ValueError as exc:
        raise AccessDenied("bad_request", str(exc), 422) from exc
    state.invalidate()
    state.store.audit(actor=p.username, role=p.role, action="import:synthea", detail=f"{report['total']} resource(s)")
    return report


# ------------------------------------------------------------------ SMART on FHIR (mock)
smart_router = APIRouter()


@smart_router.get("/.well-known/smart-configuration")
def smart_config(request: Request) -> dict[str, Any]:
    base = str(request.base_url).rstrip("/")
    return {"issuer": base, "authorization_endpoint": f"{base}/api/smart/authorize", "token_endpoint": f"{base}/api/smart/token", "grant_types_supported": ["authorization_code"],
            "code_challenge_methods_supported": ["S256"], "response_types_supported": ["code"], "scopes_supported": ["launch/patient", "patient/*.read", "patient/Observation.read", "patient/Patient.read", "user/*.read", "openid", "fhirUser"],
            "capabilities": ["launch-standalone", "client-public", "context-standalone-patient", "permission-patient", "permission-user", "sso-openid-connect"]}


@router.get("/smart/authorize")
def smart_authorize(request: Request, response_type: str, client_id: str, redirect_uri: str, scope: str, state: str = "", code_challenge: str = "", code_challenge_method: str = "S256",
                    login_hint: str = "dr.rao", launch_patient: str | None = None, st: AppState = Depends(get_state)):
    if response_type != "code":
        raise AccessDenied("unsupported_response_type", "Only response_type=code is supported.", 400)
    if not code_challenge:
        raise AccessDenied("invalid_request", "PKCE code_challenge is required.", 400)
    code = st.sec.smart_authorize(username=login_hint, client_id=client_id, redirect_uri=redirect_uri, scope=scope, challenge=code_challenge, method=code_challenge_method, patient=launch_patient)
    target = f"{redirect_uri}{'&' if '?' in redirect_uri else '?'}code={code}&state={state}"
    if "application/json" in request.headers.get("accept", ""):
        return {"redirect": target, "code": code, "state": state}
    return RedirectResponse(target)


@router.post("/smart/token")
async def smart_token(request: Request, st: AppState = Depends(get_state)) -> dict[str, Any]:
    form = await request.form()
    if form.get("grant_type") != "authorization_code":
        raise AccessDenied("unsupported_grant_type", "Only authorization_code is supported.", 400)
    return st.sec.smart_token(code=str(form.get("code", "")), verifier=str(form.get("code_verifier", "")), client_id=str(form.get("client_id", "")), redirect_uri=str(form.get("redirect_uri", "")))


# ------------------------------------------------------------------ FHIR REST
FHIR_CT = "application/fhir+json"
PATIENT_SCOPED = set(fhir.SUPPORTED) - {"Patient", "Practitioner", "Location"}


def fjson(body: dict[str, Any], status: int = 200) -> JSONResponse:
    return JSONResponse(body, status_code=status, media_type=FHIR_CT)


@fhir_router.get("/metadata")
def fhir_metadata(request: Request) -> JSONResponse:
    return fjson(fhir.capability_statement(str(request.base_url).rstrip("/") + "/fhir"))


def _check_scope(p: Principal, rtype: str) -> None:
    if not Security.scope_allows(p, rtype, "read"):
        raise AccessDenied("insufficient_scope", f"Token scope does not permit reading {rtype}.", 403)


def _params(items: list[tuple[str, Any]]) -> dict[str, Any]:
    out = []
    for name, val in items:
        key = "valueBoolean" if isinstance(val, bool) else "valueString"
        out.append({"name": name, key: val})
    return {"resourceType": "Parameters", "parameter": out}


@fhir_router.get("/CodeSystem/$lookup")
def fhir_lookup(system: str, code: str, p: Principal = Depends(get_principal)) -> JSONResponse:
    found = TS.lookup(system, code)
    if found is None:
        return fjson(fhir.operation_outcome("error", "not-found", f"Code '{code}' not found in {system}."), 404)
    return fjson(_params([("name", found["system"]), ("display", found["display"])]))


@fhir_router.get("/ValueSet/$validate-code")
def fhir_validate_code(system: str, code: str, display: str | None = None, p: Principal = Depends(get_principal)) -> JSONResponse:
    r = TS.validate_code(system, code, display)
    items: list[tuple[str, Any]] = [("result", r["result"]), ("message", r["message"])]
    if r.get("display"):
        items.append(("display", r["display"]))
    return fjson(_params(items))


@fhir_router.get("/ConceptMap/$translate")
def fhir_translate(system: str, code: str, p: Principal = Depends(get_principal)) -> JSONResponse:
    matches = TS.translate(system, code)
    return fjson({"resourceType": "Parameters", "parameter": [{"name": "result", "valueBoolean": bool(matches)}] + [
        {"name": "match", "part": [{"name": "equivalence", "valueCode": m["equivalence"]}, {"name": "concept", "valueCoding": {"system": m["system"], "code": m["code"], "display": m["display"]}}]} for m in matches]})


@fhir_router.get("/$export")
def fhir_export_start(state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> JSONResponse:
    """Bulk data export (simplified, synchronous kick-off): NDJSON per resource type for every patient the caller may see."""
    state.sec.require(p, "fhir:read")
    _check_scope(p, "Patient")
    files: dict[str, list[str]] = {}
    pids = state.sec.visible_patients(p)
    for pid in pids:
        state.store.audit(actor=p.username, role=p.role, action="fhir:export", patient=pid, resource="$export")
        for t in ["Patient", *sorted(PATIENT_SCOPED)]:
            if not Security.scope_allows(p, t, "read"):
                continue
            rows = [state.store.get("Patient", pid)] if t == "Patient" else state.store.search(t, patient=pid)
            files.setdefault(t, []).extend(json.dumps(r, separators=(",", ":")) for r in rows if r)
    jid = secrets.token_hex(8)
    state.exports[jid] = {"owner": p.username, "files": {t: "\n".join(v) + "\n" for t, v in files.items()}, "patients": len(pids)}
    return JSONResponse({"resourceType": "OperationOutcome", "issue": [{"severity": "information", "code": "informational", "diagnostics": f"Export {jid} accepted."}]},
                        status_code=202, media_type=FHIR_CT, headers={"Content-Location": f"/fhir/export/{jid}"})


def _export_job(state: AppState, p: Principal, jid: str) -> dict[str, Any]:
    job = state.exports.get(jid)
    if job is None or job["owner"] != p.username:
        raise AccessDenied("not_found", "Export job not found.", 404)
    return job


@fhir_router.get("/export/{jid}")
def fhir_export_status(jid: str, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> JSONResponse:
    job = _export_job(state, p, jid)
    out = [{"type": t, "url": f"/fhir/export/{jid}/{t}.ndjson", "count": body.count("\n")} for t, body in job["files"].items()]
    return JSONResponse({"transactionTime": iso(utcnow()), "request": "/fhir/$export", "requiresAccessToken": True, "output": out, "error": []}, media_type="application/json")


@fhir_router.get("/export/{jid}/{fname}")
def fhir_export_file(jid: str, fname: str, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> Response:
    job = _export_job(state, p, jid)
    body = job["files"].get(fname.removesuffix(".ndjson"))
    if body is None:
        raise AccessDenied("not_found", "No such export file.", 404)
    return Response(body, media_type="application/fhir+ndjson")


@fhir_router.get("/Patient/{pid}/$everything")
def fhir_everything(pid: str, request: Request, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> JSONResponse:
    state.sec.require(p, "fhir:read")
    _check_scope(p, "Patient")
    state.sec.authorize_patient(p, "fhir:read", pid, resource="Patient/$everything")
    ents = [state.store.get("Patient", pid)]
    for t in sorted(PATIENT_SCOPED):
        ents += state.store.search(t, patient=pid)
    return fjson(fhir.bundle([e for e in ents if e][:1500], btype="searchset", total=len(ents)))


@fhir_router.get("/{rtype}")
def fhir_search(rtype: str, request: Request, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> JSONResponse:
    if rtype not in fhir.SUPPORTED:
        return fjson(fhir.operation_outcome("error", "not-supported", f"Resource type '{rtype}' is not supported."), 404)
    state.sec.require(p, "fhir:read")
    _check_scope(p, rtype)
    q = dict(request.query_params)
    q.pop("access_token", None)
    count = max(1, min(int(q.get("_count", 50)), 200))
    offset = max(0, int(q.get("_offset", 0)))
    if rtype == "Patient":
        rows = []
        for pid in state.sec.visible_patients(p):
            pat = state.store.get("Patient", pid)
            assert pat
            nm = (pat.get("name") or [{}])[0].get("text", "").lower()
            if "name" in q and q["name"].lower() not in nm:
                continue
            if "_id" in q and q["_id"] != pid:
                continue
            if "gender" in q and q["gender"] != pat.get("gender"):
                continue
            if "birthdate" in q and not pat.get("birthDate", "").startswith(q["birthdate"].lstrip("eqgl")):
                continue
            if "identifier" in q and not any(i.get("value") == q["identifier"].split("|")[-1] for i in pat.get("identifier", [])):
                continue
            rows.append(pat)
        state.store.audit(actor=p.username, role=p.role, action="fhir:search", resource="Patient", detail=f"{len(rows)} result(s)")
        return fjson(fhir.bundle(rows[offset:offset + count], total=len(rows), self_link=str(request.url)))
    if rtype in ("Practitioner", "Location"):
        rows = state.store.all_of(rtype)
        if "name" in q:
            rows = [r for r in rows if q["name"].lower() in json.dumps(r.get("name", "")).lower()]
        return fjson(fhir.bundle(rows[offset:offset + count], total=len(rows)))
    pid = q.get("patient", "").replace("Patient/", "")
    if not pid:
        return fjson(fhir.operation_outcome("error", "required", "The 'patient' search parameter is required for this resource type."), 400)
    state.sec.authorize_patient(p, "fhir:read", pid, resource=rtype)
    since = until = None
    if "date" in q:
        for part in q["date"].split(","):
            if part.startswith("ge"):
                since = part[2:]
            elif part.startswith("le"):
                until = part[2:]
    rows = state.store.search(rtype, patient=pid, code=q.get("code", "").split("|")[-1] or None, status=q.get("status"), since=since, until=until, order="desc" if q.get("_sort", "").startswith("-") else "asc")
    if "category" in q:
        rows = [r for r in rows if any(c.get("code") == q["category"] for cat in r.get("category", []) for c in cat.get("coding", []))]
    return fjson(fhir.bundle(rows[offset:offset + count], total=len(rows), self_link=str(request.url)))


@fhir_router.get("/{rtype}/{rid}")
def fhir_read(rtype: str, rid: str, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> JSONResponse:
    if rtype not in fhir.SUPPORTED:
        return fjson(fhir.operation_outcome("error", "not-supported", f"Resource type '{rtype}' is not supported."), 404)
    state.sec.require(p, "fhir:read")
    _check_scope(p, rtype)
    res = state.store.get(rtype, rid)
    if not res:
        return fjson(fhir.operation_outcome("error", "not-found", f"{rtype}/{rid} not found."), 404)
    pid = res["id"] if rtype == "Patient" else (res.get("subject") or res.get("patient") or {}).get("reference", "").replace("Patient/", "")
    if pid:
        state.sec.authorize_patient(p, "fhir:read", pid, resource=f"{rtype}/{rid}")
    return fjson(res)


@fhir_router.post("/{rtype}")
async def fhir_create(rtype: str, request: Request, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> JSONResponse:
    state.sec.require(p, "fhir:write")
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return fjson(fhir.operation_outcome("error", "invalid", "Body is not valid JSON."), 400)
    if body.get("resourceType") != rtype:
        return fjson(fhir.operation_outcome("error", "invalid", f"resourceType must be '{rtype}'."), 400)
    problems = fhir.validate_resource(body)
    if problems:
        return fjson({"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "invalid", "diagnostics": m} for m in problems]}, 422)
    pid = (body.get("subject") or body.get("patient") or {}).get("reference", "").replace("Patient/", "") or None
    if rtype == "Patient":
        return fjson(fhir.operation_outcome("error", "not-supported", "Patient registration is performed through ADT messages."), 405)
    if pid:
        state.sec.authorize_patient(p, "fhir:write", pid, resource=rtype, detail="create")
    body.pop("id", None)
    body.setdefault("meta", {}).setdefault("tag", []).append({"system": "https://asclepius.example/tags", "code": "synthetic", "display": "Synthetic record"})
    saved = state.store.put(body)
    state.invalidate(pid)
    return JSONResponse(saved, status_code=201, media_type=FHIR_CT, headers={"Location": f"/fhir/{rtype}/{saved['id']}"})


# ------------------------------------------------------------------ CDS Hooks
@cds_router.get("")
def cds_discovery() -> dict[str, Any]:
    return cds.discovery()


class CdsRequest(BaseModel):
    hook: str
    hookInstance: str = ""
    context: dict[str, Any] = Field(default_factory=dict)


@cds_router.post("/{service_id}")
def cds_call(service_id: str, body: CdsRequest, state: AppState = Depends(get_state), p: Principal = Depends(get_principal)) -> dict[str, Any]:
    svc = next((x for x in cds.SERVICES if x["id"] == service_id), None)
    if svc is None or body.hook != svc["hook"]:
        raise AccessDenied("not_found", f"Unknown CDS service '{service_id}' for hook '{body.hook}'.", 404)
    pid = str(body.context.get("patientId", ""))
    if not pid:
        raise AccessDenied("bad_request", "context.patientId is required.", 422)
    guard_patient(state, p, "patient:read", pid, "cds-hooks")
    ch = state.chart(pid)
    assert ch is not None
    return {"cards": cds.patient_view_cards(ch)}
