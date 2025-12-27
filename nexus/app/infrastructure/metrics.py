from prometheus_client import Counter, Histogram, CONTENT_TYPE_LATEST, generate_latest
from fastapi import APIRouter, Response
import time
from functools import wraps

# Metrics definitions
JOB_SUBMITTED_TOTAL = Counter(
    "nexus_job_submitted_total", 
    "Total number of jobs submitted",
    ["task_type"]
)

JOB_COMPLETED_TOTAL = Counter(
    "nexus_job_completed_total",
    "Total number of jobs completed",
    ["task_type", "status"]
)

EVENT_PROCESSING_SECONDS = Histogram(
    "nexus_event_processing_seconds",
    "Time spent processing events",
    ["handler"]
)

COMMAND_PUBLISH_SECONDS = Histogram(
    "nexus_command_publish_seconds",
    "Time spent publishing commands",
    ["routing_key"]
)

metrics_router = APIRouter()

@metrics_router.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
