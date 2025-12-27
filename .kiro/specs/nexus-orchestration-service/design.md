# Design Document

## Overview

The Nexus Orchestration Service will be refactored from a monolithic class-based design into a modular FastAPI microservice following clean architecture principles. The new design separates concerns into distinct layers: API routing, business logic (workflow orchestration), infrastructure (RabbitMQ, storage), and data models. The service will support configurable DAG-based workflows, maintain persistent state for job tracking, handle partial failures gracefully, and provide comprehensive observability.

The architecture follows the hexagonal/ports-and-adapters pattern where the core workflow engine is independent of infrastructure details, making the system testable and adaptable to different message brokers or storage backends.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  API Router  │  │   Health     │  │   Metrics    │     │
│  │  /jobs       │  │   /health    │  │   /metrics   │     │
│  │  /status     │  │   /ready     │  │              │     │
│  └──────┬───────┘  └──────────────┘  └──────────────┘     │
│         │                                                    │
│  ┌──────▼──────────────────────────────────────────┐       │
│  │         Workflow Orchestration Service          │       │
│  │  - Job submission                                │       │
│  │  - Status queries                                │       │
│  │  - Workflow coordination                         │       │
│  └──────┬──────────────────────────────────────────┘       │
│         │                                                    │
│  ┌──────▼──────────────────────────────────────────┐       │
│  │           Workflow Engine (Core)                 │       │
│  │  - DAG execution                                 │       │
│  │  - State transitions                             │       │
│  │  - Event routing                                 │       │
│  │  - Completion detection                          │       │
│  └──┬────────────────────────────────────────┬─────┘       │
│     │                                         │              │
│  ┌──▼──────────────┐              ┌──────────▼─────┐       │
│  │   MQ Manager    │              │ State Manager  │       │
│  │  - Connection   │              │  - Context ops │       │
│  │  - Publishing   │              │  - Persistence │       │
│  │  - Consuming    │              │                │       │
│  └──┬──────────────┘              └────────┬───────┘       │
│     │                                      │                │
└─────┼──────────────────────────────────────┼────────────────┘
      │                                      │
┌─────▼──────────┐              ┌───────────▼────────┐
│   RabbitMQ     │              │  MinIO Storage     │
│  - CMD Exchange│              │  - Claim Check     │
│  - EVT Exchange│              │  - State Context   │
└────────────────┘              └────────────────────┘
```

### Component Interaction Flow

1. **Job Submission**: Client → API Router → Orchestration Service → Workflow Engine → State Manager + MQ Manager
2. **Event Processing**: RabbitMQ → MQ Manager → Workflow Engine → State Manager + MQ Manager (next command)
3. **Status Query**: Client → API Router → Orchestration Service → State Manager → Response

### Directory Structure

```
nexus/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry point
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py              # API endpoint definitions
│   │   └── dependencies.py        # Dependency injection
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py              # Configuration management
│   │   ├── logging.py             # Structured logging setup
│   │   └── lifecycle.py           # Startup/shutdown handlers
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── orchestrator.py        # Core workflow engine
│   │   ├── workflows.py           # Workflow definitions
│   │   ├── state_machine.py       # State transition logic
│   │   └── handlers.py            # Event handlers
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── mq_manager.py          # RabbitMQ operations
│   │   ├── storage.py             # Storage abstraction
│   │   └── metrics.py             # Metrics collection
│   ├── models/
│   │   ├── __init__.py
│   │   ├── messages.py            # Message protocol models
│   │   ├── api_models.py          # API request/response models
│   │   ├── workflow_models.py     # Workflow configuration models
│   │   └── state_models.py        # State context models
│   └── services/
│       ├── __init__.py
│       ├── job_service.py         # Job submission logic
│       ├── status_service.py      # Status query logic
│       └── report_service.py      # Report generation logic
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── config/
│   └── workflows.yaml             # Workflow definitions
├── requirements.txt
├── Dockerfile
└── README.md
```

## Components and Interfaces

### 1. API Layer (app/api/)

#### routes.py

```python
from fastapi import APIRouter, Depends, HTTPException
from app.models.api_models import JobSubmitRequest, JobSubmitResponse, JobStatusResponse
from app.services.job_service import JobService
from app.services.status_service import StatusService

router = APIRouter(prefix="/api/v1")

