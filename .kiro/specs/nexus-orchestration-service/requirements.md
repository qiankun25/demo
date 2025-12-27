# Requirements Document

## Introduction

The Nexus Orchestration Service is the central coordination hub for a distributed microservices architecture that processes academic papers through a multi-stage pipeline. The service receives high-level task requests (such as morning report generation), orchestrates downstream tool services (discovery, download, parsing, indexing) via RabbitMQ message queues, maintains task state throughout the workflow lifecycle, and handles partial failures gracefully. The system implements a DAG-based workflow engine with claim-check pattern for large payloads, supports fan-out/fan-in patterns for parallel processing, and provides RESTful APIs for task submission and status queries.

## Glossary

- **Nexus Service**: The orchestration microservice that coordinates all downstream tool services
- **Tool Service**: A specialized microservice that performs a specific function (discovery, download, parsing, indexing, retrieval, translation)
- **DAG (Directed Acyclic Graph)**: A workflow representation where tasks have dependencies and execute in a specific order
- **Trace ID**: A unique identifier (UUID) that tracks a single job request through its entire lifecycle
- **Work Key**: A unique identifier for a single unit of work within a job (e.g., processing one paper)
- **Claim Check Pattern**: A messaging pattern where large payloads are stored externally and only references (keys) are passed in messages
- **Fan-out**: A pattern where one task spawns multiple parallel sub-tasks
- **Fan-in**: A pattern where multiple parallel tasks must complete before proceeding to the next stage
- **Command Exchange**: A RabbitMQ direct exchange for sending task commands to tool services
- **Event Exchange**: A RabbitMQ topic exchange for receiving status events from tool services
- **Message Package**: A standardized message format containing header (trace_id, task_type, sender, timestamp) and payload
- **State Context**: Persistent storage of job state including work keys, completed items, and failures
- **Morning Report**: A specific workflow type that discovers, downloads, parses, and indexes academic papers
- **Storage Backend**: MinIO-based S3-compatible storage for claim-check data persistence
- **Routing Key**: A RabbitMQ message routing identifier (e.g., cmd.discovery.start, evt.parser.finished)
- **FastAPI Application**: The web framework providing RESTful API endpoints
- **Workflow Engine**: The component responsible for DAG execution and state transitions
- **MQ Manager**: The component responsible for RabbitMQ connection and message operations

## Requirements

### Requirement 1: Task Submission API

**User Story:** As an API client, I want to submit orchestration jobs via RESTful endpoints, so that I can trigger complex multi-stage workflows programmatically.

#### Acceptance Criteria

1. WHEN a client sends a POST request to the task submission endpoint with valid task type and parameters THEN the Nexus Service SHALL generate a unique trace ID and return it immediately
2. WHEN the Nexus Service receives a task submission request THEN the Nexus Service SHALL persist the initial payload using the claim-check pattern before triggering downstream services
3. WHEN a task submission request contains invalid parameters THEN the Nexus Service SHALL return an HTTP 400 error with validation details
4. WHEN the Nexus Service successfully accepts a task THEN the Nexus Service SHALL initialize the state context with empty work keys and completed lists
5. WHERE the task type is MORNING_REPORT THEN the Nexus Service SHALL trigger the discovery service as the first workflow step

### Requirement 2: Message Queue Connection Management

**User Story:** As a system operator, I want the orchestration service to maintain reliable RabbitMQ connections, so that message delivery remains consistent even during network disruptions.

#### Acceptance Criteria

1. WHEN the Nexus Service starts THEN the Nexus Service SHALL establish a robust connection to RabbitMQ with automatic reconnection capability
2. WHEN the Nexus Service connects to RabbitMQ THEN the Nexus Service SHALL declare the command exchange as a durable direct exchange
3. WHEN the Nexus Service connects to RabbitMQ THEN the Nexus Service SHALL declare the event exchange as a durable topic exchange
4. WHEN the Nexus Service declares its event listener queue THEN the Nexus Service SHALL bind it to all event routing keys using the pattern "evt.#"
5. IF the RabbitMQ connection is lost THEN the Nexus Service SHALL automatically attempt reconnection without crashing

