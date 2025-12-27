import pytest
from unittest.mock import MagicMock, patch
from app.infrastructure.storage import MinIOStorage, StateManager
from app.core.config import Settings
from app.models.state_models import JobContext
import json
import pickle

@pytest.fixture
def mock_settings():
    return Settings(
        minio_endpoint="localhost:9000",
        minio_access_key="admin",
        minio_secret_key="password",
        minio_bucket="test-bucket"
    )

@pytest.fixture
def mock_minio():
    with patch("app.infrastructure.storage.Minio") as mock:
        yield mock.return_value

@pytest.fixture
def storage(mock_settings, mock_minio):
    return MinIOStorage(mock_settings)

@pytest.mark.asyncio
async def test_storage_put_json(storage, mock_minio):
    data = {"key": "value"}
    await storage.put("test-key", data)
    
    mock_minio.put_object.assert_called_once()
    args = mock_minio.put_object.call_args
    # args[0] is (bucket, key, data, length)
    assert args[0][1] == "test-key"
    # kwargs has content_type
    assert args[1]["content_type"] == "application/json"

@pytest.mark.asyncio
async def test_storage_get_json(storage, mock_minio):
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({"key": "value"}).encode()
    mock_minio.get_object.return_value = mock_response
    
    result = await storage.get("test-key")
    assert result == {"key": "value"}

@pytest.mark.asyncio
async def test_state_manager_update(storage):
    state_manager = StateManager(storage)
    trace_id = "test-trace"
    
    # Mock existing context
    initial_ctx = JobContext(trace_id=trace_id, task_type="test", init_key="init")
    
    # Mock get to return the dict
    with patch.object(storage, "get", return_value=initial_ctx.model_dump()):
        # Mock put
        with patch.object(storage, "put") as mock_put:
            updated = await state_manager.update_context(trace_id, {"current_stage": "next"})
            
            assert updated.current_stage == "next"
            mock_put.assert_called_once()
            saved_data = mock_put.call_args[0][1]
            assert saved_data["current_stage"] == "next"
