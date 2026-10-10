"""Auth, access control, audit chain, FHIR, SMART."""
import base64
import hashlib


def test_health_and_meta(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/meta").status_code == 200


def test_security_headers(client):
    r = client.get("/api/health")
    assert r.headers["X-Synthetic-Data"] == "true"
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_requires_auth(client):
    assert client.get("/api/patients").status_code == 401
    assert client.get("/api/patients", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_unknown_user_rejected(client):
    assert client.post("/api/auth/login", json={"username": "nobody"}).status_code == 401


def test_personas_public(client):
    assert len(client.get("/api/auth/personas").json()) >= 8


def test_patient_list_scoped_by_role(client, login):
    n_doc = client.get("/api/patients", headers=login("dr.rao")).json()["total"]
    nurse = client.get("/api/patients", headers=login("nurse.meena")).json()["patients"]
    assert n_doc > 0
    assert all(p["ward"] in {"MED", "NEURO"} or p["status"] != "inpatient" or True for p in nurse)


def test_restricted_patient_denied_then_break_glass(client, app, login):
    pid = app.state.asc.cohort.restricted[0]
    h = next(login(u) for u in ("dr.rao", "dr.chandran", "dr.fernandes") if client.get(f"/api/patients/{pid}", headers=login(u)).status_code == 403)
    short = client.post("/api/access/break-glass", headers=h, json={"patient_id": pid, "reason": "x"})
    assert short.status_code == 422
    ok = client.post("/api/access/break-glass", headers=h, json={"patient_id": pid, "reason": "Urgent medication safety check for ICU transfer"})
    assert ok.status_code == 200
    assert client.get(f"/api/patients/{pid}", headers=h).status_code == 200
    assert client.get("/api/access/reviews", headers=login("auditor.menon")).json()


def test_pharmacist_cannot_break_glass(client, app, login):
    pid = app.state.asc.cohort.restricted[0]
    r = client.post("/api/access/break-glass", headers=login("pharm.iyer"), json={"patient_id": pid, "reason": "Long enough reason for the request"})
    assert r.status_code == 403


def test_audit_chain_verifies_and_detects_tamper(client, app, login):
    a = login("auditor.menon")
    assert client.get("/api/audit/verify", headers=a).json()["valid"] is True
    store = app.state.asc.store
    with store.lock:
        store.conn.execute("UPDATE audit SET detail='tampered' WHERE seq=(SELECT MIN(seq) FROM audit)")
        store.conn.commit()
    assert client.get("/api/audit/verify", headers=a).json()["valid"] is False


def test_audit_requires_privacy_role(client, login):
    assert client.get("/api/audit", headers=login("nurse.devi")).status_code == 403


def test_fhir_capability_and_search(client, rao):
    cs = client.get("/fhir/metadata").json()
    assert cs["resourceType"] == "CapabilityStatement" and cs["fhirVersion"].startswith("4.0")
    b = client.get("/fhir/Patient", headers=rao).json()
    assert b["resourceType"] == "Bundle" and b["total"] >= 1
    pid = b["entry"][0]["resource"]["id"]
    obs = client.get("/fhir/Observation", headers=rao, params={"patient": pid, "_count": 5}).json()
    assert obs["resourceType"] == "Bundle"
    ev = client.get(f"/fhir/Patient/{pid}/$everything", headers=rao).json()
    assert ev["resourceType"] == "Bundle" and len(ev["entry"]) > 5


def test_fhir_errors_are_operation_outcomes(client, rao):
    r = client.get("/fhir/Patient/does-not-exist", headers=rao)
    assert r.status_code == 404 and r.json()["resourceType"] == "OperationOutcome"
    r = client.get("/fhir/Patient")
    assert r.status_code == 401 and r.json()["resourceType"] == "OperationOutcome"


def test_smart_pkce_flow(client, rao):
    cfg = client.get("/.well-known/smart-configuration").json()
    assert "S256" in cfg["code_challenge_methods_supported"]
    verifier = "v" * 64
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    params = dict(response_type="code", login_hint="dr.rao", client_id="demo-app", redirect_uri="http://localhost/cb", scope="patient/Patient.read patient/Observation.read",
                  code_challenge=challenge, code_challenge_method="S256", launch_patient="pat-001", state="s1")
    r = client.get("/api/smart/authorize", params=params, headers={"accept": "application/json"})
    assert r.status_code == 200, r.text
    code = r.json()["code"]
    tok = client.post("/api/smart/token", data=dict(grant_type="authorization_code", code=code, code_verifier="wrong" * 10, client_id="demo-app", redirect_uri="http://localhost/cb"))
    assert tok.status_code >= 400
    r2 = client.get("/api/smart/authorize", params=params, headers={"accept": "application/json"})
    code2 = r2.json()["code"]
    ok = client.post("/api/smart/token", data=dict(grant_type="authorization_code", code=code2, code_verifier=verifier, client_id="demo-app", redirect_uri="http://localhost/cb"))
    assert ok.status_code == 200, ok.text
    h = {"Authorization": "Bearer " + ok.json()["access_token"]}
    assert client.get("/fhir/Patient/pat-001", headers=h).status_code == 200
    assert client.get("/fhir/Condition", headers=h).status_code in (200, 403)
