"""Decision agent: every class / risk combination maps to the policy table."""

import pytest
from src.agent.policy_engine import PolicyEngine

engine = PolicyEngine()


@pytest.mark.parametrize("cls, conf, risk, action", [
    ("Normal", 0.99, "low", "none"),
    ("Probe", 0.72, "medium", "trigger_alert"),
    ("Probe", 0.95, "high", "block_ip"),
    ("DoS", 0.95, "high", "isolate_service"),
    ("DoS", 0.60, "low", "trigger_alert"),
    ("R2L", 0.88, "medium", "block_ip"),
    ("U2R", 0.93, "high", "restart_instance"),
])
def test_policy_table(cls, conf, risk, action):
    d = engine.decide(cls, conf)
    assert d["risk_level"] == risk
    assert d["action"] == action
    assert cls in d["reasoning"]


def test_threshold_boundaries():
    assert engine.decide("DoS", 0.90)["risk_level"] == "high"
    assert engine.decide("DoS", 0.899)["risk_level"] == "medium"
    assert engine.decide("DoS", 0.70)["risk_level"] == "medium"
    assert engine.decide("DoS", 0.699)["risk_level"] == "low"


def test_normal_is_always_low_risk():
    assert engine.decide("Normal", 1.0)["risk_level"] == "low"


def test_unknown_class_fails_safe_with_alert():
    assert engine.decide("Mystery", 0.99)["action"] == "trigger_alert"
