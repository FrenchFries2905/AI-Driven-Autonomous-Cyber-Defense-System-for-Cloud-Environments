"""Evidence log and metrics."""

import sqlite3
import pytest

from src.reliability.evidence_log import EvidenceLog
from src.reliability.metrics import compute_metrics, feedback_report


def record(cls="DoS", action="isolate_service", success=True, mttd=4.0, mttr=200.0):
    return {"predicted_class": cls, "confidence": 0.95, "risk_level": "high", "action": action,
            "reasoning": "test", "source_ip": "10.0.0.1", "mttd_ms": mttd, "mttr_ms": mttr,
            "mitigation_outcome": {"target": "svc", "success": success, "detail": "x"}}


@pytest.fixture()
def log(tmp_path):
    return EvidenceLog(str(tmp_path / "e.db"))


def test_record_and_fetch_newest_first(log):
    a = log.record_event(record("DoS"))
    b = log.record_event(record("Probe", "trigger_alert"))
    ids = [e["id"] for e in log.fetch_events()]
    assert ids == [b, a]


def test_log_is_append_only(log):
    eid = log.record_event(record())
    with pytest.raises(sqlite3.DatabaseError):
        log._conn.execute("UPDATE events SET action='none' WHERE id=?", (eid,))
    with pytest.raises(sqlite3.DatabaseError):
        log._conn.execute("DELETE FROM events WHERE id=?", (eid,))


def test_metrics_counts_and_slo(log):
    log.record_event(record("Normal", "none", mttr=0.0))
    log.record_event(record("DoS"))
    log.record_event(record("U2R", "restart_instance", mttr=800.0))
    log.record_health_check(True)
    log.record_health_check(True)
    m = compute_metrics(log)
    assert m["total_events"] == 3
    assert m["detected_threats"] == 2
    assert m["mitigated_incidents"] == 2
    assert m["slo_compliance"]["mttr_within_target_pct"] == 100.0
    assert m["uptime_pct"] == 100.0


def test_feedback_flags_failing_action(log):
    for _ in range(5):
        log.record_event(record(success=False))
    notes = feedback_report(compute_metrics(log))
    assert any("isolate_service" in n for n in notes)


def test_empty_log_metrics_do_not_crash(log):
    m = compute_metrics(log)
    assert m["total_events"] == 0 and m["uptime_pct"] is None