@router.post("/jobs", response_model=JobSubmitResponse)
async def submit_job(
    request: JobSubmitRequest,
    job_service: JobService = Depends()
) -> JobSubmitResponse:
    """Submit a new orchestration job"""
    pass

@router.get("/jobs/{trace_id}", response_model=JobStatusResponse)
async def get_job_status(
    trace_id: str,
    status_service: StatusService = Depends()
) -> JobStatusResponse:
    """Query job status by trace ID"""
    pass

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@router.get("/ready")
async def readiness_check(
    mq_manager: MQManager = Depends(),
    storage: StorageBackend = Depends()
):
    """Readiness check with dependency health"""
    pass
```

### 2. Core Configuration (app/core/)

#### config.py

```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # RabbitMQ Configuration
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    cmd_exchange: str = "nexus.cmd.exchange"
    evt_exchange: str = "nexus.evt.exchange"
    dlx_exchange: str = "nexus.dlx.exchange"

    # MinIO Configuration
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "papers"
    minio_secure: bool = False
    storage_prefix: str = "claimcheck/"

    # Service Configuration
    service_name: str = "nexus"
    log_level: str = "INFO"
    max_concurrent_jobs: int = 100
    shutdown_timeout: int = 30

    # Workflow Configuration
    workflow_config_path: str = "config/workflows.yaml"

    class Config:
        env_file = ".env"
```

### 3. Workflow Engine (app/engine/)

#### orchestrator.py

```python
from typing import Dict, Any, Optional
from app.models.messages import MessagePackage, EventPayload
from app.models.state_models import JobContext
from app.engine.workflows import WorkflowRegistry
from app.infrastructure.mq_manager import MQManager
from app.infrastructure.storage import StateManager

class WorkflowOrchestrator:
    """Core orchestration engine for DAG execution"""

    def __init__(
        self,
        workflow_registry: WorkflowRegistry,
        mq_manager: MQManager,
        state_manager: StateManager
    ):
        self.workflows = workflow_registry
        self.mq = mq_manager
        self.state = state_manager

    async def submit_job(self, task_type: str, initial_data: Dict[str, Any]) -> str:
        """
        Submit a new job and trigger the first workflow stage
        Returns: trace_id
        """
        pass

    async def handle_event(self, message: MessagePackage) -> None:
        """
        Process an event from a tool service and trigger next stage
        """
        pass

    async def get_job_status(self, trace_id: str) -> Optional[JobContext]:
        """
        Retrieve current job status
        """
        pass

    def _determine_next_stage(
        self,
        task_type: str,
        current_stage: str,
        event_status: str
    ) -> Optional[str]:
        """
        Determine the next workflow stage based on current state
        """
        pass
```

#### workflows.py

```python
from typing import Dict, List, Optional
from pydantic import BaseModel
from enum import Enum

class StageType(str, Enum):
    SINGLE = "single"
    FAN_OUT = "fan_out"
    FAN_IN = "fan_in"

class WorkflowStage(BaseModel):
    name: str
    stage_type: StageType
    command_routing_key: str
    success_event: str
    failure_event: str
    next_stage: Optional[str] = None
    filter_function: Optional[str] = None  # For fan-out filtering

class WorkflowDefinition(BaseModel):
    name: str
    task_type: str
    stages: List[WorkflowStage]
    initial_stage: str

class WorkflowRegistry:
    """Registry for workflow definitions"""

    def __init__(self):
        self._workflows: Dict[str, WorkflowDefinition] = {}

    def register(self, workflow: WorkflowDefinition) -> None:
        """Register a workflow definition"""
        pass

    def get_workflow(self, task_type: str) -> Optional[WorkflowDefinition]:
        """Retrieve workflow by task type"""
        pass

    def get_stage(self, task_type: str, stage_name: str) -> Optional[WorkflowStage]:
        """Get specific stage from workflow"""
        pass

    @classmethod
    def from_yaml(cls, config_path: str) -> "WorkflowRegistry":
        """Load workflows from YAML configuration"""
        pass
```

#### handlers.py

```python
from typing import Protocol, Dict, Any
from app.models.messages import MessagePackage
from app.models.state_models import JobContext

class EventHandler(Protocol):
    """Protocol for event handlers"""

    async def handle(
        self,
        message: MessagePackage,
        context: JobContext
    ) -> None:
        """Handle a specific event type"""
        ...

