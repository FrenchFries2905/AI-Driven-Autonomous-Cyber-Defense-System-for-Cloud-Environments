"""
src/api/routes/predict.py
"""

from fastapi import APIRouter, Request
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
    result = pipeline.predict(sample.dict())
    return result