"""Unit tests for ReportService"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.report_service import ReportService
from app.engine.orchestrator import WorkflowOrchestrator
from app.infrastructure.storage import StorageBackend, StateManager
from app.models.state_models import JobContext, FailureRecord


@pytest.fixture
def mock_storage():
    return AsyncMock(spec=StorageBackend)


@pytest.fixture
def mock_state():
    return AsyncMock(spec=StateManager)


@pytest.fixture
def mock_orchestrator(mock_storage, mock_state):
    orchestrator = MagicMock(spec=WorkflowOrchestrator)
    orchestrator.storage = mock_storage
    orchestrator.state_manager = mock_state
    orchestrator.get_job_status = AsyncMock()
    return orchestrator


@pytest.fixture
def service(mock_orchestrator):
    return ReportService(mock_orchestrator)


@pytest.mark.asyncio
async def test_build_morning_report_success(service, mock_orchestrator, mock_storage):
    """Test building morning report with successful data"""
    trace_id = "trace1"
    context = JobContext(
        trace_id=trace_id,
        task_type="MORNING_REPORT",
        init_key=f"job:{trace_id}:init",
        requested_limit=5,
        completed_work_keys=["task:trace1:work:1"],
        failures=[
            FailureRecord(
                work_key="task:trace1:work:2",
                stage="download",
                routing_key="cmd.downloader.start",
                input_key="data:work:task:trace1:work:2",
                error_msg="Download failed"
            )
        ],
        artifacts={
            "search_results": "data:discovery:job:trace1:input",
            "detailed_manifest": "data:manifest:trace1"
        },
        current_stage="completed"
    )
    mock_orchestrator.get_job_status.return_value = context

    # Mock manifest data
    manifest = [
        {
            "work_key": "task:trace1:work:1",
            "download_key": "data:download:data:work:task:trace1:work:1",
            "parse_key": "data:parse:data:download:data:work:task:trace1:work:1",
            "index_key": "data:index:data:parse:data:download:data:work:task:trace1:work:1"
        }
    ]

    # Mock storage responses
    async def storage_get(key):
        data = {
            f"data:manifest:{trace_id}": manifest,
            f"job:{trace_id}:init": {"query": "test query", "filters": {}},
            "data:discovery:job:trace1:input": {"query": "test query", "results": []},
            "data:download:data:work:task:trace1:work:1": {
                "filename": "paper1.pdf",
                "source_url": "http://example.com/paper1.pdf",
                "work": {
                    "title": "Test Paper",
                    "authors": ["Author 1", "Author 2"],
                    "openalex_id": "W123",
                    "doi": "10.1234/test"
                }
            },
            "data:parse:data:download:data:work:task:trace1:work:1": {
                "title": "Test Paper",
                "llm_summary": "This is a test paper summary",
                "meta": {"source_url": "http://example.com/paper1.pdf"}
            },
            "data:index:data:parse:data:download:data:work:task:trace1:work:1": {
                "collection": "default",
                "vector_count": 10,
                "persist_dir": "/path/to/vectors"
            }
        }
        return data.get(key)

    mock_storage.get.side_effect = storage_get

    report = await service.build_morning_report(trace_id, context)

    assert report.trace_id == trace_id
    assert report.task_type == "MORNING_REPORT"
    assert report.paper_count == 1
    assert report.failure_count == 1
    assert len(report.papers) == 1
    assert report.papers[0].paper.title == "Test Paper"
    assert report.papers[0].paper.authors == ["Author 1", "Author 2"]
    assert report.papers[0].summary.llm_summary == "This is a test paper summary"
    assert len(report.failures) == 1
    assert report.failures[0].work_key == "task:trace1:work:2"


@pytest.mark.asyncio
async def test_build_morning_report_no_manifest(service, mock_orchestrator, mock_storage):
    """Test building morning report without manifest (reconstruct from work_keys)"""
    trace_id = "trace2"
    context = JobContext(
        trace_id=trace_id,
        task_type="MORNING_REPORT",
        init_key=f"job:{trace_id}:init",
        requested_limit=5,
        completed_work_keys=["task:trace2:work:1"],
        artifacts={},
        current_stage="completed"
    )
    mock_orchestrator.get_job_status.return_value = context

    # Mock storage responses (no manifest, reconstruct keys)
    async def storage_get(key):
        data = {
            f"job:{trace_id}:init": {"query": "test", "filters": {}},
            "data:download:data:work:task:trace2:work:1": {
                "filename": "paper1.pdf",
                "source_url": "http://example.com/paper1.pdf"
            },
            "data:parse:data:download:data:work:task:trace2:work:1": {
                "title": "Paper Title",
                "llm_summary": "Summary"
            },
            "data:index:data:parse:data:download:data:work:task:trace2:work:1": {
                "collection": "default",
                "vector_count": 5
            }
        }
        return data.get(key)

    mock_storage.get.side_effect = storage_get

    report = await service.build_morning_report(trace_id, context)

    assert report.paper_count == 1
    assert len(report.papers) == 1
    assert report.papers[0].paper.title == "Paper Title"


@pytest.mark.asyncio
async def test_build_morning_report_missing_data(service, mock_orchestrator, mock_storage):
    """Test building report when some data is missing"""
    trace_id = "trace3"
    context = JobContext(
        trace_id=trace_id,
        task_type="MORNING_REPORT",
        init_key=f"job:{trace_id}:init",
        requested_limit=5,
        completed_work_keys=["task:trace3:work:1"],
        artifacts={},
        current_stage="completed"
    )
    mock_orchestrator.get_job_status.return_value = context

    # Mock storage returning None for some keys
    async def storage_get(key):
        # Only return parse data, missing download and index
        if key == "data:parse:data:download:data:work:task:trace3:work:1":
            return {"title": "Paper Title", "llm_summary": "Summary"}
        return None

    mock_storage.get.side_effect = storage_get

    report = await service.build_morning_report(trace_id, context)

    # Should still create report but with missing data
    assert report.paper_count == 1
    assert report.papers[0].paper.title == "Paper Title"
    # Missing data should be None or default
    assert report.papers[0].paper.pdf_url is None


@pytest.mark.asyncio
async def test_build_report_job_not_found(service, mock_orchestrator):
    """Test building report when job doesn't exist"""
    mock_orchestrator.get_job_status.return_value = None

    with pytest.raises(ValueError, match="Job trace999 not found"):
        await service.build_report("trace999")


