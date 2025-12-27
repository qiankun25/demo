# Implementation Plan

- [x] 1. Set up project structure and core configuration

  - Create nexus/ directory with FastAPI application skeleton
  - Set up app/api/, app/core/, app/engine/, app/infrastructure/, app/models/, app/services/ directories
  - Create **init**.py files for all packages
  - Set up requirements.txt with FastAPI, aio-pika, pydantic, minio dependencies
  - _Requirements: 15.1, 16.1_

- [x] 1.1 Implement core configuration management

  - Create app/core/config.py with Settings class using pydantic-settings
  - Add environment variable definitions for RabbitMQ, MinIO, and service configuration
  - Implement configuration loading with defaults for local development
  - _Requirements: 13.1, 13.2, 13.3_

- [ ]\* 1.2 Write property test for boolean environment variable parsing

  - **Property 14: Boolean environment variable parsing**
  - **Validates: Requirements 13.4**

- [x] 1.3 Implement structured logging setup

  - Create app/core/logging.py with JSON formatter
  - Add trace context injection for all log entries
  - Configure log levels from environment variables
  - _Requirements: 22.1, 22.2, 22.4_

- [x] 2. Implement data models and message protocols

  - Create app/models/messages.py with MsgHeader, CommandPayload, EventPayload, MessagePackage
  - Create app/models/api_models.py with JobSubmitRequest, JobSubmitResponse, JobStatusResponse
  - Create app/models/state_models.py with JobContext, FailureRecord
  - Create app/models/workflow_models.py with WorkflowDefinition, WorkflowStage, StageType
  - _Requirements: 15.4_

- [ ]\* 2.1 Write property test for message package construction

  - **Property 7: Command message structure validity**
  - **Validates: Requirements 3.1, 3.2, 3.3**

- [ ]\* 2.2 Write property test for state context merge behavior

  - **Property 12: State update merge behavior**
  - **Validates: Requirements 5.2**

- [ ] 3. Implement storage backend and state manager

  - Create app/infrastructure/storage.py with StorageBackend abstract class
  - Implement MinIOStorage with claim-check encoding/decoding
  - Implement StateManager with context operations (get_context, update_context)
  - Add health check method for storage connectivity
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 13.5_

- [ ]\* 3.1 Write property test for claim-check round-trip

  - **Property 2: State context persistence round-trip**
  - **Validates: Requirements 5.3, 12.1, 12.4**

- [ ]\* 3.2 Write unit tests for storage operations

  - Test JSON serialization preference
  - Test pickle fallback for non-JSON data
  - Test binary data handling
  - Test missing key returns None
  - _Requirements: 12.1, 12.2, 12.3, 12.5_

- [x] 4. Implement RabbitMQ manager

  - Create app/infrastructure/mq_manager.py with MQManager class
  - Implement connect() with aio_pika.connect_robust for auto-reconnection
  - Implement exchange declarations (CMD_EXCHANGE as direct, EVT_EXCHANGE as topic)
  - Implement publish_command() with persistent delivery mode
  - Implement start_consuming() for event queue
  - Add is_healthy() method for connection checks
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.4_

- [ ]\* 4.1 Write property test for command publishing

  - **Property 7: Command message structure validity**
  - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**

- [ ]\* 4.2 Write unit tests for MQ manager

  - Test connection establishment with mocked aio_pika
  - Test exchange declarations
  - Test message publishing with correct routing keys
  - Test graceful disconnection
  - _Requirements: 2.1, 2.2, 2.3, 3.5_

- [x] 5. Implement workflow registry and definitions

  - Create app/engine/workflows.py with WorkflowRegistry class
  - Implement register() and get_workflow() methods
  - Implement from_yaml() class method to load workflow configurations
  - Create config/workflows.yaml with MORNING_REPORT workflow definition
  - _Requirements: 17.1, 17.2, 17.4_

- [ ]\* 5.1 Write unit tests for workflow registry

  - Test workflow registration
  - Test workflow retrieval by task type
  - Test stage lookup
  - Test YAML loading
  - _Requirements: 17.1, 17.4_

- [x] 6. Implement work key utilities

  - Create app/engine/utils.py with work key inference functions
  - Implement infer_work_key() to extract work keys from various key formats
  - Implement work_has_pdf_candidate() to filter papers
  - Implement generate_work_key() for sequential key generation
  - _Requirements: 11.1, 11.2, 11.3, 11.5, 8.2, 8.4_

- [x]* 6.1 Write property test for work key inference round-trip

  - **Property 3: Work key inference consistency**
  - **Validates: Requirements 11.1, 11.2, 11.3**

- [x]* 6.2 Write property test for PDF candidate filtering

  - **Property 11: PDF candidate filtering correctness**
  - **Validates: Requirements 8.2**

