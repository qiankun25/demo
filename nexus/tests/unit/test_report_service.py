import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.report_service import ReportService
from app.infrastructure.storage import StateManager, StorageBackend
from app.models.state_models import JobContext, FailureRecord

@pytest.fixture
def mock_storage():
    return AsyncMock(spec=StorageBackend)

@pytest.fixture
def mock_state():
    return AsyncMock(spec=StateManager)

@pytest.fixture
def service(mock_storage, mock_state):
    return ReportService(mock_storage, mock_state)

@pytest.mark.asyncio
async def test_build_report_success(service, mock_state, mock_storage):
    trace_id = "trace1"
    context = JobContext(
        trace_id=trace_id,
        task_type="MORNING_REPORT",
        init_key="init",
        completed_work_keys=["task:trace1:work:1"],
        failures=[
            FailureRecord(
                work_key="task:trace1:work:2",
                stage="download",
                routing_key="worker",
                input_key="input",
                error_msg="Failed"
            )
        ]
    )
    mock_state.get_context.return_value = context
    
    # Mock storage data
    async def get_side_effect(key):
        data = {
            "data:work:task:trace1:work:1": {"title": "Paper 1"},
            "data:download:task:trace1:work:1": {"path": "/tmp/1.pdf"},
            "data:parsed:task:trace1:work:1": {"summary": "Summary"},
            "index:vector:task:trace1:work:1": {"id": "1"}
        }
        return data.get(key)
        
    mock_storage.get.side_effect = get_side_effect
    
    report = await service.build_morning_report(trace_id)
    
    assert report["trace_id"] == trace_id
    assert report["paper_count"] == 1
    assert report["failure_count"] == 1
    assert len(report["papers"]) == 1
    assert report["papers"][0]["paper"]["title"] == "Paper 1"
    assert len(report["failures"]) == 1
    
    mock_storage.put.assert_called_once()
    mock_state.update_context.assert_called_once()

@pytest.mark.asyncio
async def test_build_report_missing_payload(service, mock_state, mock_storage):
    trace_id = "trace1"
    context = JobContext(
        trace_id=trace_id,
        task_type="MORNING_REPORT",
        init_key="init",
        completed_work_keys=["task:trace1:work:1"]
    )
    mock_state.get_context.return_value = context
    
    # Storage returns None for everything
    mock_storage.get.return_value = None
    
    report = await service.build_morning_report(trace_id)
    
    assert len(report["papers"]) == 0
    # Should still save report with empty papers
    mock_storage.put.assert_called_once()
