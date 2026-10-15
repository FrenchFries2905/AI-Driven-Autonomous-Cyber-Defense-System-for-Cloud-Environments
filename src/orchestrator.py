"""
src/orchestrator.py

Chains the whole pipeline for one telemetry sample:
    classify (Phase 3) -> decide (Phase 5) -> mitigate (Phase 6) -> log (Phase 7)

Run a quick demo on 30 random test records with:
    python -m src.orchestrator
"""

import json
import random

from src.preprocessing.pipeline import ThreatDetectionPipeline
from src.agent.policy_engine import PolicyEngine
from src.mitigation.dispatcher import dispatch
from src.reliability.evidence_log import EvidenceLog
from src.reliability.metrics import compute_metrics, feedback_report


class ThreatResponseOrchestrator:
    def __init__(self, pipeline=None, engine=None, log=None):
        # Reuse objects if given (the API passes in its already-loaded pipeline)
        self.pipeline = pipeline or ThreatDetectionPipeline()
        self.engine = engine or PolicyEngine()
        self.log = log or EvidenceLog()

    def handle(self, sample: dict, source_ip: str = "0.0.0.0",
               instance_id: str = "instance-default", service_id: str = "service-default") -> dict:
        prediction = self.pipeline.predict(sample)
        decision = self.engine.decide(prediction["predicted_class"], prediction["confidence"])
        result = dispatch(decision, source_ip=source_ip, instance_id=instance_id, service_id=service_id)

        result["source_ip"] = source_ip
        result["mttd_ms"] = prediction["latency_ms"]  # detection time = inference latency
        result["class_probabilities"] = prediction["class_probabilities"]
        result["event_id"] = self.log.record_event(result)
        return result


if __name__ == "__main__":
    from src.preprocessing.loader import load_nsl_kdd

    df = load_nsl_kdd("data/raw/KDDTest+.txt").sample(30, random_state=7)
    truth = df["label"].tolist()  # shown only for comparison; never given to the system
    features = df.drop(columns=["label", "difficulty_level"])

    orch = ThreatResponseOrchestrator()
    orch.log.record_health_check(True)

    for (_, row), actual in zip(features.iterrows(), truth):
        ip = f"10.0.{random.randint(0, 9)}.{random.randint(1, 254)}"  # simulated source address
        r = orch.handle(row.to_dict(), source_ip=ip, instance_id="web-01", service_id="auth-svc")
        print(f"#{r['event_id']:>3} actual={actual:<12} predicted={r['predicted_class']:<7} "
              f"conf={r['confidence']:.2f} risk={r['risk_level']:<6} action={r['action']:<16} "
              f"MTTD={r['mttd_ms']:.1f}ms MTTR={r['mttr_ms']:.1f}ms")

    orch.log.record_health_check(True)
    metrics = compute_metrics(orch.log)
    print("\n=== Metrics ===")
    print(json.dumps(metrics, indent=2))
    print("\n=== Feedback ===")
    for note in feedback_report(metrics):
        print("-", note)