class DiscoveryFinishedHandler:
    """Handler for discovery completion events"""

    async def handle(self, message: MessagePackage, context: JobContext) -> None:
        """
        Process discovery results and fan-out to downloaders
        - Filter papers with PDF candidates
        - Create work keys
        - Trigger parallel downloads
        """
        pass

class DownloaderFinishedHandler:
    """Handler for downloader completion events"""

    async def handle(self, message: MessagePackage, context: JobContext) -> None:
        """Trigger parser for downloaded paper"""
        pass

class ParserFinishedHandler:
    """Handler for parser completion events"""

    async def handle(self, message: MessagePackage, context: JobContext) -> None:
        """Trigger indexer for parsed paper"""
        pass

class IndexerFinishedHandler:
    """Handler for indexer completion events"""

    async def handle(self, message: MessagePackage, context: JobContext) -> None:
        """
        Record completion and check for job finalization
        - Update completed work keys
        - Check if all work is done
        - Trigger report generation if complete
        """
        pass

class FailureHandler:
    """Handler for failure events"""

    async def handle(self, message: MessagePackage, context: JobContext) -> None:
        """
        Handle task failures
        - Record failure details
        - Determine if failure is global or partial
        - Continue or halt workflow
        """
        pass
```

### 4. Infrastructure Layer (app/infrastructure/)

#### mq_manager.py

```python
import aio_pika
from aio_pika import ExchangeType, DeliveryMode, Message
from typing import Optional
from app.models.messages import MessagePackage, MsgHeader, CommandPayload

class MQManager:
    """Manages RabbitMQ connections and operations"""

    def __init__(self, config: Settings):
        self.config = config
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.cmd_exchange: Optional[aio_pika.Exchange] = None
        self.evt_exchange: Optional[aio_pika.Exchange] = None

    async def connect(self) -> None:
        """Establish robust connection to RabbitMQ"""
        pass

    async def disconnect(self) -> None:
        """Gracefully close RabbitMQ connection"""
        pass

    async def publish_command(
        self,
        routing_key: str,
        trace_id: str,
        task_type: str,
        input_key: str
    ) -> None:
        """Publish a command message to tool service"""
        pass

    async def start_consuming(
        self,
        queue_name: str,
        callback: Callable
    ) -> None:
        """Start consuming events from queue"""
        pass

    async def is_healthy(self) -> bool:
        """Check if RabbitMQ connection is healthy"""
        pass
```

#### storage.py

```python
from typing import Any, Optional, Dict
from abc import ABC, abstractmethod

class StorageBackend(ABC):
    """Abstract storage interface"""

    @abstractmethod
    async def save(self, key: str, data: Any) -> None:
        """Save data with key"""
        pass

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Retrieve data by key"""
        pass

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Check storage health"""
        pass