- [x]* 6.3 Write property test for work key format

  - **Property 10: Storage key format consistency**
  - **Validates: Requirements 8.4**

- [x] 7. Implement event handlers

  - Create app/engine/handlers.py with EventHandler protocol
  - Implement DiscoveryFinishedHandler for fan-out logic
  - Implement DownloaderFinishedHandler for parser triggering
  - Implement ParserFinishedHandler for indexer triggering
  - Implement IndexerFinishedHandler for completion tracking
  - Implement FailureHandler for partial failure handling
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 7.3_

- [x]* 7.1 Write property test for fan-out completeness

  - **Property 4: Fan-out completeness**
  - **Validates: Requirements 8.1, 8.4, 8.5**

- [x]* 7.2 Write property test for partial failure isolation

  - **Property 6: Partial failure isolation**
  - **Validates: Requirements 7.2, 7.3**

- [x]* 7.3 Write unit tests for event handlers

  - Test DiscoveryFinishedHandler with various result sets
  - Test DownloaderFinishedHandler command publishing
  - Test ParserFinishedHandler command publishing
  - Test IndexerFinishedHandler completion recording
  - Test FailureHandler with global and partial failures
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 7.3, 7.4_

- [x] 8. Implement workflow orchestrator

  - Create app/engine/orchestrator.py with WorkflowOrchestrator class
  - Implement submit_job() to initialize job and trigger first stage
  - Implement handle_event() to process events and determine next stage
  - Implement get_job_status() to retrieve current job state
  - Implement \_determine_next_stage() using workflow registry
  - Implement \_check_completion() to detect job finalization
  - _Requirements: 1.1, 1.2, 1.4, 1.5, 4.1, 4.2, 6.1, 6.2, 6.3, 6.4, 6.5, 9.1, 9.2, 9.3_

- [x]* 8.1 Write property test for trace ID uniqueness

  - **Property 1: Trace ID uniqueness**
  - **Validates: Requirements 1.1**

- [x]* 8.2 Write property test for completion detection

  - **Property 5: Completion detection accuracy**
  - **Validates: Requirements 9.1, 9.2, 9.3**

- [x]* 8.3 Write property test for workflow stage progression

  - **Property 9: Workflow stage progression**
  - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**

- [x]* 8.4 Write unit tests for orchestrator

  - Test job submission flow
  - Test event routing to correct handlers
  - Test state transitions
  - Test completion detection logic
  - _Requirements: 1.1, 1.2, 1.4, 4.1, 4.2, 9.1, 9.2, 9.3_

- [x] 9. Implement report generation service

  - Create app/services/report_service.py with ReportService class
  - Implement build_morning_report() to aggregate paper data
  - Implement \_fetch_paper_payloads() to retrieve download/parse/index data
  - Implement \_construct_paper_entry() to format paper information
  - Add error handling for missing payloads
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x]* 9.1 Write property test for report generation completeness

  - **Property 13: Report generation completeness**
  - **Validates: Requirements 10.1, 10.2, 10.4**

- [x]* 9.2 Write unit tests for report service

  - Test report structure with completed papers
  - Test error handling for missing payloads
  - Test report key format
  - Test failure inclusion in report
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 10. Checkpoint - Ensure all tests pass

  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement job submission service

  - Create app/services/job_service.py with JobService class
  - Implement submit_job() to validate request and call orchestrator
  - Add request validation logic
  - Add initial payload persistence
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x]* 11.1 Write property test for job submission

  - **Property 1: Trace ID uniqueness**
  - **Validates: Requirements 1.1**

- [x]* 11.2 Write unit tests for job service

  - Test valid job submission
  - Test invalid parameter handling
  - Test payload persistence before triggering
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 12. Implement status query service

  - Create app/services/status_service.py with StatusService class
  - Implement get_job_status() to retrieve and format job state
  - Implement \_calculate_counts() for work item statistics
  - Add handling for non-existent trace IDs
  - _Requirements: 19.1, 19.2, 19.3, 19.4_

- [x]* 12.1 Write property test for status count calculation

  - **Property: Status count accuracy**
  - **Validates: Requirements 19.2**

- [x]* 12.2 Write unit tests for status service

  - Test status retrieval for existing jobs
  - Test 404 handling for missing trace IDs
  - Test count calculations
  - Test report key inclusion
  - _Requirements: 19.1, 19.2, 19.3, 19.4_

- [x] 13. Implement API routes

  - Create app/api/routes.py with FastAPI router
  - Implement POST /api/v1/jobs endpoint for job submission
  - Implement GET /api/v1/jobs/{trace_id} endpoint for status queries
  - Implement GET /health endpoint for liveness checks
  - Implement GET /ready endpoint for readiness checks
  - Add request/response validation with Pydantic models
  - _Requirements: 1.1, 1.3, 19.1, 19.4, 21.1, 21.2_

