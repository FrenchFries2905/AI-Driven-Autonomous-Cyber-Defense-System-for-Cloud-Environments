"""
src/api/main.py

FastAPI entrypoint. Loads the pipeline, policy engine, evidence log and
orchestrator ONCE at startup and stores them on app.state.

Run with:
    uvicorn src.api.main:app --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.preprocessing.pipeline import ThreatDetectionPipeline
from src.reliability.evidence_log import EvidenceLog
from src.orchestrator import ThreatResponseOrchestrator
from src.api.routes import predict, health, respond, monitoring


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading threat detection pipeline...")
    app.state.pipeline = ThreatDetectionPipeline()
    app.state.evidence_log = EvidenceLog()
    app.state.orchestrator = ThreatResponseOrchestrator(
        pipeline=app.state.pipeline, log=app.state.evidence_log
    )
    app.state.evidence_log.record_health_check(True)  # service started
    print("Pipeline loaded. API ready.")
    yield
    app.state.evidence_log.close()
    app.state.pipeline = None


app = FastAPI(
    title="Autonomous Threat Detection API",
    description="Classifies network telemetry, decides a response, mitigates, and logs evidence",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(predict.router, tags=["Prediction"])
app.include_router(respond.router, tags=["Response"])
app.include_router(monitoring.router, tags=["Monitoring"])
app.include_router(health.router, tags=["Health"])


@app.get("/")
async def root():
    return {"message": "Threat Detection API is running. See /docs for usage."}
