"""
src/api/routes/health.py

GET /health. Each call is also stored as a health check, which is what
the uptime figure in /metrics is computed from.
"""

from fastapi import APIRouter, Request
from src.api.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(request: Request):
    pipeline_loaded = getattr(request.app.state, "pipeline", None) is not None

    log = getattr(request.app.state, "evidence_log", None)
    if log is not None:
        log.record_health_check(pipeline_loaded)

    return {
        "status": "ok" if pipeline_loaded else "degraded",
        "model_loaded": pipeline_loaded,
    }
