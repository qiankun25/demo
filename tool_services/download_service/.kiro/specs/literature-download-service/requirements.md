# Requirements Document

## Introduction

This document specifies the requirements for a Literature Download Service built on the Dify platform's research agent ecosystem. The system enables asynchronous downloading of academic literature (PDFs) from various sources (arXiv, Semantic Scholar, Springer, etc.), with automatic retry mechanisms, file storage in MinIO, and task status tracking via PostgreSQL.

## Glossary

- **Download Service**: The FastAPI-based web service that receives download requests and manages task lifecycle
- **Task Worker**: The Celery worker process that executes asynchronous download operations
- **Task Queue**: Redis-based message broker for distributing download tasks
- **Object Storage**: MinIO S3-compatible storage system for PDF files
- **Task Database**: PostgreSQL database storing task metadata and file records
- **Presigned URL**: Time-limited signed URL for secure file access from MinIO
- **URL Validator**: Component that checks URL reachability before download attempts
- **Downloader**: Component that retrieves PDF files from remote sources
- **Storage Manager**: Component that handles file uploads to MinIO

## Requirements

### Requirement 1: Task Creation API

**User Story:** As an upstream service, I want to submit a literature URL for download, so that I can retrieve the PDF file asynchronously without blocking my workflow.

#### Acceptance Criteria

1. WHEN a POST request is sent to /download with a valid URL, THE Download Service SHALL create a task record in the Task Database with status "pending"
2. WHEN a task record is created, THE Download Service SHALL enqueue the task to the Task Queue
3. WHEN a task is successfully enqueued, THE Download Service SHALL return a unique task identifier within 200 milliseconds
4. THE Download Service SHALL accept URLs from arXiv, Semantic Scholar, and Springer domains
5. IF the request body is missing the "url" field, THEN THE Download Service SHALL return HTTP 422 with validation error details

### Requirement 2: Asynchronous Download Execution

**User Story:** As a system operator, I want download tasks to execute asynchronously with automatic retries, so that temporary failures do not result in permanent task failures.

#### Acceptance Criteria

1. WHEN a task is dequeued from the Task Queue, THE Task Worker SHALL update the task status to "downloading" in the Task Database
2. WHEN the URL Validator confirms URL reachability, THE Task Worker SHALL proceed with file download
3. IF a download attempt fails, THEN THE Task Worker SHALL retry the operation up to 3 times with exponential backoff starting at 5 seconds
4. WHEN a file is successfully downloaded, THE Task Worker SHALL upload the file to Object Storage in the "papers" bucket
5. WHEN file upload succeeds, THE Task Worker SHALL update the task status to "success" and record the file metadata in the Task Database
6. IF all retry attempts are exhausted, THEN THE Task Worker SHALL update the task status to "failed" and record the error message

### Requirement 3: URL Validation

**User Story:** As a system operator, I want to validate URL reachability before attempting downloads, so that I can fail fast on invalid URLs and conserve system resources.

#### Acceptance Criteria

1. WHEN validating a URL, THE URL Validator SHALL send an HTTP HEAD request to the target URL
2. IF the HEAD request fails, THEN THE URL Validator SHALL send an HTTP GET request as a fallback
3. WHEN the response status code is between 200 and 299, THE URL Validator SHALL report the URL as reachable
4. WHEN the response status code is 404 or 5xx, THE URL Validator SHALL report the URL as unreachable
5. THE URL Validator SHALL complete validation within 10 seconds or report timeout

### Requirement 4: File Storage Management

**User Story:** As a system operator, I want downloaded files stored in MinIO with automatic bucket creation, so that files are persistently available and accessible via secure URLs.

#### Acceptance Criteria

