"""
src/reliability/metrics.py

Computes reliability metrics from the evidence log:
  - MTTD: Mean Time to Detect (sample arrival -> classification done)
  - MTTR: Mean Time to Respond (decision -> mitigation finished)
  - SLO compliance: share of events that met the target times
    (SLO: Service Level Objective, a measurable target the service promises to meet)
  - Uptime: share of health checks that passed
"""

import math

# Targets from the project report (Chapter 6)
TARGETS = {
    "mttd_ms": 5_000,     # MTTD < 5 s
    "mttr_ms": 30_000,    # MTTR < 30 s
    "uptime_pct": 99.5,   # uptime >= 99.5 %
}


def _stats(values: list) -> dict:
    if not values:
        return {"mean": None, "p95": None, "max": None}
    s = sorted(values)
    k = max(0, math.ceil(0.95 * len(s)) - 1)  # p95: 95% of events were faster than this
    return {
        "mean": round(sum(s) / len(s), 2),
        "p95": round(s[k], 2),
        "max": round(s[-1], 2),
    }


def _pct(part: int, whole: int):
    return round(100.0 * part / whole, 2) if whole else None


def compute_metrics(log) -> dict:
    events = log.fetch_events(newest_first=False)
    checks = log.fetch_health_checks()
    n = len(events)

    mttd = [e["mttd_ms"] for e in events]
    mttr = [e["mttr_ms"] for e in events]

    by_class, by_action = {}, {}
    for e in events:
        by_class[e["predicted_class"]] = by_class.get(e["predicted_class"], 0) + 1
        a = by_action.setdefault(e["action"], {"count": 0, "successes": 0, "total_ms": 0.0})
        a["count"] += 1
        a["successes"] += e["success"]
        a["total_ms"] += e["mttr_ms"]
    action_summary = {
        name: {
            "count": a["count"],
            "success_rate_pct": _pct(a["successes"], a["count"]),
            "mean_ms": round(a["total_ms"] / a["count"], 2),
        }
        for name, a in by_action.items()
    }

    threats = [e for e in events if e["predicted_class"] != "Normal"]
    mitigated = [e for e in events if e["action"] != "none" and e["success"]]

    uptime = _pct(sum(c["ok"] for c in checks), len(checks))

    return {
        "total_events": n,
        "detected_threats": len(threats),
        "mitigated_incidents": len(mitigated),
        "events_by_class": by_class,
        "actions": action_summary,
        "mttd_ms": _stats(mttd),
        "mttr_ms": _stats(mttr),
        "slo_compliance": {
            "mttd_within_target_pct": _pct(sum(v <= TARGETS["mttd_ms"] for v in mttd), n),
            "mttr_within_target_pct": _pct(sum(v <= TARGETS["mttr_ms"] for v in mttr), n),
        },
        "uptime_pct": uptime,
        "uptime_meets_target": (uptime >= TARGETS["uptime_pct"]) if uptime is not None else None,
        "health_checks": len(checks),
    }


def feedback_report(metrics: dict, min_events: int = 5) -> list:
    """
    Simple, explainable feedback loop: flags things a human should review.
    It does NOT change policies by itself, so every policy change stays auditable.
    """
    notes = []
    for name, a in metrics["actions"].items():
        if name != "none" and a["count"] >= min_events and a["success_rate_pct"] < 95:
            notes.append(f"Action '{name}' succeeded only {a['success_rate_pct']}% of the time "
                         f"({a['count']} runs): review how it is executed.")
    slo = metrics["slo_compliance"]
    if slo["mttr_within_target_pct"] is not None and slo["mttr_within_target_pct"] < 100:
        notes.append("Some responses exceeded the MTTR target: review slow actions.")
    if slo["mttd_within_target_pct"] is not None and slo["mttd_within_target_pct"] < 100:
        notes.append("Some detections exceeded the MTTD target: review inference latency.")
    if metrics["uptime_meets_target"] is False:
        notes.append("Uptime is below the 99.5% target.")
    if not notes:
        notes.append("No review flags: all measured objectives were met.")
    return notes
