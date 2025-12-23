I will implement the event-driven microservice architecture using **Python** and **aio-pika** (as requested for high concurrency).

The implementation will be divided into three independent modules located in separate directories, ensuring strict decoupling between the Orchestrator (Nexus) and the Executors (Tools).

### Directory Structure
```text
demo/
├── shared/                 # Common contracts (Shared by all)
│   ├── __init__.py
│   └── common.py           # Configs, Pydantic Models, MockStorage
├── nexus_service/          # Orchestration Layer
│   ├── __init__.py
│   └── core.py             # Nexus logic (DAG State Machine)
├── tool_services/          # Execution Layer
    ├── sdk/                # Base SDK for tools
    │   ├── __init__.py
    │   └── base.py         # BaseToolService (aio-pika implementation)
    ├── impl/               # Concrete Tool Implementations
    │   ├── __init__.py
    │   └── tools.py        # Downloader, Parser, Indexer
    └── run_tools.py        # Entry point to run tools
```

### Implementation Details

1.  **Shared Module (`shared/common.py`)**
    *   Define `RabbitConfig` (Exchanges: `nexus.cmd.exchange`, `nexus.evt.exchange`).
    *   Define Pydantic models: `MsgHeader`, `CommandPayload`, `EventPayload`, `MessagePackage`.
    *   Implement `MockStorage` to simulate Redis/MinIO (Claim Check pattern).

2.  **Tool SDK (`tool_services/sdk/base.py`)**
    *   Implement `BaseToolService` using `aio_pika`.
    *   **Features**:
        *   Async connection management.
        *   Automatic Exchange/Queue declaration and binding.
        *   Standardized `on_message` handler: Deserialize -> `do_work` -> Publish Event -> ACK.
        *   Error handling: Catches exceptions and publishes `FAIL` events.

3.  **Nexus Service (`nexus_service/core.py`)**
    *   Implement `NexusService` using `aio_pika`.
    *   **Features**:
        *   Listens to `evt.#` (Wildcard topic).
        *   **DAG Logic**:
            *   `evt.downloader.finished` -> Trigger `parser`.
            *   `evt.parser.finished` -> Trigger `indexer`.
        *   `submit_job`: API simulation to start the workflow.

4.  **Tool Implementations (`tool_services/impl/tools.py`)**
    *   Concrete classes for `Downloader`, `Parser`, `Indexer`.
    *   Focus purely on business logic (simulated with `asyncio.sleep`).

5.  **Verification**
    *   Create a runner script `run_demo.py` that:
        1.  Starts RabbitMQ (assumed running or mocked if environment restricts). *Note: Since I cannot start a real RabbitMQ server in this environment, I will write the code assuming a standard local RabbitMQ instance is available. If unavailable, I will provide the code ready for deployment.*
        2.  Launches Nexus and Tools in background async tasks.
        3.  Simulates a job submission.
        4.  Prints logs to console to verify the flow.

### Dependencies
I will install `aio-pika`, `pydantic` if not present.
(Note: I will check for installed packages first).
