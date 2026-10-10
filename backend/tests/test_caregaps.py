"""Care gaps, lab delta checks / KDIGO AKI, and extra coverage for clinical helpers and endpoints."""

from datetime import date, timedelta

from asclepius import caregaps, deltacheck
from asclepius.chart import Chart
from asclepius.clinical import (
    age_band,
    age_years,
    ckd_stage,
    egfr_ckd_epi_2021,
    lab_flag,
    lab_range,
    obs_code,
    obs_value,
)


def _chart(age=70, sex="female", keys=(), labs=None, meds=(), sbp=None):
    c = Chart(patient={}, pid="x", name="T", sex=sex, age=age, birth="1950-01-01")
    c.conditions = [{"key": k} for k in keys]
    c.labs = labs or {}
    c.meds = [{"key": m} for m in meds]
    if sbp:
        c.vitals = {"sbp": [("2026-01-01T00:00:00Z", sbp)], "dbp": [("2026-01-01T00:00:00Z", 85)]}
    return c


def _ts(days_ago):
    return (date(2026, 6, 1) - timedelta(days=days_ago)).isoformat() + "T00:00:00+00:00"


def test_care_gaps_by_age_and_sex():
    r = caregaps.care_gaps(_chart(age=70, sex="female"), date(2026, 6, 1))
    ids = {g["id"] for g in r["gaps"]}
    assert {"imm-pneumococcal", "imm-zoster", "scr-colorectal", "scr-breast", "scr-lipids"} <= ids
    assert "scr-cervical" not in ids
    young = {g["id"] for g in caregaps.care_gaps(_chart(age=25, sex="male"), date(2026, 6, 1))["gaps"]}
    assert "imm-pneumococcal" not in young and "scr-breast" not in young
    assert "scr-cervical" in {g["id"] for g in caregaps.care_gaps(_chart(age=30, sex="female"), date(2026, 6, 1))["gaps"]}
    assert caregaps.care_gaps(_chart(age=10), date(2026, 6, 1))["gaps"] == []


def test_chronic_monitoring_gaps():
    today = date(2026, 6, 1)
    fresh = {"hba1c": [(_ts(30), 7.0, "o1")], "creatinine": [(_ts(30), 1.0, "o2")]}
    met = {g["id"]: g["status"] for g in caregaps.care_gaps(_chart(keys=["t2dm"], labs=fresh, meds=["atorvastatin"]), today)["gaps"]}
    assert met["chr-hba1c"] == "met" and met["chr-renal"] == "met" and "chr-statin" not in met
    stale = {"hba1c": [(_ts(400), 7.0, "o1")]}
    bad = {g["id"]: g for g in caregaps.care_gaps(_chart(keys=["t2dm"], labs=stale), today)["gaps"]}
    assert bad["chr-hba1c"]["status"] == "overdue" and "400 days" in bad["chr-hba1c"]["detail"]
    assert bad["chr-renal"]["status"] == "overdue" and bad["chr-statin"]["status"] == "overdue"


def test_condition_specific_gaps():
    today = date(2026, 6, 1)
    g = {x["id"]: x["status"] for x in caregaps.care_gaps(_chart(keys=["htn", "af", "mi", "hypothyroid", "ckd3"], sbp=150), today)["gaps"]}
    assert g["chr-bp"] == "overdue" and g["chr-anticoag"] == "overdue" and g["chr-secondary"] == "overdue"
    assert g["chr-tsh"] == "overdue" and g["chr-egfr"] == "overdue"
    ok = {x["id"]: x["status"] for x in caregaps.care_gaps(_chart(keys=["htn", "af"], sbp=120, meds=["warfarin"]), today)["gaps"]}
    assert ok["chr-bp"] == "met" and "chr-anticoag" not in ok


def test_delta_checks():
    labs = {"potassium": [(_ts(1), 4.0, "a"), (_ts(0), 5.4, "b")], "sodium": [(_ts(1), 140, "c"), (_ts(0), 139, "d")],
            "platelets": [(_ts(10), 300, "e"), (_ts(0), 100, "f")]}
    flagged = {d["analyte"] for d in deltacheck.delta_checks(_chart(labs=labs))}
    assert flagged == {"potassium"}  # sodium stable; platelets outside the 72 h window


def _stage(prev, now, days=1):
    return deltacheck.kdigo_aki(_chart(labs={"creatinine": [(_ts(days), prev, "a"), (_ts(0), now, "b")]}))["stage"]


def test_kdigo_aki_stages():
    assert deltacheck.kdigo_aki(_chart())["stage"] == 0
    assert deltacheck.kdigo_aki(_chart(labs={"creatinine": [(_ts(0), 1.0, "a")]}))["stage"] == 0
    assert _stage(1.0, 2.0, 30) == 0  # baseline older than 7 days
    assert _stage(1.0, 1.1) == 0
    assert _stage(1.0, 1.3) == 1 and _stage(1.0, 1.6, 5) == 1
    assert _stage(1.0, 2.1) == 2
    assert _stage(1.0, 3.2) == 3 and _stage(2.0, 4.2) == 3


def test_caregap_and_labreview_endpoints(client, rao):
    pid = client.get("/api/patients", headers=rao).json()["patients"][0]["id"]
    g = client.get(f"/api/patients/{pid}/caregaps", headers=rao)
    assert g.status_code == 200 and "gaps" in g.json()
    lr = client.get(f"/api/patients/{pid}/labreview", headers=rao)
    assert lr.status_code == 200 and "aki" in lr.json()
    assert client.get(f"/api/patients/{pid}/caregaps").status_code == 401


def test_caregap_endpoints_are_audited_and_scoped(client, rao, login):
    pid = client.get("/api/patients", headers=rao).json()["patients"][0]["id"]
    client.get(f"/api/patients/{pid}/labreview", headers=rao)
    assert "labreview" in str(client.get("/api/audit?limit=30", headers=login("auditor.menon")).json())
    assert client.get(f"/api/patients/{pid}/caregaps", headers=login("admin.kumar")).status_code == 403


def test_quality_caregaps_population(client, rao, login):
    r = client.get("/api/quality/caregaps", headers=rao)
    assert r.status_code == 200
    body = r.json()
    assert body["measures"] and all(0 <= m["rate"] <= 1 for m in body["measures"])
    assert len(body["most_open"]) <= 5
    assert client.get("/api/quality/caregaps", headers=login("admin.kumar")).status_code == 403


def test_clinical_helpers():
    assert age_years("2000-06-15", date(2026, 6, 14)) == 25 and age_years("2000-06-15", date(2026, 6, 15)) == 26
    assert [age_band(a) for a in (5, 20, 50, 80)] == ["0-17", "18-39", "40-64", "65+"]
    assert [ckd_stage(v) for v in (95, 70, 50, 35, 20, 5)] == ["G1", "G2", "G3a", "G3b", "G4", "G5"]
    assert egfr_ckd_epi_2021(1.0, 50, "male") != egfr_ckd_epi_2021(1.0, 50, "female")
    assert lab_range("hemoglobin", "female") == (12.0, 15.5) and lab_range("hemoglobin", "male") == (13.0, 17.0)
    assert lab_flag("hemoglobin", 11.0, "female") == "low"
    assert lab_flag("potassium", 9.0) == "critical-high" and lab_flag("potassium", 4.0) == "normal"
    assert obs_value({"valueQuantity": {"value": 3}}) == 3.0 and obs_value({}) is None
    assert obs_code({"code": {"coding": [{"code": "x"}]}}) == "x" and obs_code({}) is None
