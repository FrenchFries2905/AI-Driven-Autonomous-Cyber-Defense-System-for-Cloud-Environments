"""
src/mitigation/trigger_alert.py

Simulated "Trigger Alert" mitigation action. In a real deployment this
would send a notification via email, Slack webhook, or a SIEM/alerting
system. Here it's simulated by logging the alert to console/return value.
"""

import time
import random
from datetime import datetime, timezone


def trigger_alert(threat_category: str, confidence: float, source_ip: str = "0.0.0.0") -> dict:
    """
    Simulates raising an alert for a detected threat.
    """
    start = time.perf_counter()

    time.sleep(random.uniform(0.02, 0.1))  # simulate notification dispatch latency

    message = (
        f"[ALERT] {threat_category} detected from {source_ip} "
        f"(confidence={confidence:.2f}) at {datetime.now(timezone.utc).isoformat()}"
    )
    print(message)  # stand-in for an actual notification channel

    duration_ms = (time.perf_counter() - start) * 1000

    return {
        "action": "trigger_alert",
        "target": source_ip,
        "success": True,
        "duration_ms": round(duration_ms, 2),
        "detail": message,
    }


if __name__ == "__main__":
    print(trigger_alert("Probe", 0.83, "10.0.0.15"))