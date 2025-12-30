"""
Unit tests for SUMMARY_REPORT workflow in Orchestrator
Tests the new direct papers parameter mode and legacy summary_report_key mode
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.engine.orchestrator import WorkflowOrchestrator
from app.models.state_models import JobContext


@pytest.fixture
def mock_mq():
    """Mock MQ Manager"""
    mq = AsyncMock()
    mq.publish_command = AsyncMock()
    return mq


@pytest.fixture
def mock_storage():
    """Mock Storage Backend"""
    storage = AsyncMock()
    storage.put = AsyncMock()
    storage.get = AsyncMock()
    return storage


@pytest.fixture
def mock_state_manager():
    """Mock State Manager"""
    state_manager = AsyncMock()
    state_manager.save_context = AsyncMock()
    state_manager.update_context = AsyncMock()
    state_manager.get_context = AsyncMock()
    return state_manager


@pytest.fixture
def mock_registry():
    """Mock Workflow Registry"""
    registry = MagicMock()
    workflow = MagicMock()
    workflow.stages = []
    registry.get_workflow = MagicMock(return_value=workflow)
    return registry


@pytest.fixture
def orchestrator(mock_mq, mock_storage, mock_state_manager, mock_registry):
    """Create orchestrator with mocked dependencies"""
    return WorkflowOrchestrator(
        mq=mock_mq,
        state_manager=mock_state_manager,
        storage=mock_storage,
        registry=mock_registry
    )


@pytest.mark.asyncio
async def test_summary_report_with_direct_papers(orchestrator, mock_mq, mock_storage, mock_state_manager):
    """Test SUMMARY_REPORT with direct papers parameter (new mode)"""
    # Arrange
    test_papers = [
        {
            "pdf_url": "http://minio:9000/downloads/file1.pdf?presigned=xxx",
            "title": "Paper 1",
            "authors": ["Author A"]
        },
        {
            "pdf_url": "http://minio:9000/downloads/file2.pdf?presigned=yyy",
            "title": "Paper 2",
            "authors": ["Author B", "Author C"]
        }
    ]
    
    params = {
        "papers": test_papers,
        "domain": "medical",
        "style": "academic"
    }
    
    # Act
    trace_id = await orchestrator.submit_job("SUMMARY_REPORT", params)
    
    # Assert
    assert trace_id is not None
    
    # Verify storage.put was called for input data
    storage_put_calls = mock_storage.put.call_args_list
    assert len(storage_put_calls) >= 3  # 1 input + 2 papers
    
    # Verify input data was stored
    input_call = storage_put_calls[0]
    assert "data:job:" in input_call[0][0]
    
    # Verify summary_report_input was stored
    summary_input_call = storage_put_calls[1]
    assert f"data:summary_report_input:{trace_id}" == summary_input_call[0][0]
    stored_data = summary_input_call[0][1]
    assert stored_data["papers"] == test_papers
    assert stored_data["domain"] == "medical"
    
    # Verify paper work data was stored
    for i in range(2):
        paper_call = storage_put_calls[2 + i]
        paper_key = paper_call[0][0]
        paper_data = paper_call[0][1]
        
        assert "data:work:" in paper_key
        assert paper_data["pdf_url"] == test_papers[i]["pdf_url"]
        assert paper_data["title"] == test_papers[i]["title"]
        assert paper_data["authors"] == test_papers[i]["authors"]
        assert paper_data["content_type"] == "application/pdf"
    
    # Verify parser commands were published
    assert mock_mq.publish_command.call_count == 2
    for i, call in enumerate(mock_mq.publish_command.call_args_list):
        kwargs = call[1]
        assert kwargs["routing_key"] == "cmd.parser.start"
        assert kwargs["trace_id"] == trace_id
        assert kwargs["task_type"] == "parser"
        assert "data:work:" in kwargs["input_key"]
    
    # Verify context was saved
    mock_state_manager.save_context.assert_called_once()
    saved_context = mock_state_manager.save_context.call_args[0][0]
    assert saved_context.trace_id == trace_id
    assert saved_context.task_type == "SUMMARY_REPORT"
    assert saved_context.current_stage == "processing"
    assert len(saved_context.work_keys) == 2


@pytest.mark.asyncio
async def test_summary_report_with_legacy_key(orchestrator, mock_mq, mock_storage, mock_state_manager):
    """Test SUMMARY_REPORT with summary_report_key (legacy mode)"""
    # Arrange
    test_papers = [
        {
            "pdf_url": "http://example.com/paper1.pdf",
            "title": "Legacy Paper 1",
            "authors": ["Author X"]
        }
    ]
    
    legacy_key = "seed:summary_report:legacy_test"
    legacy_data = {
        "papers": test_papers,
        "domain": "computer_science"
    }
    
    # Mock storage.get to return legacy data
    mock_storage.get.return_value = legacy_data
    
    params = {
        "summary_report_key": legacy_key,
        "domain": "computer_science"
    }
    
    # Act
    trace_id = await orchestrator.submit_job("SUMMARY_REPORT", params)
    
    # Assert
    assert trace_id is not None
    
    # Verify storage.get was called with legacy key
    mock_storage.get.assert_called_once_with(legacy_key)
    
    # Verify parser command was published
    assert mock_mq.publish_command.call_count == 1
    
    # Verify context was saved
    mock_state_manager.save_context.assert_called_once()
    saved_context = mock_state_manager.save_context.call_args[0][0]
    assert len(saved_context.work_keys) == 1


@pytest.mark.asyncio
async def test_summary_report_missing_parameters(orchestrator):
    """Test SUMMARY_REPORT fails when neither papers nor summary_report_key provided"""
    params = {"domain": "test"}
    
    with pytest.raises(ValueError) as exc_info:
        await orchestrator.submit_job("SUMMARY_REPORT", params)
    
    assert "requires either 'papers' or 'summary_report_key'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_summary_report_invalid_papers_format(orchestrator):
    """Test SUMMARY_REPORT fails when papers is not a list"""
    params = {"papers": "not_a_list"}
    
    with pytest.raises(ValueError) as exc_info:
        await orchestrator.submit_job("SUMMARY_REPORT", params)
    
    assert "'papers' must be a list" in str(exc_info.value)


@pytest.mark.asyncio
async def test_summary_report_paper_missing_pdf_url(orchestrator):
    """Test SUMMARY_REPORT fails when paper is missing pdf_url"""
    params = {
        "papers": [
            {"title": "No URL Paper"}
        ]
    }
    
    with pytest.raises(ValueError) as exc_info:
        await orchestrator.submit_job("SUMMARY_REPORT", params)
    
    assert "must have non-empty 'pdf_url'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_summary_report_paper_empty_pdf_url(orchestrator):
    """Test SUMMARY_REPORT fails when paper has empty pdf_url"""
    params = {
        "papers": [
            {"pdf_url": "", "title": "Empty URL"}
        ]
    }
    
    with pytest.raises(ValueError) as exc_info:
        await orchestrator.submit_job("SUMMARY_REPORT", params)
    
    assert "must have non-empty 'pdf_url'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_summary_report_paper_not_dict(orchestrator):
    """Test SUMMARY_REPORT fails when paper is not a dict"""
    params = {
        "papers": [
            "not_a_dict"
        ]
    }
    
    with pytest.raises(ValueError) as exc_info:
        await orchestrator.submit_job("SUMMARY_REPORT", params)
    
    assert "must be a dict" in str(exc_info.value)


@pytest.mark.asyncio
async def test_summary_report_empty_papers_list(orchestrator):
    """Test SUMMARY_REPORT fails when papers list is empty"""
    params = {"papers": []}
    
    with pytest.raises(ValueError) as exc_info:
        await orchestrator.submit_job("SUMMARY_REPORT", params)
    
    assert "requires at least one paper" in str(exc_info.value)


@pytest.mark.asyncio
async def test_summary_report_with_presigned_urls(orchestrator, mock_mq, mock_storage, mock_state_manager):
    """Test SUMMARY_REPORT correctly handles presigned URLs from upload service"""
    # Arrange - Simulate real presigned URLs from MinIO
    test_papers = [
        {
            "pdf_url": "http://minio:9000/downloads/uploads/uuid1/doc1.pdf?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...",
            "title": "Uploaded Document 1",
            "authors": ["User A"]
        },
        {
            "pdf_url": "http://minio:9000/downloads/uploads/uuid2/doc2.pdf?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...",
            "title": "Uploaded Document 2",
            "authors": []
        }
    ]
    
    params = {
        "papers": test_papers,
        "domain": "medical"
    }
    
    # Act
    trace_id = await orchestrator.submit_job("SUMMARY_REPORT", params)
    
    # Assert
    assert trace_id is not None
    
    # Verify parser commands contain correct presigned URLs
    for i, call in enumerate(mock_mq.publish_command.call_args_list):
        kwargs = call[1]
        input_key = kwargs["input_key"]
        
        # Find the corresponding storage.put call for this input_key
        for put_call in mock_storage.put.call_args_list:
            if put_call[0][0] == input_key:
                paper_data = put_call[0][1]
                # Verify presigned URL is preserved
                assert "X-Amz-Algorithm" in paper_data["pdf_url"]
                assert paper_data["pdf_url"] == test_papers[i]["pdf_url"]
                break

