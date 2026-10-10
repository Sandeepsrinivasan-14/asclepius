"""Body map, discharge summary, terminology service, Synthea import and CLI."""

import json
import sys

import pytest

from asclepius import cli, synthea
from asclepius import termservice as TS


def _first_inpatient(client, h):
    rows = client.get("/api/patients?status=inpatient", headers=h).json()["patients"]
    assert rows
    return rows[0]["id"]


def test_bodymap_groups_chart_by_organ(client, rao):
    pid = _first_inpatient(client, rao)
    r = client.get(f"/api/patients/{pid}/bodymap", headers=rao)
    assert r.status_code == 200
    body = r.json()
    keys = {o["key"] for o in body["organs"]}
    assert {"heart", "lungs", "kidneys", "brain"} <= keys
    assert body["ranked"][0] in keys
    assert any(o["status"] != "clear" for o in body["organs"])
    assert {o["status"] for o in body["organs"]} <= {"clear", "watch", "abnormal", "critical"}


def test_bodymap_enforces_access(client, login):
    assert client.get("/api/patients/pat-001/bodymap", headers=login("auditor.menon")).status_code == 403


def test_discharge_summary_draft(client, rao):
    pid = _first_inpatient(client, rao)
    r = client.get(f"/api/patients/{pid}/discharge", headers=rao)
    assert r.status_code == 200
    d = r.json()
    assert d["status"].startswith("DRAFT")
    assert d["patient"]["id"] == pid and d["warning_signs"] and d["follow_up"] and d["allergies"]
    assert "Synthetic" in d["disclaimer"]


def test_discharge_requires_notes_permission(client, login):
    assert client.get("/api/patients/pat-001/discharge", headers=login("pharm.iyer")).status_code == 403


def test_terminology_service(client, rao):
    systems = client.get("/api/terminology/systems", headers=rao).json()["systems"]
    assert {s["system"] for s in systems} == {"icd10", "snomed", "loinc", "rxnorm"}
    assert all(s["concepts"] > 30 for s in systems)
    r = client.get("/api/terminology/lookup", params={"system": "icd10", "code": "E11.9"}, headers=rao).json()
    assert r["display"].startswith("Type 2 diabetes") and r["translations"][0]["code"] == "44054006"
    assert client.get("/api/terminology/lookup", params={"system": "loinc", "code": "0000-0"}, headers=rao).status_code == 404
    v = client.get("/api/terminology/validate", params={"system": "snomed", "code": "38341003", "display": "wrong"}, headers=rao).json()
    assert v["result"] is True and "differs" in v["message"]
    assert client.get("/api/terminology/validate", params={"system": "rxnorm", "code": "nope"}, headers=rao).json()["result"] is False
    ex = client.get("/api/terminology/expand", params={"system": "loinc", "q": "glucose"}, headers=rao).json()["concepts"]
    assert ex and all("glucose" in c["display"].lower() for c in ex)
    assert client.get("/api/terminology/expand", params={"system": "nope"}, headers=rao).status_code == 422


def test_fhir_terminology_operations(client, rao):
    r = client.get("/fhir/CodeSystem/$lookup", params={"system": "http://loinc.org", "code": "2160-0"}, headers=rao)
    assert r.status_code == 200 and r.json()["resourceType"] == "Parameters"
    assert client.get("/fhir/CodeSystem/$lookup", params={"system": "loinc", "code": "x"}, headers=rao).status_code == 404
    v = client.get("/fhir/ValueSet/$validate-code", params={"system": "icd10", "code": "I10"}, headers=rao).json()
    assert {"name": "result", "valueBoolean": True} in v["parameter"]
    t = client.get("/fhir/ConceptMap/$translate", params={"system": "snomed", "code": "38341003"}, headers=rao).json()
    assert any(x["name"] == "match" for x in t["parameter"])


def test_termservice_helpers():
    assert TS.system_key("http://snomed.info/sct") == "snomed" and TS.system_key("ICD-10") == "icd10" and TS.system_key("zzz") is None
    assert TS.lookup("zzz", "1") is None and TS.expand("zzz") == []
    assert TS.validate_code("icd10", "I10", "Essential hypertension")["message"] == "OK"


def test_synthea_import_end_to_end(client, rao, login):
    sample = client.get("/api/import/synthea/sample", headers=rao).json()
    before = len(client.get("/api/patients", headers=rao).json()["patients"])
    rep = client.post("/api/import/synthea", json=sample, headers=rao).json()
    assert rep["imported"]["Patient"] == 1 and rep["imported"]["Condition"] == 3 and rep["imported"]["MedicationRequest"] == 1
    assert rep["imported"]["Observation"] == 5  # BP panel flattened into systolic + diastolic
    assert rep["skipped"] == {"Claim": 1, "Organization": 1}
    assert rep["mapped"]["conditions"] == 2
    rows = client.get("/api/patients", headers=rao).json()["patients"]
    assert len(rows) == before + 1
    new = next(r for r in rows if r["name"] == "Elena Hartmann")
    full = client.get(f"/api/patients/{new['id']}", headers=rao).json()
    assert {c["key"] for c in full["conditions_detail"]} >= {"htn", "t2dm"}
    assert any(lab["key"] == "creatinine" and lab["flag"] == "high" for lab in full["labs"])
    assert new["abha"] and new["mrn"] == "SYN-MR-1042"
    assert client.get(f"/api/patients/{new['id']}/bodymap", headers=rao).status_code == 200
    assert client.get(f"/api/patients/{new['id']}", headers=login("nurse.devi")).status_code in (403, 404)


def test_synthea_import_rejects_bad_input(client, rao, login):
    assert client.post("/api/import/synthea", json={"resourceType": "Patient"}, headers=rao).status_code == 422
    assert client.post("/api/import/synthea", content="not json", headers=rao).status_code == 400
    assert client.post("/api/import/synthea", json=synthea.demo_bundle(), headers=login("pharm.iyer")).status_code == 403


def test_synthea_file_import_and_helpers(tmp_path):
    from asclepius.db import Store

    (tmp_path / "p1.json").write_text(json.dumps(synthea.demo_bundle(3)))
    (tmp_path / "hospitalInformation1.json").write_text("{}")
    st = Store(":memory:")
    rep = synthea.import_files(st, [str(tmp_path)])
    assert rep["files"] == 1 and rep["imported"]["Patient"] == 1
    assert synthea._norm_dt("2020-03-04T12:00:00-05:00") == "2020-03-04T17:00:00Z" and synthea._norm_dt("garbage-in") == "garbage-in"
    with pytest.raises(ValueError):
        synthea.import_bundle(st, {"resourceType": "Patient"})


def test_cli_doctor_and_import(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ASCLEPIUS_PATIENTS", "16")
    monkeypatch.setattr(sys, "argv", ["asclepius", "doctor"])
    cli.main()
    assert "patients=16" in capsys.readouterr().out
    f = tmp_path / "b.json"
    f.write_text(json.dumps(synthea.demo_bundle(5)))
    monkeypatch.setattr(sys, "argv", ["asclepius", "import-synthea", str(f)])
    cli.main()
    assert "'files': 1" in capsys.readouterr().out
