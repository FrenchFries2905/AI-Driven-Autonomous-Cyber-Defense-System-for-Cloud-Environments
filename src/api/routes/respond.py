"""
src/api/routes/respond.py

POST /respond: runs the full pipeline (classify -> decide -> mitigate -> log)
for one telemetry sample.
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.api.schemas import TelemetrySample

router = APIRouter()


class RespondRequest(BaseModel):
    sample: TelemetrySample
    source_ip: str = "0.0.0.0"
    instance_id: str = "instance-default"
    service_id: str = "service-default"


# Plain `def` (not async): mitigation actions sleep to simulate real API calls,
# and FastAPI runs plain functions in a worker thread so they don't block other requests.
@router.post("/respond")
def respond(body: RespondRequest, request: Request):
    orchestrator = request.app.state.orchestrator
    return orchestrator.handle(
        body.sample.model_dump(),
        source_ip=body.source_ip,
        instance_id=body.instance_id,
        service_id=body.service_id,
    )