### Requirement 3: Command Publishing

**User Story:** As the orchestration engine, I want to publish commands to downstream tool services, so that I can trigger the next stage of workflow execution.

#### Acceptance Criteria

1. WHEN the orchestration engine needs to trigger a tool service THEN the Nexus Service SHALL construct a message package with header and command payload
2. WHEN publishing a command message THEN the Nexus Service SHALL include the trace ID, task type, and sender in the message header
3. WHEN publishing a command message THEN the Nexus Service SHALL include the task ID and input key in the command payload
4. WHEN publishing a command message THEN the Nexus Service SHALL set the delivery mode to persistent to ensure message durability
5. WHEN a command is successfully published THEN the Nexus Service SHALL log the routing key and trace ID for observability

### Requirement 4: Event Consumption and Processing

**User Story:** As the orchestration engine, I want to consume events from tool services, so that I can react to task completions and failures.

#### Acceptance Criteria

1. WHEN the Nexus Service receives an event message THEN the Nexus Service SHALL deserialize it into a message package structure
2. WHEN processing an event message THEN the Nexus Service SHALL extract the trace ID, routing key, and status from the message
3. WHEN an event indicates task failure THEN the Nexus Service SHALL log the error message and sender information
4. WHEN processing an event THEN the Nexus Service SHALL acknowledge the message to RabbitMQ after successful processing
5. IF event processing fails THEN the Nexus Service SHALL reject the message and allow RabbitMQ retry mechanisms to handle it

### Requirement 5: State Context Management

**User Story:** As the orchestration engine, I want to maintain persistent state for each job, so that I can track progress and make workflow decisions.

#### Acceptance Criteria

1. WHEN a new job is submitted THEN the Nexus Service SHALL create a state context with the trace ID as the key
2. WHEN updating state context THEN the Nexus Service SHALL merge new fields with existing context without overwriting unrelated data
3. WHEN storing state context THEN the Nexus Service SHALL persist it to the storage backend using the claim-check pattern
4. WHEN retrieving state context THEN the Nexus Service SHALL handle missing or corrupted data gracefully by returning empty dictionaries
5. WHEN state context is updated THEN the Nexus Service SHALL validate that the context structure is a dictionary before merging

### Requirement 6: DAG Workflow Orchestration for Morning Report

**User Story:** As the orchestration engine, I want to execute the morning report workflow as a directed acyclic graph, so that papers flow through discovery, download, parsing, and indexing stages.

#### Acceptance Criteria

1. WHEN the discovery service completes THEN the Nexus Service SHALL extract the results and schedule download tasks for papers with valid PDF candidates
2. WHEN scheduling download tasks THEN the Nexus Service SHALL create individual work keys for each paper and fan-out commands to the downloader service
3. WHEN the downloader service completes for a paper THEN the Nexus Service SHALL trigger the parser service with the download output key
4. WHEN the parser service completes for a paper THEN the Nexus Service SHALL trigger the indexer service with the parser output key
5. WHEN the indexer service completes for a paper THEN the Nexus Service SHALL record the work key as completed in the state context

### Requirement 7: Partial Failure Handling

**User Story:** As a system operator, I want the orchestration service to handle partial failures gracefully, so that one paper's failure does not block the entire job.

#### Acceptance Criteria

1. WHEN a tool service reports a failure event THEN the Nexus Service SHALL extract the error message and input key from the event payload
2. IF a failure occurs after fan-out has begun THEN the Nexus Service SHALL record the failure in the state context with work key, stage, and error details
3. WHEN recording a failure THEN the Nexus Service SHALL continue processing other papers without aborting the entire job
4. WHEN a failure occurs before fan-out THEN the Nexus Service SHALL treat it as a global failure and halt the job
5. WHEN determining job completion THEN the Nexus Service SHALL count both completed and failed work keys toward the total

### Requirement 8: Fan-out Work Scheduling

**User Story:** As the orchestration engine, I want to schedule parallel work items after discovery, so that multiple papers can be processed concurrently.

#### Acceptance Criteria

