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
    assert mock_state.atomic_update_context.call_count == 1
    # Check that update function adds artifacts
    update_func = mock_state.atomic_update_context.call_args[0][1]
    
    ctx_copy = context.model_copy()
    updates = update_func(ctx_copy)
    
    assert "work_keys" in updates
    assert "artifacts" in updates
    assert updates["artifacts"]["search_results"] == "results_key"

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
async def test_indexer_handler(mock_mq, mock_state, mock_storage, context, message_package):
    handler = IndexerFinishedHandler(mock_mq, mock_state, mock_storage)
    msg = message_package({
        "status": "SUCCESS",
        "output_key": "data:index:task:trace:work:0"
    })
    
    # Mock state get
    context.work_keys = ["task:trace:work:0"]
    context.task_type = "MORNING_REPORT" # Set task type for report logic
    
    # Mock atomic_update_context to return an updated context that is complete
    async def mock_atomic_update(trace_id, func):
        ctx = context.model_copy()
        updates = func(ctx)
        # Apply updates
        ctx_dict = ctx.model_dump()
        ctx_dict.update(updates)
        return JobContext(**ctx_dict)
        
    mock_state.atomic_update_context.side_effect = mock_atomic_update
    
    await handler.handle(msg, context)
    
    # Verify manifest generation
    assert mock_storage.put.call_count == 1
    call_args = mock_storage.put.call_args
    assert "data:manifest:" in call_args[0][0]
    
    # Verify status update
    assert mock_state.atomic_update_context.call_count == 2 # 1 for work completion, 1 for final status
    
    # Verify artifacts update in final call
    final_call = mock_state.atomic_update_context.call_args_list[1]
    update_func = final_call[0][1]
    ctx_copy = context.model_copy()
    updates = update_func(ctx_copy)
    
    assert "artifacts" in updates
    assert "detailed_manifest" in updates["artifacts"]
    assert updates["current_stage"] == "completed"

@pytest.mark.asyncio
async def test_failure_handler(mock_state, mock_mq, mock_storage, context, message_package):
    handler = FailureHandler(mock_state, mock_mq, mock_storage)
    msg = message_package({
        "status": "FAIL",
        "input_key": "data:work:task:trace:work:0",
        "error_msg": "Boom"
    })
    
    context.task_type = "MORNING_REPORT" # Enable report/manifest logic
    
    # Mock atomic update
    async def mock_atomic_update(trace_id, func):
        ctx = context.model_copy()
        updates = func(ctx)
        # Apply updates
        ctx_dict = ctx.model_dump()
        ctx_dict.update(updates)
        return JobContext(**ctx_dict)
        
    mock_state.atomic_update_context.side_effect = mock_atomic_update
    
    await handler.handle(msg, context)
    
    # Should call twice: 1. Record Failure 2. Finalize Status/Manifest
    assert mock_state.atomic_update_context.call_count == 2
    
    # Check failure record (first call)
    call_args = mock_state.atomic_update_context.call_args_list[0]
    update_func = call_args[0][1]
    
    ctx_copy = context.model_copy()
    updates = update_func(ctx_copy)
    
    assert len(updates["failures"]) == 1
    assert updates["failures"][0].work_key == "task:trace:work:0"
    
    # Check manifest generation (second call)
    final_call = mock_state.atomic_update_context.call_args_list[1]
    update_func = final_call[0][1]
    ctx_copy = context.model_copy()
    updates = update_func(ctx_copy)
    
    assert "artifacts" in updates
    assert "detailed_manifest" in updates["artifacts"]
