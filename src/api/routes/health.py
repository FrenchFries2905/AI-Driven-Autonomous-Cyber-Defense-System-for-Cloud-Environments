"""
src/api/routes/health.py
"""

from fastapi import APIRouter, Request
from src.api.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(request: Request):
    pipeline_loaded = getattr(request.app.state, "pipeline", None) is not None
    return {
        "status": "ok" if pipeline_loaded else "degraded",
        "model_loaded": pipeline_loaded,
    }