1. WHEN discovery results are received THEN the Nexus Service SHALL filter papers to include only those with valid PDF candidates
2. WHEN filtering papers THEN the Nexus Service SHALL check for PDF URLs in best_oa_location, locations array, and arXiv landing pages
3. WHEN scheduling work items THEN the Nexus Service SHALL respect the requested limit parameter from the initial job submission
4. WHEN creating work items THEN the Nexus Service SHALL generate sequential work keys in the format "task:{trace_id}:work:{index}"
5. WHEN persisting work items THEN the Nexus Service SHALL store the work metadata with the work key before sending commands

### Requirement 9: Job Completion Detection

**User Story:** As the orchestration engine, I want to detect when all work items have completed or failed, so that I can finalize the job and generate the report.

#### Acceptance Criteria

1. WHEN a work item completes or fails THEN the Nexus Service SHALL check if all scheduled work keys have been accounted for
2. WHEN checking completion status THEN the Nexus Service SHALL combine completed work keys and failed work keys into a done set
3. WHEN all work keys are in the done set and no report exists THEN the Nexus Service SHALL trigger report generation
4. WHEN triggering report generation THEN the Nexus Service SHALL prevent duplicate report creation by checking for existing report keys
5. WHEN a report is generated THEN the Nexus Service SHALL update the state context with the report key

### Requirement 10: Morning Report Generation

**User Story:** As a job requester, I want to receive a comprehensive report of all processed papers, so that I can review the results and access indexed content.

#### Acceptance Criteria

1. WHEN generating a morning report THEN the Nexus Service SHALL retrieve all completed work keys from the state context
2. WHEN building the report THEN the Nexus Service SHALL fetch download, parse, and index payloads for each completed paper
3. WHEN a completed work key has missing downstream payloads THEN the Nexus Service SHALL raise an error indicating data inconsistency
4. WHEN constructing paper entries THEN the Nexus Service SHALL include paper metadata, summary, index information, and all associated keys
5. WHEN the report is complete THEN the Nexus Service SHALL persist it to storage with a key in the format "data:morning_report:{trace_id}"

### Requirement 11: Work Key Inference

**User Story:** As the orchestration engine, I want to infer work keys from various downstream keys, so that I can track which paper a failure or completion event refers to.

#### Acceptance Criteria

1. WHEN receiving a key that starts with "task:{trace_id}:work:" THEN the Nexus Service SHALL return it as the work key directly
2. WHEN receiving a key containing "data:download:" THEN the Nexus Service SHALL extract the portion after the marker as the work key
3. WHEN receiving a download key in the format "data:download:{work_key}" THEN the Nexus Service SHALL strip the prefix to obtain the work key
4. WHEN a key does not match any known pattern THEN the Nexus Service SHALL raise a ValueError with the problematic key
5. WHEN inferring work keys THEN the Nexus Service SHALL handle null or empty string inputs by raising appropriate errors

### Requirement 12: Claim Check Data Persistence

**User Story:** As the orchestration engine, I want to store large payloads externally, so that message queue messages remain small and efficient.

#### Acceptance Criteria

1. WHEN storing data via claim check THEN the Nexus Service SHALL serialize the data as JSON when possible for readability
2. WHEN JSON serialization fails THEN the Nexus Service SHALL fall back to pickle serialization for Python objects
3. WHEN storing binary data THEN the Nexus Service SHALL store it directly without additional encoding
4. WHEN retrieving data via claim check THEN the Nexus Service SHALL detect the encoding format and deserialize appropriately
5. WHEN a claim check key does not exist THEN the Nexus Service SHALL return None rather than raising an error

### Requirement 13: Service Configuration Management

**User Story:** As a system operator, I want to configure the service via environment variables, so that I can deploy to different environments without code changes.

#### Acceptance Criteria

1. WHEN the Nexus Service starts THEN the Nexus Service SHALL read RabbitMQ connection URL from environment variables with sensible defaults
2. WHEN the Nexus Service starts THEN the Nexus Service SHALL read MinIO connection parameters from environment variables
3. WHEN environment variables are missing THEN the Nexus Service SHALL use default values suitable for local development
4. WHEN boolean environment variables are provided THEN the Nexus Service SHALL parse values like "true", "1", "yes" as true
5. WHEN the storage backend is initialized THEN the Nexus Service SHALL ensure the configured bucket exists before operations

