"""RabbitMQ connection and message operations manager

This module provides the MQManager class for managing RabbitMQ connections,
exchange declarations, command publishing, and event consumption.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.4
"""

import json
import logging
import time
from typing import Optional, Callable, Awaitable
import aio_pika
from aio_pika import ExchangeType, DeliveryMode, Message, connect_robust
from aio_pika.abc import AbstractConnection, AbstractChannel, AbstractExchange, AbstractQueue

from app.core.config import Settings
from app.models.messages import MessagePackage, MsgHeader, CommandPayload
from app.infrastructure.metrics import COMMAND_PUBLISH_SECONDS
from app.core.retry import with_retry, RetryConfig

logger = logging.getLogger(__name__)


class MQManager:
    """Manages RabbitMQ connections and operations
    
    Provides robust connection handling with automatic reconnection,
    exchange declarations, command publishing, and event consumption.
    
    Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.4
    """
    
    def __init__(self, config: Settings):
        """Initialize MQ Manager with configuration
        
        Args:
            config: Application settings containing RabbitMQ configuration
        """
        self.config = config
        self.connection: Optional[AbstractConnection] = None
        self.channel: Optional[AbstractChannel] = None
        self.cmd_exchange: Optional[AbstractExchange] = None
        self.evt_exchange: Optional[AbstractExchange] = None
        self._consuming = False
        
    async def connect(self) -> None:
        """Establish robust connection to RabbitMQ with auto-reconnection
        
        Creates a robust connection that automatically reconnects on failure,
        declares command and event exchanges, and sets up the channel.
        
        Requirements: 2.1, 2.2, 2.3
        
        Raises:
            aio_pika.exceptions.AMQPException: If connection fails
        """
        logger.info(f"Connecting to RabbitMQ at {self.config.rabbitmq_url}")
        
        # Requirement 2.1: Establish robust connection with auto-reconnection
        self.connection = await connect_robust(
            self.config.rabbitmq_url,
            client_properties={
                "connection_name": self.config.service_name
            }
        )
        
        # Create channel
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=10)
        
        # Requirement 2.2: Declare command exchange as durable direct exchange
        self.cmd_exchange = await self.channel.declare_exchange(
            name=self.config.cmd_exchange,
            type=ExchangeType.DIRECT,
            durable=True
        )
        logger.info(f"Declared command exchange: {self.config.cmd_exchange} (direct)")
        
        # Requirement 2.3: Declare event exchange as durable topic exchange
        self.evt_exchange = await self.channel.declare_exchange(
            name=self.config.evt_exchange,
            type=ExchangeType.TOPIC,
            durable=True
        )
        logger.info(f"Declared event exchange: {self.config.evt_exchange} (topic)")
        
        logger.info("RabbitMQ connection established successfully")
        
    async def disconnect(self) -> None:
        """Gracefully close RabbitMQ connection
        
        Closes the channel and connection, ensuring all pending operations complete.
        
        Raises:
            Exception: If disconnection fails
        """
        logger.info("Disconnecting from RabbitMQ")
        
        self._consuming = False
        
        if self.channel and not self.channel.is_closed:
            await self.channel.close()
            logger.debug("Channel closed")
            
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            logger.debug("Connection closed")
            
        logger.info("RabbitMQ disconnected successfully")
        
    @with_retry(RetryConfig(max_attempts=3))
    async def publish_command(
        self,
        routing_key: str,
        trace_id: str,
        task_type: str,
        input_key: str,
        task_id: Optional[str] = None,
        params: Optional[dict] = None
    ) -> None:
        """Publish a command message to a tool service
        
        Constructs a message package with header and command payload,
        then publishes it to the command exchange with persistent delivery.
        
        Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
        
        Args:
            routing_key: RabbitMQ routing key (e.g., "cmd.discovery.start")
            trace_id: Unique job identifier for tracing
            task_type: Type of task being executed
            input_key: Storage key for input data
            task_id: Optional task identifier (defaults to trace_id)
            params: Optional additional parameters
            
        Raises:
            ValueError: If connection is not established
            aio_pika.exceptions.AMQPException: If publishing fails
        """
        if not self.cmd_exchange:
            raise ValueError("MQ Manager not connected. Call connect() first.")
            
        start_time = time.time()
        
        # Use trace_id as task_id if not provided
        if task_id is None:
            task_id = trace_id
            
        # Requirement 3.1, 3.2: Construct message package with header and payload
        message_package = MessagePackage(
            header=MsgHeader(
                trace_id=trace_id,
                task_type=task_type,
                sender=self.config.service_name
            ),
            payload=CommandPayload(
                task_id=task_id,
                input_key=input_key,
                params=params or {}
            ).model_dump()
        )
        
        # Serialize to JSON
        message_body = message_package.model_dump_json().encode()
        
        # Requirement 3.4: Create message with persistent delivery mode
        message = Message(
            body=message_body,
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers={
                "trace_id": trace_id,
                "task_type": task_type
            }
        )
        
        # Publish to command exchange
        await self.cmd_exchange.publish(
            message=message,
            routing_key=routing_key
        )
        
        # Record metric
        COMMAND_PUBLISH_SECONDS.labels(routing_key=routing_key).observe(time.time() - start_time)
        
        # Requirement 3.5: Log the routing key and trace ID
        logger.info(
            f"Published command: routing_key={routing_key}, trace_id={trace_id}",
            extra={"trace_id": trace_id, "routing_key": routing_key}
        )
        
    async def start_consuming(
        self,
        queue_name: str,
        callback: Callable[[MessagePackage], Awaitable[None]]
    ) -> None:
        """Start consuming events from the event queue
        
        Declares the event queue, binds it to all event routing keys using
        the pattern "evt.#", and starts consuming messages.
        
        Requirements: 2.4, 4.1, 4.2, 4.4
        
        Args:
            queue_name: Name of the queue to consume from
            callback: Async function to process received messages
            
        Raises:
            ValueError: If connection is not established
            aio_pika.exceptions.AMQPException: If queue operations fail
        """
        if not self.channel or not self.evt_exchange:
            raise ValueError("MQ Manager not connected. Call connect() first.")
            
        # Requirement 2.4: Declare queue and bind to all event routing keys
        queue: AbstractQueue = await self.channel.declare_queue(
            name=queue_name,
            durable=True
        )
        
        # Bind to all event routing keys using topic pattern
        await queue.bind(
            exchange=self.evt_exchange,
            routing_key="evt.#"
        )
        
        logger.info(f"Queue '{queue_name}' bound to event exchange with pattern 'evt.#'")
        
        self._consuming = True
        
        # Define message processor
        async def process_message(message: aio_pika.IncomingMessage) -> None:
            """Process incoming message and acknowledge/reject appropriately
            
            Requirements: 4.1, 4.2, 4.4, 4.5
            """
            async with message.process():
                try:
                    # Requirement 4.1: Deserialize message into MessagePackage
                    body = message.body.decode()
                    data = json.loads(body)
                    message_package = MessagePackage(**data)
                    
                    # Requirement 4.2: Extract trace ID and routing key
                    trace_id = message_package.header.trace_id
                    routing_key = message.routing_key or "unknown"
                    
                    logger.debug(
                        f"Received event: routing_key={routing_key}, trace_id={trace_id}",
                        extra={"trace_id": trace_id, "routing_key": routing_key}
                    )
                    
                    # Process the message with callback
                    await callback(message_package)
                    
                    # Requirement 4.4: Message is acknowledged automatically by context manager
                    logger.debug(
                        f"Event processed successfully: trace_id={trace_id}",
                        extra={"trace_id": trace_id}
                    )
                    
                except Exception as e:
                    # Requirement 4.5: Log error and reject message for retry
                    logger.error(
                        f"Failed to process event: {str(e)}",
                        exc_info=True,
                        extra={
                            "routing_key": message.routing_key,
                            "error": str(e)
                        }
                    )
                    # Message will be rejected by context manager on exception
                    raise
        
        # Start consuming
        await queue.consume(process_message)
        logger.info(f"Started consuming events from queue '{queue_name}'")
        
    async def is_healthy(self) -> bool:
        """Check if RabbitMQ connection is healthy
        
        Verifies that the connection and channel are established and not closed.
        
        Returns:
            bool: True if connection is healthy, False otherwise
        """
        try:
            if not self.connection or self.connection.is_closed:
                return False
                
            if not self.channel or self.channel.is_closed:
                return False
                
            return True
            
        except Exception as e:
            logger.warning(f"Health check failed: {str(e)}")
            return False
