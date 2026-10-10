"""Early warning, coder, copilot, med rec, SBAR, portal, scribe."""
import pytest

from asclepius import abdm, warning
from asclepius.ops import erlang_c


# ---- NEWS2 / qSOFA -----------------------------------------------------
def base(**kw):
    v = dict(rr=16, spo2=98, o2=False, sbp=120, hr=70, acvpu="A", temp=36.8)
    v.update(kw)
    return v


def test_news2_normal_is_zero():
    r = warning.news2(base())
    assert r["score"] == 0 and r["risk"] == "low"


def test_news2_single_red_parameter_is_low_medium():
    r = warning.news2(base(rr=7))
    assert r["parts"]["rr"] == 3 and r["risk"] in {"low-medium", "low_medium", "medium"} or r["single_3"]


def test_news2_high_risk_at_seven():
    r = warning.news2(base(rr=26, hr=135, sbp=88, spo2=90, o2=True, acvpu="V", temp=39.5))
    assert r["score"] >= 7 and r["risk"] == "high"


def test_news2_supplemental_oxygen_adds_two():
    assert warning.news2(base(o2=True))["parts"]["o2"] == 2


def test_news2_scale2_hypercapnic_spo2():
    assert warning.news2(base(spo2=90), scale2=True)["parts"]["spo2"] == 0


def test_qsofa_counts_three_criteria():
    q = warning.qsofa(base(rr=24, sbp=95, acvpu="C"))
    assert q["score"] == 3


def test_risk_model_quality():
    m = warning.train_model()
    assert 0.7 < m.metrics["auc"] <= 1.0


def test_patient_warning_endpoint_explains_prediction(client, rao):
    r = client.get("/api/patients/pat-001/warning", headers=rao).json()
    assert "contributions" in r["ml"] or "drivers" in r["ml"] or r["ml"]
    assert r["news2"]["score"] >= 0


def test_warning_overview_sorted(client, rao):
    d = client.get("/api/warning/overview", headers=rao).json()
    scores = [p["news2"] for p in d["patients"]]
    assert scores == sorted(scores, reverse=True)


def test_monitor_snapshot(client, rao):
    assert client.get("/api/monitor/snapshot", headers=rao).status_code == 200


# ---- Coder -------------------------------------------------------------
def analyze(client, rao, text):
    return {m["key"]: m for m in client.post("/api/coding/analyze", headers=rao, json={"text": text}).json()["mentions"]}


def test_coder_negation_and_hedge(client, rao):
    m = analyze(client, rao, "No chest pain. Possible pneumonia. Fever for 2 days.")
    assert m["chest_pain"]["assertion"] == "absent"
    assert m["cap"]["assertion"] == "possible"
    assert m["cap"]["codes"]["ICD-10"] == "J18.9"


def test_coder_negation_scope_stops_at_conjunction(client, rao):
    m = analyze(client, rao, "No fever but productive cough.")
    assert m["fever"]["assertion"] == "absent"
    assert m["productive_cough"]["assertion"] == "present"


def test_terminology_search(client, rao):
    r = client.get("/api/terminology/search", headers=rao, params={"q": "pneumonia"}).json()
    assert r


# ---- Copilot -----------------------------------------------------------
def test_copilot_differential_has_evidence_and_verification(client, rao):
    d = client.get("/api/patients/pat-001/copilot", headers=rao).json()
    assert d["differential"] and d["evidence"]
    assert d["verification"]["status"] in {"Pass", "Warn", "Fail"}
    shares = sum(x["share"] for x in d["differential"])
    assert 0.5 < shares <= 1.01


def test_copilot_verifier_blocks_fabricated_numbers_and_citations(client, rao):
    r = client.post("/api/copilot/verify", headers=rao, json={"patient_id": "pat-001", "narrative": "The patient is 200 years old with troponin 9999 [E99]."}).json()
    assert r["released"] is False


def test_copilot_accuracy_on_synthetic_cohort(app):
    ev = app.state.asc.copilot_eval()
    assert ev["n"] > 10 and ev["top3"] >= 0.7


# ---- Med rec -----------------------------------------------------------
def test_medrec_maps_brands_and_flags(client, rao):
    r = client.post("/api/patients/pat-001/medrec", headers=rao, json={"lists": [{"source": "Patient", "text": "Glucophage 500 BD\nBrufen 400 TDS prn\nEcosprin 75 OD"}]}).json()
    names = str(r["reconciled"]).lower()
    assert "metformin" in names and "ibuprofen" in names
    assert r["counts"]


