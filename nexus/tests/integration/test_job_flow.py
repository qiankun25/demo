import pytest
import asyncio
import aio_pika
import json
from testcontainers.rabbitmq import RabbitMqContainer
from testcontainers.minio import MinioContainer
from app.infrastructure.mq_manager import MQManager
from app.infrastructure.storage import MinIOStorage, StateManager
from app.core.config import Settings
from app.engine.orchestrator import WorkflowOrchestrator
from app.engine.workflows import WorkflowRegistry
from app.models.messages import MessagePackage, MsgHeader

# Skip if docker not available?
# But we detected docker.

@pytest.fixture(scope="module")
def rabbitmq():
    with RabbitMqContainer("rabbitmq:3.9-management") as rabbit:
        yield rabbit

@pytest.fixture(scope="module")
def minio():
    with MinioContainer("minio/minio:latest", access_key="minioadmin", secret_key="minioadmin") as minio:
        yield minio

@pytest.fixture
def settings(rabbitmq, minio):
    # RabbitMQ URL from container
    rabbit_url = rabbitmq.get_connection_url()
    # MinIO URL from container
    # MinioContainer exposes port, we need to format it.
    # get_url() returns http://host:port
    minio_endpoint = minio.get_url().replace("http://", "")
    
    return Settings(
        rabbitmq_url=rabbit_url,
        minio_endpoint=minio_endpoint,
        minio_access_key="minioadmin",
        minio_secret_key="minioadmin",
        minio_secure=False,
        minio_bucket="test-papers",
        workflow_config_path="config/workflows.yaml",
        event_queue="test_events"
    )

@pytest.mark.asyncio
async def test_end_to_end_job(settings):
    # Initialize components
    mq = MQManager(settings)
    await mq.connect()
    
    storage = MinIOStorage(settings)
    state_manager = StateManager(storage)
    registry = WorkflowRegistry.from_yaml(settings.workflow_config_path)
    
    orchestrator = WorkflowOrchestrator(mq, state_manager, storage, registry)
    
    # Start consumer
    consume_task = asyncio.create_task(
        mq.start_consuming(settings.event_queue, orchestrator.handle_event)
    )
    
    # Submit job
    trace_id = await orchestrator.submit_job("MORNING_REPORT", {"limit": 1})
    assert trace_id
    
    # Verify job created
    status = await orchestrator.get_job_status(trace_id)
    assert status.current_stage == "discovery"
    
    # Simulate Discovery Event
    results_key = f"data:discovery:{trace_id}"
    await storage.put(results_key, [{"best_oa_location": {"pdf_url": "http://example.com/1.pdf"}}])
    
    msg = MessagePackage(
        header=MsgHeader(trace_id=trace_id, task_type="discovery", sender="discovery_service"),
        payload={
            "status": "SUCCESS",
            "output_key": results_key
        }
    )
    
    exchange = await mq.channel.get_exchange(settings.evt_exchange)
    await exchange.publish(
        aio_pika.Message(body=msg.model_dump_json().encode()),
        routing_key="evt.discovery.finished"
    )
    
    # Wait for processing
    for _ in range(10):
        await asyncio.sleep(0.5)
        status = await orchestrator.get_job_status(trace_id)
        if status.current_stage == "processing":
            break
            
    assert status.current_stage == "processing"
    assert len(status.work_keys) == 1
    work_key = status.work_keys[0]
    
    # Simulate Download Event
    msg = MessagePackage(
        header=MsgHeader(trace_id=trace_id, task_type="downloader", sender="download_service"),
        payload={
            "status": "SUCCESS",
            "input_key": f"data:work:{work_key}",
            "output_key": f"files/{work_key}.pdf"
        }
    )
    await exchange.publish(
        aio_pika.Message(body=msg.model_dump_json().encode()),
        routing_key="evt.downloader.finished"
    )
    
    await asyncio.sleep(0.5)
    
    # Simulate Parse Event
    msg = MessagePackage(
        header=MsgHeader(trace_id=trace_id, task_type="parser", sender="parser_service"),
        payload={
            "status": "SUCCESS",
            "input_key": work_key,
            "output_key": f"data:parsed:{work_key}"
        }
    )
    await storage.put(f"data:parsed:{work_key}", {"summary": "test"})
    
    await exchange.publish(
        aio_pika.Message(body=msg.model_dump_json().encode()),
        routing_key="evt.parser.finished"
    )
    
    await asyncio.sleep(0.5)
    
    # Simulate Index Event
    msg = MessagePackage(
        header=MsgHeader(trace_id=trace_id, task_type="indexer", sender="indexer_service"),
        payload={
            "status": "SUCCESS",
            "input_key": work_key,
            "output_key": f"index:vector:{work_key}"
        }
    )
    await storage.put(f"index:vector:{work_key}", {"id": "1"})
    
    await exchange.publish(
        aio_pika.Message(body=msg.model_dump_json().encode()),
        routing_key="evt.indexer.finished"
    )
    
    # Wait for completion
    for _ in range(10):
        await asyncio.sleep(0.5)
        status = await orchestrator.get_job_status(trace_id)
        if status.current_stage == "completed":
            break
            
    assert status.current_stage == "completed"
    assert status.report_key
    
    # Verify report
    report = await storage.get(status.report_key)
    assert report["paper_count"] == 1
    
    # Cleanup
    consume_task.cancel()
    await mq.disconnect()
