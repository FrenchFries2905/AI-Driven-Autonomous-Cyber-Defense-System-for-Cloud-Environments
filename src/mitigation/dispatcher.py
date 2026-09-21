"""
src/mitigation/dispatcher.py

Central dispatcher for the Automated Mitigation Layer. Takes the decision
returned by the AI Decision Agent (Phase 5) and executes the corresponding
action, or does nothing for action == "none". Measures end-to-end
mitigation time to support the MTTR (Mean Time to Respond) target.
"""

import time

from src.mitigation.block_ip import block_ip
from src.mitigation.trigger_alert import trigger_alert
from src.mitigation.restart_instance import restart_instance
from src.mitigation.isolate_service import isolate_service


def dispatch(decision: dict, source_ip: str = "0.0.0.0", instance_id: str = "instance-default",
             service_id: str = "service-default") -> dict:
    """
    decision: the dict returned by PolicyEngine.decide(), e.g.
        {"predicted_class": "DoS", "confidence": 0.95, "risk_level": "high",
         "action": "isolate_service", "reasoning": "..."}

    Returns a combined record: the original decision + the mitigation outcome,
    ready to be handed to the evidence log (Phase 7).
    """
    start = time.perf_counter()
    action = decision.get("action", "trigger_alert")

    if action == "block_ip":
        outcome = block_ip(source_ip)
    elif action == "trigger_alert":
        outcome = trigger_alert(decision["predicted_class"], decision["confidence"], source_ip)
    elif action == "restart_instance":
        outcome = restart_instance(instance_id)
    elif action == "isolate_service":
        outcome = isolate_service(service_id)
    elif action == "none":
        outcome = {
            "action": "none",
            "target": None,
            "success": True,
            "duration_ms": 0.0,
            "detail": "No mitigation required (Normal traffic).",
        }
    else:
        # Unknown action name -- fail safe with an alert rather than doing nothing silently
        outcome = trigger_alert(decision["predicted_class"], decision["confidence"], source_ip)
        outcome["detail"] += f" (unrecognized action '{action}', defaulted to alert)"

    total_mttr_ms = (time.perf_counter() - start) * 1000

    return {
        **decision,
        "mitigation_outcome": outcome,
        "mttr_ms": round(total_mttr_ms, 2),
    }


if __name__ == "__main__":
    # Manual test using decisions from the policy engine
    from src.agent.policy_engine import PolicyEngine

    engine = PolicyEngine()

    test_cases = [
        ("Normal", 0.99),
        ("Probe", 0.72),
        ("DoS", 0.95),
        ("U2R", 0.93),
    ]

    for cls, conf in test_cases:
        decision = engine.decide(cls, conf)
        result = dispatch(decision, source_ip="192.168.1.77", instance_id="web-01", service_id="auth-svc")
        print(result)
        print(f"  -> MTTR: {result['mttr_ms']} ms\n")