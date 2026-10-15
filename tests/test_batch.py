"""Batch prediction must agree with single-sample prediction."""

import pytest
from fastapi.testclient import TestClient

from src.reliability.evidence_log import EvidenceLog
from tests.conftest import NORMAL_SAMPLE, FLOOD_SAMPLE, VALID_CLASSES


@pytest.fixture()
def client(tmp_path, monkeypatch, require_model):
    db = str(tmp_path / "evidence.db")
    monkeypatch.setattr("src.api.main.EvidenceLog", lambda: EvidenceLog(db))
    from src.api.main import app
    with TestClient(app) as c:
        yield c


def test_batch_matches_single_predictions(client):
    samples = [NORMAL_SAMPLE, FLOOD_SAMPLE, NORMAL_SAMPLE]
    batch = client.post("/predict/batch", json=samples).json()
    assert len(batch) == 3
    for s, b in zip(samples, batch):
        single = client.post("/predict", json=s).json()
        assert b["predicted_class"] == single["predicted_class"] in VALID_CLASSES
        assert abs(b["confidence"] - single["confidence"]) < 0.001


def test_batch_rejects_oversized_request(client):
    r = client.post("/predict/batch", json=[NORMAL_SAMPLE] * 5001)
    assert r.status_code == 413


def test_batch_handles_unseen_category(client):
    odd = dict(NORMAL_SAMPLE, service="never_seen_before")
    assert client.post("/predict/batch", json=[odd]).status_code == 200