- [x]* 13.1 Write unit tests for API routes

  - Test job submission endpoint with valid/invalid requests
  - Test status query endpoint
  - Test health check endpoint
  - Test readiness check endpoint
  - _Requirements: 1.1, 1.3, 19.1, 19.4, 21.1, 21.2, 21.3, 21.4_

- [x] 14. Implement dependency injection

  - Create app/api/dependencies.py with FastAPI dependencies
  - Implement get_settings() dependency
  - Implement get_mq_manager() dependency with singleton pattern
  - Implement get_storage() dependency with singleton pattern
  - Implement get_state_manager() dependency
  - Implement get_orchestrator() dependency
  - _Requirements: 16.2_

- [x] 15. Implement application lifecycle management

  - Create app/core/lifecycle.py with startup and shutdown handlers
  - Implement startup_handler() to initialize connections
  - Implement shutdown_handler() for graceful shutdown
  - Add background task for event consumption
  - Add timeout handling for shutdown
  - _Requirements: 16.3, 16.4, 23.1, 23.2, 23.3, 23.4, 23.5_

- [x]* 15.1 Write integration test for graceful shutdown

  - Test in-flight message completion before shutdown
  - Test connection closure after message acknowledgment
  - Test shutdown timeout enforcement
  - _Requirements: 23.2, 23.3, 23.4, 23.5_

- [x] 16. Implement main FastAPI application

  - Create app/main.py with FastAPI app instance
  - Register API routers
  - Add startup and shutdown event handlers
  - Configure CORS middleware if needed
  - Add exception handlers for common errors
  - _Requirements: 16.1, 16.3, 16.4, 16.5_

- [x] 17. Implement metrics collection

  - Create app/infrastructure/metrics.py with Prometheus metrics
  - Add counters for submitted, completed, failed jobs
  - Add histograms for event processing latency
  - Add histograms for command publishing latency
  - Implement /metrics endpoint
  - _Requirements: 24.1, 24.2, 24.3, 24.4, 24.5_

- [x]* 17.1 Write unit tests for metrics

  - Test metric increments
  - Test metric labels
  - Test metrics endpoint format
  - _Requirements: 24.1, 24.2, 24.3, 24.4, 24.5_

- [x] 18. Implement retry logic with exponential backoff

  - Create app/core/retry.py with RetryConfig and with_retry() function
  - Implement exponential backoff calculation
  - Add retry logic to MQ operations
  - Add retry logic to storage operations
  - Configure max attempts and delays
  - _Requirements: 18.1, 18.2, 18.3, 18.4_

- [x]* 18.1 Write unit tests for retry logic

  - Test exponential backoff calculation
  - Test max attempts enforcement
  - Test retriable vs non-retriable errors
  - _Requirements: 18.1, 18.2, 18.3, 18.4_

- [x] 19. Create workflow configuration file

  - Create config/workflows.yaml with MORNING_REPORT workflow
  - Define stages: discovery, downloader (fan-out), parser, indexer
  - Define routing keys and event patterns
  - Add filter function reference for PDF candidate filtering
  - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_

- [x] 20. Checkpoint - Integration testing

  - Ensure all tests pass, ask the user if questions arise.

- [x] 21. Write integration tests with test containers

  - Set up pytest fixtures for RabbitMQ and MinIO test containers
  - Write integration test for full job submission flow
  - Write integration test for event processing flow
  - Write integration test for state persistence
  - Write integration test for command publishing
  - _Requirements: All_

- [x]* 21.1 Write end-to-end test for MORNING_REPORT workflow

  - Submit job, mock tool service events, verify report generation
  - Test partial failure handling
  - Test concurrent job processing
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 7.2, 7.3, 20.1, 20.2, 20.3_

- [x] 22. Create Dockerfile and deployment configuration

  - Create Dockerfile with Python 3.11 base image
  - Add requirements installation
  - Configure uvicorn command
  - Create docker-compose.yml for local development
  - Add environment variable documentation
  - _Requirements: Deployment_

- [x] 23. Create README and documentation

  - Write README.md with project overview
  - Document API endpoints with examples
  - Document environment variables
  - Document workflow configuration format
  - Add architecture diagrams
  - _Requirements: Documentation_

- [x] 24. Final checkpoint - Complete testing and validation
  - Run all unit tests
  - Run all property-based tests
  - Run all integration tests
  - Run end-to-end tests
  - Verify test coverage meets requirements
  - Ensure all tests pass, ask the user if questions arise.
