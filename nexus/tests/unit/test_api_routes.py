import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from app.api.routes import router
from app.api.dependencies import get_job_service, get_status_service, get_mq_manager, get_storage
from unittest.mock import AsyncMock, MagicMock
from app.models.api_models import JobSubmitResponse, JobStatusResponse

app = FastAPI()
app.include_router(router, prefix="/api/v1")

@pytest.fixture
def mock_job_service():
    return AsyncMock()

@pytest.fixture
def mock_status_service():
    return AsyncMock()

@pytest.fixture
def mock_mq():
    mq = AsyncMock()
    mq.is_healthy.return_value = True
    return mq

@pytest.fixture
def mock_storage():
    storage = AsyncMock()
    storage.is_healthy.return_value = True
    return storage

@pytest.fixture
def client(mock_job_service, mock_status_service, mock_mq, mock_storage):
    app.dependency_overrides[get_job_service] = lambda: mock_job_service
    app.dependency_overrides[get_status_service] = lambda: mock_status_service
    app.dependency_overrides[get_mq_manager] = lambda: mock_mq
    app.dependency_overrides[get_storage] = lambda: mock_storage
    return TestClient(app)

def test_submit_job(client, mock_job_service):
    mock_job_service.submit_job.return_value = JobSubmitResponse(trace_id="t1")
    
    resp = client.post("/api/v1/jobs", json={"task_type": "test", "parameters": {}})
    
    assert resp.status_code == 202
    assert resp.json()["trace_id"] == "t1"

def test_get_status(client, mock_status_service):
    mock_status_service.get_job_status.return_value = JobStatusResponse(
        trace_id="t1", task_type="test", status="running", 
        total_work_items=10, completed_count=1, failed_count=0, pending_count=9
    )
    
    resp = client.get("/api/v1/jobs/t1")
    
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"

def test_get_artifact(client, mock_status_service):
    async def mock_stream_gen():
        yield b'{"test": "data"}'
        
    mock_status_service.get_artifact_stream.return_value = (mock_stream_gen(), "application/json")
    
    resp = client.get("/api/v1/jobs/t1/artifacts/search_res")
    
    assert resp.status_code == 200
    assert resp.content == b'{"test": "data"}'
    assert resp.headers["content-type"] == "application/json"

def test_get_artifact_404_job(client, mock_status_service):
    mock_status_service.get_artifact_stream.side_effect = ValueError("Job t1 not found")
    
    resp = client.get("/api/v1/jobs/t1/artifacts/search_res")
    
    assert resp.status_code == 404

def test_get_status_404(client, mock_status_service):
    mock_status_service.get_job_status.return_value = None
    
    resp = client.get("/api/v1/jobs/t1")
    
    assert resp.status_code == 404

def test_health(client):
    # Depending on how we mount, it might be /api/v1/health or /health
    # In this test setup, we mounted router at /api/v1
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"

def test_ready(client):
    resp = client.get("/api/v1/ready")
    assert resp.status_code == 200
