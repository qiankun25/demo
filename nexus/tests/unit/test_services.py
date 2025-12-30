import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.job_service import JobService
from app.services.status_service import StatusService
from app.engine.orchestrator import WorkflowOrchestrator
from app.models.api_models import JobSubmitRequest
from app.models.state_models import JobContext

@pytest.fixture
def mock_orchestrator():
    return AsyncMock(spec=WorkflowOrchestrator)

@pytest.mark.asyncio
async def test_job_service_submit(mock_orchestrator):
    service = JobService(mock_orchestrator)
    mock_orchestrator.submit_job.return_value = "trace1"
    
    req = JobSubmitRequest(task_type="test", parameters={"k": "v"})
    resp = await service.submit_job(req)
    
    assert resp.trace_id == "trace1"
    assert resp.status == "submitted"
    mock_orchestrator.submit_job.assert_called_once()

@pytest.mark.asyncio
async def test_status_service_get(mock_orchestrator):
    service = StatusService(mock_orchestrator)
    context = JobContext(
        trace_id="trace1",
        task_type="test",
        init_key="init",
        work_keys=["w1", "w2"],
        completed_work_keys=["w1"],
        failures=[]
    )
    mock_orchestrator.get_job_status.return_value = context
    
    resp = await service.get_job_status("trace1")
    
    assert resp.trace_id == "trace1"
    assert resp.total_work_items == 2
    assert resp.completed_count == 1
    assert resp.pending_count == 1
    assert resp.failed_count == 0

@pytest.mark.asyncio
async def test_status_service_not_found(mock_orchestrator):
    service = StatusService(mock_orchestrator)
    mock_orchestrator.get_job_status.return_value = None
    
    resp = await service.get_job_status("trace1")
    assert resp is None

@pytest.mark.asyncio
async def test_status_service_fallback_manifest(mock_orchestrator):
    service = StatusService(mock_orchestrator)
    mock_orchestrator.storage = AsyncMock()
    mock_orchestrator.storage.exists.return_value = True
    context = JobContext(
        trace_id="t1",
        task_type="MORNING_REPORT",
        init_key="init",
        work_keys=["w1"],
        completed_work_keys=["w1"],
        failures=[],
        current_stage="completed",
        artifacts={}
    )
    mock_orchestrator.get_job_status.return_value = context

    resp = await service.get_job_status("t1")

    assert resp.artifacts["detailed_manifest"] == "/api/v1/jobs/t1/artifacts/detailed_manifest"

@pytest.mark.asyncio
async def test_status_service_get_artifact_stream_fallback_manifest(mock_orchestrator):
    service = StatusService(mock_orchestrator)
    mock_orchestrator.storage = AsyncMock()
    mock_orchestrator.storage.exists.return_value = True
    mock_orchestrator.storage.get_stream.return_value = ("stream", "application/json")
    context = JobContext(
        trace_id="t1",
        task_type="MORNING_REPORT",
        init_key="init",
        work_keys=["w1"],
        completed_work_keys=["w1"],
        failures=[],
        current_stage="completed",
        artifacts={}
    )
    mock_orchestrator.get_job_status.return_value = context

    stream, content_type = await service.get_artifact_stream("t1", "detailed_manifest")

    assert stream == "stream"
    assert content_type == "application/json"

@pytest.mark.asyncio
async def test_status_service_get_artifact_stream_storage_key_direct(mock_orchestrator):
    service = StatusService(mock_orchestrator)
    mock_orchestrator.storage = AsyncMock()
    mock_orchestrator.storage.exists.return_value = True
    mock_orchestrator.storage.get_stream.return_value = ("stream", "application/json")
    context = JobContext(
        trace_id="t1",
        task_type="MORNING_REPORT",
        init_key="init",
        work_keys=["w1"],
        completed_work_keys=["w1"],
        failures=[],
        current_stage="completed",
        artifacts={}
    )
    mock_orchestrator.get_job_status.return_value = context

    storage_key = "data:parse:data:download:data:work:w1"
    stream, content_type = await service.get_artifact_stream("t1", storage_key)

    assert stream == "stream"
    assert content_type == "application/json"
