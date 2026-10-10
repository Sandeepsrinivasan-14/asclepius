"""Calculators, CDS Hooks, bulk export and clinical helper coverage."""

import pytest

from asclepius import calculators, cds
from asclepius.clinical import age_band, age_years, ckd_stage, lab_flag, lab_range, obs_code, obs_value


def test_cha2ds2_vasc_scores():
    r = calculators.run("cha2ds2-vasc", {"age": 78, "sex": "female", "hypertension": True, "diabetes": True})
    assert r["score"] == 2 + 1 + 1 + 1 and r["band"] == "high"
    assert calculators.run("cha2ds2-vasc", {"age": 40, "sex": "male"})["band"] == "low"
    assert calculators.run("cha2ds2-vasc", {"age": 70, "sex": "male"})["band"] == "moderate"


def test_curb65_bands():
    base = {"age": 40, "urea_mmol_l": 5, "resp_rate": 16, "sbp": 120, "dbp": 80}
    assert calculators.run("curb65", base)["score"] == 0
    assert calculators.run("curb65", {**base, "confusion": True, "age": 70})["band"] == "moderate"
    sev = calculators.run("curb65", {**base, "confusion": True, "age": 70, "urea_mmol_l": 9, "resp_rate": 32})
    assert sev["score"] == 4 and sev["band"] == "high"


def test_cockcroft_bmi_calcium():
    assert calculators.run("cockcroft-gault", {"age": 60, "sex": "male", "weight_kg": 80, "creatinine_mg_dl": 1.0})["score"] == 88.9
    f = calculators.run("cockcroft-gault", {"age": 60, "sex": "female", "weight_kg": 80, "creatinine_mg_dl": 2.0})
    assert f["band"] == "moderate"
    b = calculators.run("bmi-bsa", {"height_cm": 170, "weight_kg": 70})
    assert b["score"] == 24.2 and b["band"] == "healthy" and b["bsa_m2"] == 1.82
    assert calculators.run("corrected-calcium", {"calcium_mg_dl": 8.0, "albumin_g_dl": 2.0})["score"] == 9.6


def test_calculator_validation():
    with pytest.raises(ValueError):
        calculators.run("bmi-bsa", {"height_cm": 170})
    with pytest.raises(ValueError):
        calculators.run("cockcroft-gault", {"age": 1, "sex": "m", "weight_kg": 1, "creatinine_mg_dl": 0})
    with pytest.raises(KeyError):
        calculators.run("nope", {})


def test_calculator_endpoints(client, rao):
    cat = client.get("/api/calculators", headers=rao).json()["calculators"]
    assert {c["id"] for c in cat} >= {"curb65", "bmi-bsa"}
    ok = client.post("/api/calculators/bmi-bsa", json={"height_cm": 180, "weight_kg": 90}, headers=rao)
    assert ok.status_code == 200 and ok.json()["score"] == 27.8
    assert client.post("/api/calculators/bmi-bsa", json={}, headers=rao).status_code == 422
    assert client.post("/api/calculators/zzz", json={}, headers=rao).status_code == 404
    assert client.get("/api/calculators").status_code == 401


def _inpatient(client, h):
    return client.get("/api/patients?status=inpatient", headers=h).json()["patients"][0]["id"]


def test_cds_discovery_and_cards(client, rao):
    assert client.get("/cds-services").json()["services"][0]["hook"] == "patient-view"
    rows = client.get("/api/patients?status=inpatient", headers=rao).json()["patients"]
    seen = []
    for r in rows:
        resp = client.post("/cds-services/asclepius-patient-view", json={"hook": "patient-view", "context": {"patientId": r["id"]}}, headers=rao)
        assert resp.status_code == 200
        seen += resp.json()["cards"]
    assert seen and all(c["indicator"] in {"info", "warning", "critical"} and c["source"]["label"] for c in seen)


def test_cds_errors_and_access(client, rao, login):
    pid = _inpatient(client, rao)
    call = lambda body, h: client.post("/cds-services/asclepius-patient-view", json=body, headers=h)  # noqa: E731
    assert call({"hook": "order-select", "context": {"patientId": pid}}, rao).status_code == 404
    assert call({"hook": "patient-view", "context": {}}, rao).status_code == 422
    assert call({"hook": "patient-view", "context": {"patientId": pid}}, {}).status_code == 401
    assert call({"hook": "patient-view", "context": {"patientId": "pat-001"}}, login("auditor.menon")).status_code == 403
    assert call({"hook": "patient-view", "context": {"patientId": "missing"}}, rao).status_code == 404


