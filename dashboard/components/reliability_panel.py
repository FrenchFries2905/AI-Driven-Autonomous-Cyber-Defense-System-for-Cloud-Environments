"""
dashboard/components/reliability_panel.py

Panel showing reliability metrics against the Chapter 6 targets:
MTTD (Mean Time to Detect), MTTR (Mean Time to Respond), SLO compliance
(SLO: Service Level Objective, a measurable target), and uptime.
"""

import streamlit as st

MTTD_TARGET_MS = 5_000
MTTR_TARGET_MS = 30_000
UPTIME_TARGET_PCT = 99.5


def _fmt(value, unit: str = "") -> str:
    return "n/a" if value is None else f"{value:,}{unit}"


def render(metrics: dict) -> None:
    st.subheader("Reliability metrics")

    mttd, mttr = metrics.get("mttd_ms", {}), metrics.get("mttr_ms", {})
    slo = metrics.get("slo_compliance", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("MTTD (mean)", _fmt(mttd.get("mean"), " ms"),
              help=f"Target: under {MTTD_TARGET_MS:,} ms. 95th percentile: {_fmt(mttd.get('p95'), ' ms')}")
    c2.metric("MTTR (mean)", _fmt(mttr.get("mean"), " ms"),
              help=f"Target: under {MTTR_TARGET_MS:,} ms. 95th percentile: {_fmt(mttr.get('p95'), ' ms')}")
    c3.metric("SLO compliance", f"{_fmt(slo.get('mttr_within_target_pct'), '%')}",
              help="Share of responses finished within the MTTR target. "
                   f"Detections within MTTD target: {_fmt(slo.get('mttd_within_target_pct'), '%')}")
    c4.metric("Uptime", _fmt(metrics.get("uptime_pct"), "%"),
              help=f"Target: at least {UPTIME_TARGET_PCT}%. Based on {metrics.get('health_checks', 0)} health checks.")

    st.markdown("**Review notes**")
    for note in metrics.get("feedback", []):
        if note.startswith("No review flags"):
            st.success(note)
        else:
            st.warning(note)