### Requirement 14: Observability and Logging

**User Story:** As a system operator, I want comprehensive logging throughout the orchestration process, so that I can debug issues and monitor system health.

#### Acceptance Criteria

1. WHEN a new job is received THEN the Nexus Service SHALL log the task type and trace ID
2. WHEN sending a command THEN the Nexus Service SHALL log the routing key and trace ID
3. WHEN receiving an event THEN the Nexus Service SHALL log the routing key and trace ID
4. WHEN a task fails THEN the Nexus Service SHALL log the error message, sender, and trace ID
5. WHEN a job completes THEN the Nexus Service SHALL log the completion status and report key

### Requirement 15: Modular Architecture with Separation of Concerns

**User Story:** As a developer, I want the service to follow clean architecture principles with separated concerns, so that the codebase is maintainable and testable.

#### Acceptance Criteria

1. WHEN organizing the codebase THEN the Nexus Service SHALL separate API routing, business logic, and infrastructure concerns into distinct modules
2. WHEN implementing RabbitMQ operations THEN the Nexus Service SHALL encapsulate connection management and message publishing in a dedicated MQ Manager component
3. WHEN implementing workflow logic THEN the Nexus Service SHALL encapsulate DAG execution and state transitions in a dedicated Workflow Engine component
4. WHEN defining data structures THEN the Nexus Service SHALL use Pydantic models for all message protocols and API request/response schemas
5. WHEN implementing storage operations THEN the Nexus Service SHALL abstract storage backend details behind a consistent interface

### Requirement 16: FastAPI Application Structure

**User Story:** As a developer, I want the service to follow FastAPI best practices, so that the application is scalable and follows industry standards.

#### Acceptance Criteria

1. WHEN structuring the application THEN the Nexus Service SHALL organize code into app/api, app/core, app/engine, app/models, and app/services directories
2. WHEN defining API endpoints THEN the Nexus Service SHALL use FastAPI routers with proper dependency injection
3. WHEN the application starts THEN the Nexus Service SHALL initialize RabbitMQ connections and event consumers as background tasks
4. WHEN the application shuts down THEN the Nexus Service SHALL gracefully close RabbitMQ connections and complete in-flight message processing
5. WHEN handling requests THEN the Nexus Service SHALL leverage FastAPI's async capabilities for non-blocking operations

### Requirement 17: Workflow Template Configuration

**User Story:** As a system architect, I want workflow definitions to be configurable rather than hardcoded, so that new workflow types can be added without code changes.

#### Acceptance Criteria

1. WHEN defining a workflow THEN the Nexus Service SHALL represent it as a configuration structure with stages and transitions
2. WHEN processing an event THEN the Nexus Service SHALL look up the next stage from the workflow configuration rather than using hardcoded conditionals
3. WHEN a workflow stage completes THEN the Nexus Service SHALL determine the next action based on the workflow template
4. WHEN multiple workflow types exist THEN the Nexus Service SHALL select the appropriate template based on the task type
5. WHEN a workflow requires fan-out THEN the Nexus Service SHALL support parallel execution patterns in the configuration

### Requirement 18: Error Recovery and Retry Mechanisms

**User Story:** As a system operator, I want the service to implement retry logic for transient failures, so that temporary issues do not cause permanent job failures.

#### Acceptance Criteria

1. WHEN a transient error occurs during message publishing THEN the Nexus Service SHALL retry the operation with exponential backoff
2. WHEN a storage operation fails due to network issues THEN the Nexus Service SHALL retry the operation up to a configured maximum
3. WHEN retry attempts are exhausted THEN the Nexus Service SHALL log the failure and propagate the error appropriately
4. WHEN processing events THEN the Nexus Service SHALL distinguish between retriable and non-retriable errors
5. WHEN a message cannot be processed THEN the Nexus Service SHALL send it to a dead letter queue after maximum retries

### Requirement 19: Job Status Query API

**User Story:** As an API client, I want to query the status of submitted jobs, so that I can monitor progress and retrieve results.