def test_cds_card_logic():
    class C:  # minimal stand-in chart
        pid, sex, inpatient, labs = "x", "male", False, {"lactate": [("t", 6.0, "o")], "bogus": [("t", 1, "o")], "sodium": []}
    cards = cds.patient_view_cards(C())  # type: ignore[arg-type]
    assert any("Critical result" in c["summary"] for c in cards)


def test_bulk_export_flow(client, rao, login):
    r = client.get("/fhir/$export", headers=rao)
    assert r.status_code == 202
    loc = r.headers["content-location"]
    status = client.get(loc, headers=rao)
    assert status.status_code == 200
    out = status.json()["output"]
    assert any(o["type"] == "Patient" and o["count"] > 0 for o in out)
    nd = client.get(out[0]["url"], headers=rao)
    assert nd.headers["content-type"].startswith("application/fhir+ndjson")
    assert nd.text.count("\n") == out[0]["count"]
    # another user cannot read this job; unknown files 404
    assert client.get(loc, headers=login("dr.chandran")).status_code == 404
    assert client.get(loc + "/Nothing.ndjson", headers=rao).status_code == 404
    assert client.get("/fhir/$export").status_code == 401
    audit = client.get("/api/audit?limit=500", headers=login("auditor.menon")).json()
    assert any(e.get("action") == "fhir:export" for e in (audit.get("entries") or audit.get("events") or []))


def test_clinical_helpers():
    assert age_years("2000-06-15") >= 25
    assert [age_band(a) for a in (5, 30, 50, 80)] == ["0-17", "18-39", "40-64", "65+"]
    assert [ckd_stage(x) for x in (95, 70, 50, 35, 20, 5)] == ["G1", "G2", "G3a", "G3b", "G4", "G5"]
    assert lab_range("hemoglobin", "female") == (12.0, 15.5) and lab_range("hemoglobin", "male") == (13.0, 17.0)
    assert lab_flag("hemoglobin", 5, "male") in {"low", "critical-low"}
    assert obs_value({"valueQuantity": {"value": 3}}) == 3.0 and obs_value({}) is None
    assert obs_code({"code": {"coding": [{"code": "x"}]}}) == "x" and obs_code({}) is None


def test_endpoint_sweep_across_roles(client, login, rao):
    personas = client.get("/api/auth/personas").json()
    users = [p["username"] for p in (personas["personas"] if isinstance(personas, dict) else personas)]
    assert len(users) >= 4
    pid = _inpatient(client, rao)
    paths = ["/api/auth/me", "/api/patients", f"/api/patients/{pid}", f"/api/patients/{pid}/vitals?hours=6", f"/api/patients/{pid}/labs",
             f"/api/patients/{pid}/timeline", f"/api/patients/{pid}/notes", f"/api/patients/{pid}/copilot", f"/api/patients/{pid}/coding",
             f"/api/patients/{pid}/warning", f"/api/patients/{pid}/handoff", f"/api/patients/{pid}/portal?lang=ta", f"/api/patients/{pid}/discharge",
             "/api/patients/lookup?q=jo", "/api/patients/lookup?q=thomas", "/api/monitor/snapshot", "/api/warning/overview", "/api/governance/models",
             "/api/governance/drift", "/api/governance/fairness", "/api/governance/overrides", "/api/ops/overview", "/api/ops/forecast",
             "/api/ops/opd?extra=Clinic:1", "/api/ops/flow", "/api/ops/census", "/api/imaging/studies", "/api/audit", "/api/audit/verify",
             "/api/access/grants", "/api/access/reviews", "/api/abdm/catalog", "/api/interop/queue", "/api/scribe/demos"]
    for u in users:
        h = login(u)
        for path in paths:
            r = client.get(path, headers=h)
            assert r.status_code in {200, 403, 404, 422}, (u, path, r.status_code, r.text[:200])
            assert r.status_code != 500


def test_lookup_hides_clinical_data_without_access(client, login):
    r = client.get("/api/patients/lookup?q=ab", headers=login("dr.chandran"))
    assert r.status_code == 422
