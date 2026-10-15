"""Mitigation layer: dispatcher routes each action and returns a uniform outcome."""

import pytest
from src.mitigation.dispatcher import dispatch

OUTCOME_KEYS = {"action", "target", "success", "duration_ms", "detail"}


def decision(action, cls="DoS", conf=0.95):
    return {"predicted_class": cls, "confidence": conf, "risk_level": "high",
            "action": action, "reasoning": "test"}


@pytest.mark.parametrize("action", ["block_ip", "trigger_alert", "restart_instance", "isolate_service"])
def test_each_action_runs_and_succeeds(action):
    r = dispatch(decision(action), source_ip="10.0.0.9", instance_id="i-1", service_id="svc-1")
    assert set(r["mitigation_outcome"]) >= OUTCOME_KEYS
    assert r["mitigation_outcome"]["action"] == action
    assert r["mitigation_outcome"]["success"] is True
    assert r["mttr_ms"] >= r["mitigation_outcome"]["duration_ms"] - 1


def test_none_action_is_a_noop():
    r = dispatch(decision("none", cls="Normal", conf=0.99))
    assert r["mitigation_outcome"]["action"] == "none"
    assert r["mttr_ms"] < 5


def test_unknown_action_falls_back_to_alert():
    r = dispatch(decision("self_destruct"))
    assert r["mitigation_outcome"]["action"] == "trigger_alert"
    assert "unrecognized" in r["mitigation_outcome"]["detail"]


def test_mttr_is_far_below_30_seconds():
    assert dispatch(decision("restart_instance"))["mttr_ms"] < 30_000
