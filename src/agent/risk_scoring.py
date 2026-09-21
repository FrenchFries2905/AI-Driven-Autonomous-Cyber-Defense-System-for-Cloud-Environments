"""
src/agent/risk_scoring.py

Computes a risk level (low / medium / high) from a classification result.
Risk is currently driven by model confidence, bucketed against thresholds
defined in policies.yaml -- deliberately simple and explainable, rather
than a learned/black-box risk score, so every decision can be traced
back to a rule a human can read.
"""

import os
import yaml

POLICY_PATH = os.path.join(os.path.dirname(__file__), "policies.yaml")


def load_thresholds(policy_path: str = POLICY_PATH) -> dict:
    with open(policy_path, "r") as f:
        config = yaml.safe_load(f)
    return config["risk_thresholds"]


def compute_risk_level(predicted_class: str, confidence: float, thresholds: dict = None) -> str:
    """
    Bucket a prediction into 'low', 'medium', or 'high' risk.

    Normal traffic is always low risk regardless of confidence --
    a highly confident "Normal" prediction should not be escalated.
    For attack classes, higher confidence means the model is more
    certain it's a real attack, so it maps to higher risk.
    """
    if thresholds is None:
        thresholds = load_thresholds()

    if predicted_class == "Normal":
        return "low"

    if confidence >= thresholds["high"]:
        return "high"
    elif confidence >= thresholds["medium"]:
        return "medium"
    else:
        return "low"


if __name__ == "__main__":
    thresholds = load_thresholds()
    print("Loaded thresholds:", thresholds)

    test_cases = [
        ("Normal", 0.99),
        ("DoS", 0.95),
        ("DoS", 0.75),
        ("DoS", 0.50),
        ("U2R", 0.92),
    ]
    for cls, conf in test_cases:
        risk = compute_risk_level(cls, conf, thresholds)
        print(f"{cls} @ {conf} -> risk = {risk}")