@pytest.mark.asyncio
async def test_build_report_job_not_completed(service, mock_orchestrator):
    """Test building report when job is not completed"""
    trace_id = "trace4"
    context = JobContext(
        trace_id=trace_id,
        task_type="MORNING_REPORT",
        init_key=f"job:{trace_id}:init",
        current_stage="processing"
    )
    mock_orchestrator.get_job_status.return_value = context

    with pytest.raises(ValueError, match="is not completed yet"):
        await service.build_report(trace_id)


@pytest.mark.asyncio
async def test_build_summary_report(service, mock_orchestrator, mock_storage):
    """Test building summary report"""
    trace_id = "trace5"
    context = JobContext(
        trace_id=trace_id,
        task_type="SUMMARY_REPORT",
        init_key=f"job:{trace_id}:init",
        artifacts={},
        current_stage="completed"
    )
    mock_orchestrator.get_job_status.return_value = context

    overview_key = f"data:overview:task:{trace_id}:overview_in"
    overview_data = {
        "overview_md": "# Summary\n\nThis is a summary.",
        "meta": {
            "model": "gpt-4",
            "paper_count": 3,
            "domain": "AI",
            "style": "academic"
        }
    }

    async def storage_get(key):
        if key == overview_key:
            return overview_data
        return None

    async def storage_exists(key):
        return key == overview_key

    mock_storage.get.side_effect = storage_get
    mock_storage.exists.side_effect = storage_exists

    report = await service.build_summary_report(trace_id, context)

    assert report.trace_id == trace_id
    assert report.task_type == "SUMMARY_REPORT"
    assert report.overview_md == "# Summary\n\nThis is a summary."
    assert report.meta["paper_count"] == 3
    assert report.paper_count == 3


@pytest.mark.asyncio
async def test_build_report_unsupported_task_type(service, mock_orchestrator):
    """Test building report for unsupported task type"""
    trace_id = "trace6"
    context = JobContext(
        trace_id=trace_id,
        task_type="UNSUPPORTED_TASK",
        init_key=f"job:{trace_id}:init",
        current_stage="completed"
    )
    mock_orchestrator.get_job_status.return_value = context

    with pytest.raises(ValueError, match="not supported for task type"):
        await service.build_report(trace_id)
