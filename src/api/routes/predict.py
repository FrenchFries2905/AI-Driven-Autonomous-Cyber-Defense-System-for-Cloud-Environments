"""
src/api/routes/predict.py
"""

from typing import List

from fastapi import APIRouter, HTTPException, Request
from src.api.schemas import TelemetrySample, PredictionResponse

router = APIRouter()


@router.post("/predict", response_model=PredictionResponse)
async def predict(sample: TelemetrySample, request: Request):
    """
    Classify a single network telemetry sample.
    The loaded ThreatDetectionPipeline lives on app.state.pipeline
    (set once at startup — see main.py) so it isn't reloaded per request.
    """
    pipeline = request.app.state.pipeline
    result = pipeline.predict(sample.model_dump())
    return result


MAX_BATCH = 5000


@router.post("/predict/batch", response_model=List[PredictionResponse])
def predict_batch(samples: List[TelemetrySample], request: Request):
    """Classify many samples in one call (much higher throughput than one call per sample)."""
    if len(samples) > MAX_BATCH:
        raise HTTPException(status_code=413, detail=f"Batch too large (max {MAX_BATCH} samples).")
    pipeline = request.app.state.pipeline
    return pipeline.predict_batch([s.model_dump() for s in samples])