class MinIOStorage(StorageBackend):
    """MinIO implementation of storage backend"""

    def __init__(self, config: Settings):
        self.config = config
        # Initialize MinIO client

    async def save(self, key: str, data: Any) -> None:
        """Save to MinIO with claim-check encoding"""
        pass

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve from MinIO with decoding"""
        pass

class StateManager:
    """Manages job state context operations"""

    def __init__(self, storage: StorageBackend):
        self.storage = storage

    def _ctx_key(self, trace_id: str) -> str:
        """Generate context key for trace ID"""
        return f"task:{trace_id}:ctx"

    async def get_context(self, trace_id: str) -> Dict[str, Any]:
        """Retrieve job context"""
        pass

    async def update_context(self, trace_id: str, **kwargs) -> Dict[str, Any]:
        """Update job context with new fields"""
        pass

    async def save_claim_check(self, key: str, data: Any) -> None:
        """Save data using claim-check pattern"""
        pass

    async def get_claim_check(self, key: str) -> Optional[Any]:
        """Retrieve data using claim-check pattern"""
        pass
```

## Data Models

### Message Protocol Models (app/models/messages.py)

```python
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import time

class MsgHeader(BaseModel):
    trace_id: str
    task_type: str
    sender: str
    timestamp: float = Field(default_factory=time.time)

class CommandPayload(BaseModel):
    task_id: str
    input_key: str
    params: Dict[str, Any] = Field(default_factory=dict)

class EventPayload(BaseModel):
    status: str  # "SUCCESS" or "FAIL"
    output_key: Optional[str] = None
    input_key: Optional[str] = None
    error_msg: Optional[str] = None

class MessagePackage(BaseModel):
    header: MsgHeader
    payload: Dict[str, Any]
```

### API Models (app/models/api_models.py)

```python
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

class JobSubmitRequest(BaseModel):
    task_type: str
    parameters: Dict[str, Any] = Field(default_factory=dict)

class JobSubmitResponse(BaseModel):
    trace_id: str
    status: str = "submitted"
    message: str = "Job submitted successfully"

class WorkItemStatus(BaseModel):
    work_key: str
    status: str  # "pending", "completed", "failed"
    stage: Optional[str] = None
    error_msg: Optional[str] = None

class JobStatusResponse(BaseModel):
    trace_id: str
    task_type: str
    status: str  # "running", "completed", "failed"
    total_work_items: int
    completed_count: int
    failed_count: int
    pending_count: int
    report_key: Optional[str] = None
    failures: List[Dict[str, Any]] = Field(default_factory=list)
```

### State Models (app/models/state_models.py)

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class FailureRecord(BaseModel):
    work_key: str
    stage: str
    routing_key: str
    input_key: str
    error_msg: str

class JobContext(BaseModel):
    trace_id: str
    task_type: str
    init_key: str
    requested_limit: int = 5
    work_keys: List[str] = Field(default_factory=list)
    completed_work_keys: List[str] = Field(default_factory=list)
    failures: List[FailureRecord] = Field(default_factory=list)
    discovery_key: Optional[str] = None
    report_key: Optional[str] = None
    current_stage: str = "init"
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

## Correctness Properties

_A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees._

### Property 1: Trace ID Uniqueness

_For any_ two job submissions, the generated trace IDs should be distinct, ensuring no collision in job tracking.
**Validates: Requirements 1.1**

### Property 2: State Context Persistence Round-Trip

_For any_ job context data structure, saving then retrieving the context should produce an equivalent structure with all fields preserved.
**Validates: Requirements 5.3, 12.1, 12.4**

### Property 3: Work Key Inference Consistency

_For any_ valid work key, transforming it to a downstream key (download/parse/index) and then inferring back should return the original work key.
**Validates: Requirements 11.1, 11.2, 11.3**

### Property 4: Fan-out Completeness

_For any_ discovery result set with N valid papers, the fan-out process should create exactly N work keys and publish exactly N download commands.
**Validates: Requirements 8.1, 8.4, 8.5**

### Property 5: Completion Detection Accuracy

_For any_ job with N work keys, when exactly N items appear in the union of completed and failed sets, the job should be marked as complete.
**Validates: Requirements 9.1, 9.2, 9.3**

### Property 6: Partial Failure Isolation

_For any_ job with multiple work items, a failure in one work item should not prevent other work items from completing successfully.
**Validates: Requirements 7.2, 7.3**

### Property 7: Command Message Structure Validity

_For any_ command published, the message should contain a valid header with trace_id, task_type, sender, and a payload with task_id and input_key.
**Validates: Requirements 3.1, 3.2, 3.3**

### Property 8: Event Processing Idempotency

_For any_ event message, processing it multiple times should produce the same state transitions as processing it once (for idempotent operations).
**Validates: Requirements 4.1, 4.2**

### Property 9: Workflow Stage Progression

_For any_ workflow definition, following the stage transitions from initial_stage should never create a cycle.
**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**

### Property 10: Storage Key Format Consistency

_For any_ trace_id and work index, the generated keys (work_key, download_key, parse_key, index_key) should follow the documented format patterns.
**Validates: Requirements 8.4, 11.1, 11.2**

### Property 11: PDF Candidate Filtering Correctness

_For any_ work object, if it has a PDF URL in best_oa_location, locations, or arXiv landing page, it should pass the PDF candidate filter.
**Validates: Requirements 8.2**

### Property 12: State Update Merge Behavior

_For any_ existing context and new fields, updating the context should preserve all existing fields not present in the update.
**Validates: Requirements 5.2**

### Property 13: Report Generation Completeness

_For any_ completed job, the generated report should include entries for all work keys in the completed_work_keys list.
**Validates: Requirements 10.1, 10.2, 10.4**

### Property 14: Configuration Environment Variable Parsing

_For any_ boolean environment variable with values "true", "1", "yes", the parser should return True; for "false", "0", "no", it should return False.
**Validates: Requirements 13.4**

### Property 15: Graceful Shutdown Completion

_For any_ in-flight messages at shutdown time, all messages should be acknowledged before connection closure.
**Validates: Requirements 23.2, 23.3**

## Error Handling

### Error Categories

1. **Validation Errors**: Invalid API requests, malformed messages

   - Return HTTP 400 with detailed error messages
   - Log validation failures with request context

2. **Infrastructure Errors**: RabbitMQ connection failures, storage unavailability

   - Implement exponential backoff retry (max 3 attempts)
   - Return HTTP 503 for readiness checks
   - Trigger alerts for persistent failures

3. **Business Logic Errors**: Missing workflow definitions, invalid state transitions

   - Log error with full context
   - Return HTTP 500 with generic message (hide internals)
   - Record in metrics for monitoring

4. **Partial Failures**: Individual work item failures in fan-out scenarios

   - Record failure in state context
   - Continue processing other items
   - Include in final report

5. **Timeout Errors**: Long-running operations exceeding limits
   - Cancel operation gracefully
   - Clean up resources
   - Return timeout error to client

### Error Recovery Strategies

```python
class RetryConfig(BaseModel):
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0

async def with_retry(
    operation: Callable,
    retry_config: RetryConfig,
    retriable_exceptions: tuple
) -> Any:
    """Execute operation with exponential backoff retry"""
    pass
```

### Dead Letter Queue Handling

- Messages that fail after max retries go to DLQ
- DLQ messages are logged with full context
- Separate monitoring for DLQ depth
- Manual intervention process for DLQ recovery

## Testing Strategy

### Unit Testing

Focus on individual components in isolation:

- **Workflow Engine**: Test stage transitions, completion detection, work key inference
- **State Manager**: Test context updates, merge behavior, persistence
- **MQ Manager**: Test message construction, routing key generation (with mocked connection)
- **Handlers**: Test event processing logic with mocked dependencies
- **API Routes**: Test request validation, response formatting

Tools: pytest, pytest-asyncio, pytest-mock

### Property-Based Testing

Use Hypothesis for property-based tests:

- Generate random trace IDs and verify uniqueness
- Generate random work keys and test inference round-trips
- Generate random context data and test persistence round-trips
- Generate random discovery results and verify fan-out counts
- Generate random completion scenarios and verify detection logic

Configuration: Minimum 100 iterations per property test

### Integration Testing

Test component interactions:

- **API → Service → Engine**: Full job submission flow
- **MQ → Engine → State**: Event processing flow
- **Engine → MQ**: Command publishing flow
- **State → Storage**: Persistence operations

Use test containers for RabbitMQ and MinIO

### End-to-End Testing

Test complete workflows:

- Submit MORNING_REPORT job
- Mock tool service responses
- Verify state transitions
- Verify final report generation

### Performance Testing

- Concurrent job submission (target: 100 concurrent jobs)
- Event processing throughput
- State query latency (target: <100ms)
- Memory usage under load

## Deployment Considerations

### Docker Configuration

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY config/ ./config/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables

Required:

- `RABBITMQ_URL`
- `MINIO_ENDPOINT`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`

Optional (with defaults):

- `LOG_LEVEL=INFO`
- `MAX_CONCURRENT_JOBS=100`
- `SHUTDOWN_TIMEOUT=30`

### Health Checks

- Liveness: `/health` (always returns 200 if process running)
- Readiness: `/ready` (checks RabbitMQ and MinIO connectivity)

### Monitoring

- Prometheus metrics at `/metrics`
- Structured JSON logs to stdout
- Trace context in all logs for correlation

## Migration Strategy

### Phase 1: Create New Structure

- Set up FastAPI application skeleton
- Implement models and interfaces
- Create unit tests

### Phase 2: Implement Core Components

- MQ Manager with connection handling
- State Manager with storage operations
- Workflow Engine with basic orchestration

### Phase 3: Implement Handlers

- Port existing event handling logic
- Implement configurable workflow definitions
- Add property-based tests

### Phase 4: API Layer

- Implement REST endpoints
- Add request validation
- Implement status queries

### Phase 5: Integration & Testing

- Integration tests with test containers
- End-to-end workflow tests
- Performance testing

### Phase 6: Deployment

- Deploy alongside existing service
- Gradual traffic migration
- Monitor and validate
- Decommission old service

## Open Questions

1. Should we support workflow versioning for backward compatibility?
2. What is the desired behavior for job cancellation?
3. Should we implement priority queues for different job types?
4. What metrics are most critical for alerting?
5. Should we support custom workflow definitions via API?
