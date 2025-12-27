"""Unit tests for MQManager

Tests RabbitMQ connection management, message publishing, and health checks.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.infrastructure.mq_manager import MQManager
from app.core.config import Settings
from app.models.messages import MessagePackage, MsgHeader, CommandPayload


@pytest.fixture
def settings():
    """Create test settings"""
    return Settings(
        rabbitmq_url="amqp://guest:guest@localhost:5672/",
        cmd_exchange="test.cmd.exchange",
        evt_exchange="test.evt.exchange",
        service_name="test-service"
    )


@pytest.fixture
def mq_manager(settings):
    """Create MQManager instance"""
    return MQManager(settings)


@pytest.mark.asyncio
async def test_mq_manager_initialization(mq_manager, settings):
    """Test MQManager initializes with correct configuration"""
    assert mq_manager.config == settings
    assert mq_manager.connection is None
    assert mq_manager.channel is None
    assert mq_manager.cmd_exchange is None
    assert mq_manager.evt_exchange is None


@pytest.mark.asyncio
async def test_connect_establishes_connection(mq_manager):
    """Test connect() establishes robust connection and declares exchanges"""
    # Mock aio_pika components
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    mock_cmd_exchange = AsyncMock()
    mock_evt_exchange = AsyncMock()
    
    mock_connection.channel = AsyncMock(return_value=mock_channel)
    mock_channel.set_qos = AsyncMock()
    mock_channel.declare_exchange = AsyncMock(
        side_effect=[mock_cmd_exchange, mock_evt_exchange]
    )
    
    with patch('app.infrastructure.mq_manager.connect_robust', return_value=mock_connection):
        await mq_manager.connect()
    
    # Verify connection was established
    assert mq_manager.connection == mock_connection
    assert mq_manager.channel == mock_channel
    assert mq_manager.cmd_exchange == mock_cmd_exchange
    assert mq_manager.evt_exchange == mock_evt_exchange
    
    # Verify exchanges were declared correctly
    assert mock_channel.declare_exchange.call_count == 2


@pytest.mark.asyncio
async def test_publish_command_creates_valid_message(mq_manager):
    """Test publish_command() creates and publishes valid message package"""
    # Setup mock exchange
    mock_exchange = AsyncMock()
    mq_manager.cmd_exchange = mock_exchange
    
    # Publish command
    await mq_manager.publish_command(
        routing_key="cmd.discovery.start",
        trace_id="test-trace-123",
        task_type="MORNING_REPORT",
        input_key="task:test-trace-123:init"
    )
    
    # Verify publish was called
    mock_exchange.publish.assert_called_once()
    call_args = mock_exchange.publish.call_args
    
    # Verify routing key
    assert call_args.kwargs['routing_key'] == "cmd.discovery.start"
    
    # Verify message properties
    message = call_args.kwargs['message']
    assert message.delivery_mode.value == 2  # PERSISTENT


@pytest.mark.asyncio
async def test_publish_command_without_connection_raises_error(mq_manager):
    """Test publish_command() raises error when not connected"""
    with pytest.raises(ValueError, match="not connected"):
        await mq_manager.publish_command(
            routing_key="cmd.test",
            trace_id="test-123",
            task_type="TEST",
            input_key="test-key"
        )


@pytest.mark.asyncio
async def test_is_healthy_returns_true_when_connected(mq_manager):
    """Test is_healthy() returns True when connection is active"""
    # Mock healthy connection
    mock_connection = MagicMock()
    mock_connection.is_closed = False
    mock_channel = MagicMock()
    mock_channel.is_closed = False
    
    mq_manager.connection = mock_connection
    mq_manager.channel = mock_channel
    
    assert await mq_manager.is_healthy() is True


@pytest.mark.asyncio
async def test_is_healthy_returns_false_when_disconnected(mq_manager):
    """Test is_healthy() returns False when connection is closed"""
    assert await mq_manager.is_healthy() is False


@pytest.mark.asyncio
async def test_disconnect_closes_connection(mq_manager):
    """Test disconnect() closes channel and connection"""
    # Setup mocks
    mock_connection = AsyncMock()
    mock_connection.is_closed = False
    mock_channel = AsyncMock()
    mock_channel.is_closed = False
    
    mq_manager.connection = mock_connection
    mq_manager.channel = mock_channel
    
    await mq_manager.disconnect()
    
    # Verify close was called
    mock_channel.close.assert_called_once()
    mock_connection.close.assert_called_once()
