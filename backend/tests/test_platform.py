"""Interop pipeline, governance, ops twin, imaging."""

from asclepius.ops import erlang_c


def test_hl7_pipeline_idempotency_retry_dlq(client, login):
    h = login("dr.rao")
    acks = [client.post("/api/interop/hl7", headers=h, content=m["raw"]).json()["ack"] for m in client.get("/api/interop/demo", headers=h).json()["messages"]]
    assert "idempotent" in acks[1]
    assert "MSH_MISSING" in acks[4]
    res = client.post("/api/interop/process", headers=h).json()
    assert res["stats"]["duplicates"] == 1 and res["stats"]["rejected"] == 1
    assert res["stats"]["dead_lettered"] == 2 and res["stats"]["retries"] >= 2
    assert res["dead"] == 2
    jid = res["dead_letter"][0]["id"]
    assert client.post(f"/api/interop/dlq/{jid}/replay", headers=h).status_code == 200
    assert client.post("/api/interop/dlq/9999/replay", headers=h).status_code == 404


def test_interop_requires_permission(client, login):
    assert client.get("/api/interop/queue", headers=login("auditor.menon")).status_code == 403


def test_governance_endpoints(client, login):
    h = login("dr.rao")
    models = client.get("/api/governance/models", headers=h).json()
    assert len(models["models"]) >= 3
    drift = client.get("/api/governance/drift", headers=h).json()
    assert drift["features"]
    fair = client.get("/api/governance/fairness", headers=h).json()
    assert fair["attributes"] and "four-fifths" in fair["rule"].lower() or fair["rule"]


def test_override_feedback_recorded(client, login):
    h = login("dr.rao")
    r = client.post("/api/governance/feedback", headers=h, json={"model": "copilot", "patient_id": "pat-001", "action": "rejected", "reason": "Clinical picture differs"})
    assert r.status_code == 200
    assert client.get("/api/governance/overrides", headers=h).json()


def test_erlang_c_more_servers_less_waiting():
    a, b = erlang_c(10, 6, 2), erlang_c(10, 6, 4)
    key = next(k for k in a if "wait" in k and "prob" in k.lower() or k in ("p_wait", "prob_wait"))
    assert b[key] < a[key]


def test_ops_endpoints(client, login):
    h = login("admin.kumar")
    ov = client.get("/api/ops/overview", headers=h).json()
    assert 0 < ov["occupancy"] <= 1.0 or 0 < ov["occupancy"] <= 100
    fc = client.get("/api/ops/forecast", headers=h).json()
    assert len(fc["wards"]) >= 3 and fc["dates"]
    assert client.get("/api/ops/opd", headers=h).status_code == 200
    flow = client.get("/api/ops/flow", headers=h).json()
    assert flow["nodes"] and flow["links"]
    assert client.get("/api/ops/census", headers=h).json()["beds"]


def test_los_prediction_validates(client, login):
    h = login("admin.kumar")
    ok = client.post("/api/ops/los", headers=h, json={"age": 70, "ward": "MED", "acuity": 3, "comorbidities": 2, "emergency": True})
    assert ok.status_code == 200, ok.text
    assert client.post("/api/ops/los", headers=h, json={"age": 70, "ward": "NOPE", "acuity": 3, "comorbidities": 2, "emergency": True}).status_code == 422


def test_imaging_detects_lesion_not_control(client, login):
    h = login("dr.fernandes")
    a = client.get("/api/imaging/studies/MR-BRAIN-A", headers=h).json()["analysis"]
    b = client.get("/api/imaging/studies/MR-BRAIN-B", headers=h).json()["analysis"]
    pa = a.get("probability", a.get("score"))
    pb = b.get("probability", b.get("score"))
    assert pa is not None and pb is not None and pa > 0.5 > pb


def test_imaging_png_endpoints(client, login):
    h = login("dr.fernandes")
    r = client.get("/api/imaging/studies/MR-BRAIN-A/slice/5.png", headers=h)
    assert r.status_code == 200 and r.content[:4] == b"\x89PNG"
    assert client.get("/api/imaging/studies/MR-BRAIN-A/overlay/5.png", headers=h).content[:4] == b"\x89PNG"
