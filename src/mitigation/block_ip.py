"""
src/mitigation/block_ip.py

Simulated "Block IP" mitigation action. In a real deployment this would
call a cloud firewall/security-group API (e.g. AWS Security Group rule,
GCP firewall rule, or an iptables/WAF call). Here it's simulated with an
in-memory blocklist, since this is a proof-of-concept rather than a live
cloud integration.
"""

import time
import random

# In-memory simulated blocklist (would be a real firewall rule set in production)
_blocklist = set()


def block_ip(source_ip: str = "0.0.0.0") -> dict:
    """
    Simulates blocking a source IP. Returns an outcome dict matching the
    schema used by all mitigation actions, for consistent evidence logging.
    """
    start = time.perf_counter()

    # Simulate a small amount of "work" (API call latency in a real system)
    time.sleep(random.uniform(0.05, 0.2))

    _blocklist.add(source_ip)
    success = source_ip in _blocklist

    duration_ms = (time.perf_counter() - start) * 1000

    return {
        "action": "block_ip",
        "target": source_ip,
        "success": success,
        "duration_ms": round(duration_ms, 2),
        "detail": f"IP {source_ip} added to blocklist." if success else "Failed to add IP to blocklist.",
    }


if __name__ == "__main__":
    print(block_ip("192.168.1.50"))
    print("Current simulated blocklist:", _blocklist)