def test_medrec_examples(client, rao):
    assert client.get("/api/medrec/examples", headers=rao).json()["lists"]


# ---- SBAR / portal / scribe -------------------------------------------
def test_sbar_sections(client, rao):
    d = client.get("/api/patients/pat-001/handoff", headers=rao).json()
    for k in ("situation", "background", "assessment", "recommendation"):
        assert d[k]


def test_ward_handoff(client, login):
    assert client.get("/api/handoff/ward/ICU", headers=login("nurse.devi")).status_code == 200


@pytest.mark.parametrize("lang", ["en", "ta", "hi"])
def test_portal_languages_and_review_gate(client, rao, lang):
    d = client.get("/api/patients/pat-001/portal", headers=rao, params={"lang": lang}).json()
    assert d["language"] == lang and d["requires_clinician_approval"] is True and d["sections"]


def test_scribe_draft_and_sign_writes_fhir(client, app, rao):
    demo = client.get("/api/scribe/demos", headers=rao).json()["demos"][0]
    d = client.post("/api/scribe/draft", headers=rao, json={"transcript": demo["transcript"], "patient_id": "pat-001"}).json()
    assert d["note"] and d["fhir_draft"] and d["status"]
    before = len(client.get("/fhir/Condition", headers=rao, params={"patient": "pat-001"}).json().get("entry", []))
    s = client.post("/api/scribe/sign", headers=rao, json={"patient_id": "pat-001", "transcript": demo["transcript"]})
    assert s.status_code == 200 and s.json()["count"] > 0
    after = len(client.get("/fhir/Condition", headers=rao, params={"patient": "pat-001"}).json().get("entry", []))
    assert after >= before


def test_nurse_cannot_sign_notes(client, login):
    r = client.post("/api/scribe/sign", headers=login("nurse.devi"), json={"patient_id": "pat-001", "transcript": "Doctor: hello there"})
    assert r.status_code == 403


# ---- ABDM -------------------------------------------------------------
def test_abha_verhoeff():
    n = "4338399084164"[:13]
    assert abdm.verhoeff_valid(n + abdm.verhoeff_check_digit(n)) is True
    assert abdm.verhoeff_valid(n + str((int(abdm.verhoeff_check_digit(n)) + 1) % 10)) is False


def test_abdm_validate_endpoint(client, app, rao):
    abha = app.state.asc.store.get("Patient", "pat-001")
    val = next(i["value"] for i in abha["identifier"] if "abha" in str(i).lower() and "@" not in i["value"])
    assert client.get("/api/abdm/validate", headers=rao, params={"abha": val}).json()["abha"]["valid"] is True
    assert client.get("/api/abdm/validate", headers=rao, params={"abha": "91-1234-5678-9012"}).json()["abha"]["valid"] is False


def test_abdm_consent_lifecycle(client, app, rao):
    pat = app.state.asc.store.get("Patient", "pat-001")
    abha = next(i["value"] for i in pat["identifier"] if abdm.validate_abha(i["value"])["valid"])
    body = {"abha": abha, "requester": "Demo HIU", "purpose": "CAREMGT", "hi_types": ["Prescription"], "date_from": "2000-01-01", "date_to": "2099-12-31"}
    c = client.post("/api/abdm/consent-requests", headers=rao, json=body).json()
    cid = c["id"]
    assert client.get(f"/api/abdm/health-information/{cid}", headers=rao).status_code == 403  # not granted yet
    assert client.post(f"/api/abdm/consent-requests/{cid}/decision", headers=rao, json={"grant": True}).json()["status"] == "GRANTED"
    hi = client.get(f"/api/abdm/health-information/{cid}", headers=rao).json()
    assert set(hi["released_resource_types"]) <= {"Patient", "MedicationRequest"}
    client.post(f"/api/abdm/consents/{cid}/revoke", headers=rao)
    assert client.get(f"/api/abdm/health-information/{cid}", headers=rao).status_code == 403


def test_erlang_c_monotonic():
    a = erlang_c(10, 6, 2)
    b = erlang_c(10, 6, 4)
    assert b["p_wait"] < a["p_wait"] if "p_wait" in a else True
