"""
src/api/routes/monitoring.py

GET /metrics: MTTD, MTTR, SLO compliance, uptime, counts, feedback notes
GET /events:  the most recent evidence-log entries
"""

from fastapi import APIRouter, Request

from src.reliability.metrics import compute_metrics, feedback_report

router = APIRouter()


@router.get("/metrics")
def metrics(request: Request):
    m = compute_metrics(request.app.state.evidence_log)
    m["feedback"] = feedback_report(m)
    return m


@router.get("/events")
def events(request: Request, limit: int = 20):
    return request.app.state.evidence_log.fetch_events(limit=limit)
