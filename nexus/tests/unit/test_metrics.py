import pytest
from app.infrastructure.metrics import JOB_SUBMITTED_TOTAL, metrics_router
from fastapi.testclient import TestClient
from fastapi import FastAPI

app = FastAPI()
app.include_router(metrics_router)
client = TestClient(app)

def test_metrics_endpoint():
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "nexus_job_submitted_total" in resp.text

def test_metric_increment():
    # Note: prometheus_client metrics are global, so this might be affected by other tests
    # But usually tests run in isolation or we check delta
    before = JOB_SUBMITTED_TOTAL.labels(task_type="test")._value.get()
    JOB_SUBMITTED_TOTAL.labels(task_type="test").inc()
    after = JOB_SUBMITTED_TOTAL.labels(task_type="test")._value.get()
    assert after == before + 1
