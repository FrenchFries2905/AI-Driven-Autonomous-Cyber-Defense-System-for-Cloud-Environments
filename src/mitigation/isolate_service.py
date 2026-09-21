"""
src/mitigation/isolate_service.py

Simulated "Isolate Service" mitigation action. In a real deployment this
would apply network segmentation -- e.g. moving a resource into a
quarantine VPC/subnet or stripping its security group access. Here it's
simulated with an in-memory isolation registry.
"""

import time
import random
from datetime import datetime, timezone

# Simulated isolation registry (would be real network segmentation state in production)
_isolated_services = {}


def isolate_service(service_id: str = "service-default") -> dict:
    """
    Simulates isolating a service/resource from the rest of the network --
    used for higher-severity threats (e.g. high-confidence DoS or R2L)
    where blocking a single IP isn't enough.
    """
    start = time.perf_counter()

    time.sleep(random.uniform(0.15, 0.4))  # simulate network policy propagation delay

    _isolated_services[service_id] = {
        "status": "isolated",
        "isolated_at": datetime.now(timezone.utc).isoformat(),
    }
    success = _isolated_services[service_id]["status"] == "isolated"

    duration_ms = (time.perf_counter() - start) * 1000

    return {
        "action": "isolate_service",
        "target": service_id,
        "success": success,
        "duration_ms": round(duration_ms, 2),
        "detail": f"Service {service_id} isolated from network." if success else "Isolation failed.",
    }


if __name__ == "__main__":
    print(isolate_service("auth-service"))
    print("Current simulated isolation state:", _isolated_services)