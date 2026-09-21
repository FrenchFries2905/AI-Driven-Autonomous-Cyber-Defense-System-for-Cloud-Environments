"""
src/agent/policy_engine.py

The AI Decision Agent's core logic: given a classification result,
computes a risk level and looks up the corresponding mitigation action
from policies.yaml.
"""

import os
import yaml

from src.agent.risk_scoring import compute_risk_level

POLICY_PATH = os.path.join(os.path.dirname(__file__), "policies.yaml")


class PolicyEngine:
    def __init__(self, policy_path: str = POLICY_PATH):
        with open(policy_path, "r") as f:
            config = yaml.safe_load(f)

        self.policies = config["policies"]
        self.thresholds = config["risk_thresholds"]

    def decide(self, predicted_class: str, confidence: float) -> dict:
        """
        Given a classification result, returns the decision:
        risk level, chosen action, and the reasoning (for the evidence log).
        """
        risk_level = compute_risk_level(predicted_class, confidence, self.thresholds)

        class_policy = self.policies.get(predicted_class)
        if class_policy is None:
            # Unknown class -- fail safe by alerting rather than staying silent
            action = "trigger_alert"
            reasoning = f"Unrecognized class '{predicted_class}' -- defaulting to alert."
        else:
            action = class_policy.get(risk_level, "trigger_alert")
            reasoning = (
                f"Class={predicted_class}, confidence={confidence:.4f}, "
                f"risk_level={risk_level} -> action={action}"
            )

        return {
            "predicted_class": predicted_class,
            "confidence": confidence,
            "risk_level": risk_level,
            "action": action,
            "reasoning": reasoning,
        }


if __name__ == "__main__":
    engine = PolicyEngine()

    test_cases = [
        ("Normal", 0.99),
        ("Probe", 0.72),
        ("DoS", 0.95),
        ("DoS", 0.60),
        ("R2L", 0.88),
        ("U2R", 0.93),
    ]

    for cls, conf in test_cases:
        decision = engine.decide(cls, conf)
        print(decision)