#### Acceptance Criteria

1. WHEN a client sends a GET request with a trace ID THEN the Nexus Service SHALL return the current job status and progress information
2. WHEN retrieving job status THEN the Nexus Service SHALL include the count of completed, failed, and pending work items
3. WHEN a job has completed THEN the Nexus Service SHALL include the report key in the status response
4. WHEN a trace ID does not exist THEN the Nexus Service SHALL return an HTTP 404 error
5. WHEN retrieving job status THEN the Nexus Service SHALL return the response within 100 milliseconds for cached state

### Requirement 20: Concurrent Job Execution

**User Story:** As the orchestration service, I want to handle multiple jobs concurrently, so that the system can process high volumes of requests.

#### Acceptance Criteria

1. WHEN multiple jobs are submitted simultaneously THEN the Nexus Service SHALL process them concurrently without blocking
2. WHEN processing events from different jobs THEN the Nexus Service SHALL maintain separate state contexts for each trace ID
3. WHEN updating state for one job THEN the Nexus Service SHALL not interfere with state updates for other jobs
4. WHEN the system is under load THEN the Nexus Service SHALL maintain consistent performance up to 100 concurrent jobs
5. WHEN processing events THEN the Nexus Service SHALL use async/await patterns to avoid blocking the event loop

### Requirement 21: Health Check and Readiness Endpoints

**User Story:** As a platform operator, I want health check endpoints, so that I can monitor service availability and integrate with orchestration platforms.

#### Acceptance Criteria

1. WHEN a client sends a GET request to the health endpoint THEN the Nexus Service SHALL return HTTP 200 if the service is running
2. WHEN a client sends a GET request to the readiness endpoint THEN the Nexus Service SHALL return HTTP 200 if RabbitMQ and storage connections are healthy
3. WHEN RabbitMQ connection is unavailable THEN the Nexus Service SHALL return HTTP 503 from the readiness endpoint
4. WHEN storage backend is unavailable THEN the Nexus Service SHALL return HTTP 503 from the readiness endpoint
5. WHEN health checks are performed THEN the Nexus Service SHALL complete the check within 1 second

### Requirement 22: Structured Logging with Trace Context

**User Story:** As a system operator, I want structured logs with trace context, so that I can correlate logs across distributed services.

#### Acceptance Criteria

1. WHEN logging any operation THEN the Nexus Service SHALL include the trace ID in the log entry
2. WHEN logging messages THEN the Nexus Service SHALL use structured JSON format with consistent field names
3. WHEN logging errors THEN the Nexus Service SHALL include stack traces and error context
4. WHEN logging at different levels THEN the Nexus Service SHALL support configurable log levels via environment variables
5. WHEN processing events THEN the Nexus Service SHALL log the full message routing path for debugging

### Requirement 23: Graceful Shutdown

**User Story:** As a platform operator, I want the service to shut down gracefully, so that in-flight jobs are not lost during deployments.

#### Acceptance Criteria

1. WHEN the service receives a shutdown signal THEN the Nexus Service SHALL stop accepting new job submissions
2. WHEN shutting down THEN the Nexus Service SHALL wait for in-flight event processing to complete
3. WHEN shutting down THEN the Nexus Service SHALL close RabbitMQ connections after all messages are acknowledged
4. WHEN shutting down THEN the Nexus Service SHALL complete the shutdown within 30 seconds
5. IF shutdown exceeds the timeout THEN the Nexus Service SHALL force close connections and exit

### Requirement 24: Metrics and Observability

**User Story:** As a system operator, I want the service to expose metrics, so that I can monitor performance and set up alerts.

#### Acceptance Criteria

1. WHEN processing jobs THEN the Nexus Service SHALL track the count of submitted, completed, and failed jobs
2. WHEN processing events THEN the Nexus Service SHALL track event processing latency
3. WHEN publishing commands THEN the Nexus Service SHALL track command publishing latency
4. WHEN the metrics endpoint is queried THEN the Nexus Service SHALL return metrics in Prometheus format
5. WHEN tracking metrics THEN the Nexus Service SHALL include labels for task type and workflow stage
