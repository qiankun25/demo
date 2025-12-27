import pytest
from unittest.mock import AsyncMock, MagicMock
from app.engine.orchestrator import WorkflowOrchestrator
from app.models.workflow_models import WorkflowDefinition, WorkflowStage
from app.models.messages import MessagePackage, MsgHeader
from app.models.state_models import JobContext
from app.infrastructure.mq_manager import MQManager
from app.infrastructure.storage import StateManager, StorageBackend
from app.engine.workflows import WorkflowRegistry

@pytest.fixture
def mock_mq():
    return AsyncMock(spec=MQManager)

@pytest.fixture
def mock_state():
    return AsyncMock(spec=StateManager)

@pytest.fixture
def mock_storage():
    return AsyncMock(spec=StorageBackend)

@pytest.fixture
def mock_registry():
    registry = MagicMock(spec=WorkflowRegistry)
    workflow = WorkflowDefinition(
        name="Test Workflow",
        task_type="TEST_TASK",
        initial_stage="stage1",
        stages=[
            WorkflowStage(
                name="stage1",
                stage_type="single",
                command_routing_key="cmd.stage1",
                success_event="evt.stage1.finished",
                failure_event="evt.stage1.failed",
                next_stage="stage2"
            )
        ]
    )
    registry.get_workflow.return_value = workflow
    return registry

@pytest.fixture
def orchestrator(mock_mq, mock_state, mock_storage, mock_registry):
    return WorkflowOrchestrator(mock_mq, mock_state, mock_storage, mock_registry)

@pytest.mark.asyncio
async def test_submit_job(orchestrator, mock_mq, mock_state, mock_storage):
    trace_id = await orchestrator.submit_job("TEST_TASK", {"param": "value"})
    
    assert trace_id is not None
    mock_state.save_context.assert_called_once()
    mock_storage.put.assert_called_once()
    mock_mq.publish_command.assert_called_once()
    
    args = mock_mq.publish_command.call_args
    assert args.kwargs["routing_key"] == "cmd.stage1"

@pytest.mark.asyncio
async def test_handle_event_success(orchestrator, mock_state):
    # Mock context
    context = JobContext(trace_id="trace1", task_type="TEST_TASK", init_key="init")
    mock_state.get_context.return_value = context
    
    # Mock handler
    handler_mock = AsyncMock()
    # In orchestrator logic: event_key = f"evt.{task_type}.finished"
    # task_type in header is "stage1" -> "evt.stage1.finished"
    orchestrator.handlers["evt.stage1.finished"] = handler_mock
    
    # Message
    msg = MessagePackage(
        header=MsgHeader(trace_id="trace1", task_type="stage1", sender="worker"),
        payload={"status": "SUCCESS"}
    )
    
    await orchestrator.handle_event(msg)
    
    handler_mock.handle.assert_called_once()

@pytest.mark.asyncio
async def test_handle_event_failure(orchestrator, mock_state):
    context = JobContext(trace_id="trace1", task_type="TEST_TASK", init_key="init")
    mock_state.get_context.return_value = context
    
    orchestrator.failure_handler = AsyncMock()
    
    msg = MessagePackage(
        header=MsgHeader(trace_id="trace1", task_type="stage1", sender="worker"),
        payload={"status": "FAIL", "error_msg": "error"}
    )
    
    await orchestrator.handle_event(msg)
    
    orchestrator.failure_handler.handle.assert_called_once()
