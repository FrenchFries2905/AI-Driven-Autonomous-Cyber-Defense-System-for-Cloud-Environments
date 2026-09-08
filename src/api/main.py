"""
src/api/main.py

FastAPI app entrypoint. Loads the ThreatDetectionPipeline ONCE at startup
and stores it on app.state so every request reuses it (no reloading the
model per request — this matters for your MTTD latency target).

Run with:
    uvicorn src.api.main:app --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.preprocessing.pipeline import ThreatDetectionPipeline
from src.api.routes import predict, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load model + preprocessing artifacts once
    print("Loading threat detection pipeline...")
    app.state.pipeline = ThreatDetectionPipeline()
    print("Pipeline loaded. API ready.")
    yield
    # Shutdown: nothing to clean up currently
    app.state.pipeline = None


app = FastAPI(
    title="Autonomous Threat Detection API",
    description="Classifies network telemetry into Normal / Probe / DoS / U2R / R2L",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(predict.router, tags=["Prediction"])
app.include_router(health.router, tags=["Health"])


@app.get("/")
async def root():
    return {"message": "Threat Detection API is running. See /docs for usage."}