1. WHEN uploading a file, THE Storage Manager SHALL check if the "papers" bucket exists in Object Storage
2. IF the "papers" bucket does not exist, THEN THE Storage Manager SHALL create it with default permissions
3. WHEN a file is uploaded, THE Storage Manager SHALL store the file with a unique object key derived from the task identifier
4. WHEN a file upload completes, THE Storage Manager SHALL record the bucket name, object key, file size, and MIME type in the Task Database
5. WHEN generating a file access URL, THE Storage Manager SHALL create a Presigned URL valid for 3600 seconds

### Requirement 5: Task Status Query API

**User Story:** As an upstream service, I want to query the status of my download task, so that I can retrieve the file URL when the download completes.

#### Acceptance Criteria

1. WHEN a GET request is sent to /download/{task_id}, THE Download Service SHALL retrieve the task record from the Task Database
2. IF the task identifier does not exist, THEN THE Download Service SHALL return HTTP 404 with error details
3. WHEN the task status is "success", THE Download Service SHALL include a valid Presigned URL in the response
4. WHEN the task status is "pending" or "downloading", THE Download Service SHALL return the current status without a file URL
5. WHEN the task status is "failed", THE Download Service SHALL include the error message in the response

### Requirement 6: Database Schema

**User Story:** As a system operator, I want task and file metadata persisted in a relational database, so that I can track task history and file locations.

#### Acceptance Criteria

1. THE Task Database SHALL contain a "download_task" table with columns: id (UUID), url (TEXT), status (ENUM), retry_count (INT), error_message (TEXT), file_id (UUID), created_at (TIMESTAMP), updated_at (TIMESTAMP)
2. THE Task Database SHALL contain a "document_file" table with columns: id (UUID), file_name (TEXT), minio_bucket (TEXT), minio_object (TEXT), mime_type (TEXT), file_size (INT), created_at (TIMESTAMP)
3. THE Download Service SHALL use SQLAlchemy ORM for all database operations
4. WHEN a task is created, THE Download Service SHALL set created_at and updated_at to the current timestamp
5. WHEN a task status changes, THE Download Service SHALL update the updated_at timestamp

### Requirement 7: Configuration Management

**User Story:** As a system operator, I want all service configurations externalized via environment variables, so that I can deploy the service across different environments without code changes.

#### Acceptance Criteria

1. THE Download Service SHALL load configuration from environment variables using Pydantic Settings
2. THE Download Service SHALL require the following environment variables: DATABASE_URL, REDIS_URL, MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET
3. IF any required environment variable is missing, THEN THE Download Service SHALL fail to start and log the missing variable name
4. THE Download Service SHALL provide default values for optional configuration parameters
5. THE Download Service SHALL validate configuration values at startup and report validation errors

### Requirement 8: Containerized Deployment

**User Story:** As a system operator, I want the entire service stack deployable via Docker Compose, so that I can run the service with a single command.

#### Acceptance Criteria

1. THE deployment configuration SHALL include services for: FastAPI application, Celery worker, Redis, MinIO, PostgreSQL
2. WHEN docker-compose up is executed, THE deployment SHALL start all services with proper dependency ordering
3. THE FastAPI application SHALL expose port 8000 for HTTP requests
4. THE MinIO service SHALL expose port 9000 for S3 API and port 9001 for web console
5. THE Redis service SHALL expose port 6379 for client connections

### Requirement 9: End-to-End Integration Testing

**User Story:** As a developer, I want comprehensive E2E tests that validate the entire download pipeline, so that I can verify system behavior without mocking critical components.

#### Acceptance Criteria

1. THE test suite SHALL use pytest as the test framework
2. WHEN executing E2E tests, THE test suite SHALL start a real Celery worker process
3. THE test suite SHALL submit a download request for a real PDF URL and verify successful completion
4. WHEN a download completes, THE test suite SHALL verify the Presigned URL returns HTTP 200 and valid PDF content
5. THE test suite SHALL clean up test files from Object Storage after test completion
6. IF any pipeline step fails, THEN THE test suite SHALL fail the test and output detailed error logs
7. THE test suite SHALL complete within 60 seconds or fail with a timeout error
