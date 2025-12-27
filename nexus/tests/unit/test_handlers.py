import pytest
from unittest.mock import AsyncMock, MagicMock
from app.engine.handlers import (
    DiscoveryFinishedHandler,
    DownloaderFinishedHandler,
    ParserFinishedHandler,
    IndexerFinishedHandler,
    FailureHandler
)
from app.models.messages import MessagePackage, MsgHeader, EventPayload
from app.models.state_models import JobContext
from app.infrastructure.mq_manager import MQManager
from app.infrastructure.storage import StorageBackend, StateManager

@pytest.fixture
def mock_mq():
    return AsyncMock(spec=MQManager)

@pytest.fixture
def mock_storage():
    return AsyncMock(spec=StorageBackend)

@pytest.fixture
def mock_state():
    return AsyncMock(spec=StateManager)

@pytest.fixture
def context():
    return JobContext(trace_id="test-trace", task_type="test", init_key="init")

@pytest.fixture
def message_package():
    def _create(payload_dict):
        return MessagePackage(
            header=MsgHeader(trace_id="test-trace", task_type="test", sender="sender"),
            payload=payload_dict
        )
    return _create

@pytest.mark.asyncio
async def test_discovery_handler(mock_mq, mock_storage, mock_state, context, message_package):
    handler = DiscoveryFinishedHandler(mock_mq, mock_storage, mock_state)
    
    # Mock storage return
    results = [
        {"best_oa_location": {"pdf_url": "http://pdf"}}, # Valid
        {"best_oa_location": {"pdf_url": None}} # Invalid
    ]
    mock_storage.get.return_value = results
    
    msg = message_package({
        "status": "SUCCESS",
        "output_key": "results_key"
    })
    
    await handler.handle(msg, context)
    
    # Should publish 1 command
    assert mock_mq.publish_command.call_count == 1
    # Check args
    args = mock_mq.publish_command.call_args
    assert args.kwargs['task_type'] == "downloader"
    
    # Should update state
    assert mock_state.update_context.call_count == 1
    update_args = mock_state.update_context.call_args
    assert "work_keys" in update_args[0][1]

@pytest.mark.asyncio
async def test_downloader_handler(mock_mq, context, message_package):
    handler = DownloaderFinishedHandler(mock_mq)
    msg = message_package({
        "status": "SUCCESS",
        "input_key": "data:work:task:123:work:0",
        "output_key": "file_path"
    })
    
    await handler.handle(msg, context)
    
    mock_mq.publish_command.assert_called_once()
    assert mock_mq.publish_command.call_args.kwargs['task_type'] == "parser"

@pytest.mark.asyncio
async def test_indexer_handler(mock_mq, mock_state, context, message_package):
    handler = IndexerFinishedHandler(mock_mq, mock_state)
    msg = message_package({
        "status": "SUCCESS",
        "input_key": "data:parsed:task:trace:work:0"
    })
    
    # Mock state get
    context.work_keys = ["task:trace:work:0"]
    mock_state.get_context.return_value = context
    
    await handler.handle(msg, context)
    
    # Should update completed
    mock_state.update_context.assert_called_once()
    updates = mock_state.update_context.call_args[0][1]
    assert "task:trace:work:0" in updates["completed_work_keys"]
    assert updates["current_stage"] == "completed"

@pytest.mark.asyncio
async def test_failure_handler(mock_state, context, message_package):
    handler = FailureHandler(mock_state)
    msg = message_package({
        "status": "FAIL",
        "input_key": "data:work:task:trace:work:0",
        "error_msg": "Boom"
    })
    
    mock_state.get_context.return_value = context
    
    await handler.handle(msg, context)
    
    mock_state.update_context.assert_called_once()
    updates = mock_state.update_context.call_args[0][1]
    assert len(updates["failures"]) == 1
    assert updates["failures"][0].work_key == "task:trace:work:0"
