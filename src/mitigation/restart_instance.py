"""
src/mitigation/restart_instance.py

Simulated "Restart Instance" mitigation action. In a real deployment this
would call a cloud provider's compute API (e.g. AWS EC2 RebootInstances,
GCP Compute instances.reset). Here it's simulated with an in-memory
instance registry, since this is a proof-of-concept rather than a live
cloud integration.
"""

import time
import random
from datetime import datetime, timezone

# Simulated instance state registry (would be real cloud API state in production)
_instance_states = {}


def restart_instance(instance_id: str = "instance-default") -> dict:
    """
    Simulates restarting a compute instance suspected of compromise
    (e.g. after a U2R attack gains root access).
    """
    start = time.perf_counter()

    # Simulate restart latency -- this is the slowest of the four actions,
    # which is realistic (cycling a VM takes longer than a firewall rule)
    time.sleep(random.uniform(0.3, 0.8))

    _instance_states[instance_id] = {
        "status": "restarted",
        "restarted_at": datetime.now(timezone.utc).isoformat(),
    }
    success = _instance_states[instance_id]["status"] == "restarted"

    duration_ms = (time.perf_counter() - start) * 1000

    return {
        "action": "restart_instance",
        "target": instance_id,
        "success": success,
        "duration_ms": round(duration_ms, 2),
        "detail": f"Instance {instance_id} restarted." if success else "Restart failed.",
    }


if __name__ == "__main__":
    print(restart_instance("web-server-03"))
    print("Current simulated instance states:", _instance_states)