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
