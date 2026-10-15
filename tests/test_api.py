"""Integration tests: the real API with the real trained model (skipped if models are missing)."""

import pytest
from fastapi.testclient import TestClient

from src.reliability.evidence_log import EvidenceLog
from tests.conftest import NORMAL_SAMPLE, FLOOD_SAMPLE, VALID_CLASSES


@pytest.fixture()
def client(tmp_path, monkeypatch, require_model):
    db = str(tmp_path / "evidence.db")  # keep test events out of the real evidence log
    monkeypatch.setattr("src.api.main.EvidenceLog", lambda: EvidenceLog(db))
    from src.api.main import app
    with TestClient(app) as c:
        yield c


def test_health_reports_model_loaded(client):
    body = client.get("/health").json()
    assert body == {"status": "ok", "model_loaded": True}


def test_predict_returns_valid_class(client):
    r = client.post("/predict", json=NORMAL_SAMPLE)
    assert r.status_code == 200
    body = r.json()
    assert body["predicted_class"] in VALID_CLASSES
    assert 0.0 <= body["confidence"] <= 1.0
    assert abs(sum(body["class_probabilities"].values()) - 1.0) < 0.01
    assert body["latency_ms"] < 5000  # MTTD target


def test_predict_rejects_incomplete_sample(client):
    bad = dict(NORMAL_SAMPLE)
    bad.pop("src_bytes")
    assert client.post("/predict", json=bad).status_code == 422


def test_respond_runs_full_pipeline_and_logs_evidence(client):
    before = client.get("/metrics").json()["total_events"]
    r = client.post("/respond", json={"sample": FLOOD_SAMPLE, "source_ip": "10.1.2.3",
                                      "instance_id": "web-01", "service_id": "auth-svc"})
    assert r.status_code == 200
    body = r.json()
    assert body["predicted_class"] in VALID_CLASSES
    assert body["mitigation_outcome"]["success"] is True
    assert body["mttr_ms"] < 30_000 and body["mttd_ms"] < 5_000
    assert "event_id" in body

    events = client.get("/events", params={"limit": 5}).json()
    assert events[0]["id"] == body["event_id"]
    assert events[0]["source_ip"] == "10.1.2.3"
    assert client.get("/metrics").json()["total_events"] == before + 1


def test_normal_traffic_triggers_no_mitigation_when_classified_normal(client):
    body = client.post("/respond", json={"sample": NORMAL_SAMPLE}).json()
    if body["predicted_class"] == "Normal":
        assert body["action"] == "none"
    else:  # model disagrees; the policy must still map the class to an action
        assert body["action"] != "none"


def test_metrics_include_uptime_after_health_checks(client):
    client.get("/health")
    client.get("/health")
    m = client.get("/metrics").json()
    assert m["uptime_pct"] == 100.0
    assert m["health_checks"] >= 3  # startup check + two calls
