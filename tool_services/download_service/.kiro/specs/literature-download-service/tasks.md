# Implementation Plan

- [x] 1. Set up project structure and configuration

  - Create directory structure: app/, tests/, with subdirectories for models, routes, services, tasks
  - Create requirements.txt with all dependencies: fastapi, uvicorn, celery, redis, sqlalchemy, psycopg2-binary, minio, httpx, pydantic-settings, pytest, pytest-asyncio
  - Create app/config.py with Pydantic Settings for environment variables (DATABASE_URL, REDIS_URL, MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET)
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 2. Implement database models and connection

  - [x] 2.1 Create database connection setup in app/database.py

    - Implement SQLAlchemy engine with connection pooling
    - Create async session factory
    - Implement Base declarative class
    - Add database initialization function
    - _Requirements: 6.3_

  - [x] 2.2 Create DownloadTask model in app/models/task.py

    - Define TaskStatus enum (pending, downloading, success, failed)
    - Implement DownloadTask model with all fields: id, url, status, retry_count, error_message, file_id, created_at, updated_at
    - Add relationship to DocumentFile
    - Add indexes on status and created_at
    - _Requirements: 6.1, 6.4, 6.5_

  - [x] 2.3 Create DocumentFile model in app/models/file.py

    - Implement DocumentFile model with fields: id, file_name, minio_bucket, minio_object, mime_type, file_size, created_at
    - Add index on minio_bucket and minio_object
    - _Requirements: 6.2_

- [x] 3. Implement MinIO storage service

  - [x] 3.1 Create MinIOStorage class in app/services/storage.py

    - Initialize Minio client with endpoint, credentials, and bucket name
    - Implement ensure_bucket_exists() method to create bucket if missing
    - Implement upload_file() method to upload bytes to MinIO with object naming pattern {task_id}/{filename}
    - Implement get_presigned_url() method with 3600 second expiration
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 4. Implement URL validation service

  - [x] 4.1 Create URLValidator class in app/services/validator.py

    - Implement async is_reachable() method using httpx
    - Send HEAD request first, fallback to GET if HEAD fails
    - Return tuple of (is_valid: bool, error_message: str)
    - Set 10 second timeout for requests
    - Handle connection errors, timeouts, and HTTP error codes
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 5. Implement PDF downloader service

  - [x] 5.1 Create PDFDownloader class in app/services/downloader.py

    - Implement async download() method using httpx streaming
    - Extract filename from Content-Disposition header or URL path
    - Validate Content-Type contains "pdf" or "application/pdf"
    - Stream file content in chunks to handle large files
    - Return tuple of (file_content: bytes, filename: str)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 6. Set up Celery application

  - [x] 6.1 Create Celery app in app/celery_app.py

    - Configure broker URL as redis://redis:6379/0
    - Configure result backend as redis://redis:6379/1
    - Set task_default_retry_delay to 5 seconds
    - Set max_retries to 3 in task_annotations
    - Import download_task module
    - _Requirements: 2.1, 2.3, 2.6_

- [ ] 7. Implement download task worker

  - [x] 7.1 Create download_pdf_task in app/tasks/download_task.py

    - Define Celery task with bind=True, max_retries=3, autoretry configuration
    - Update task status to "downloading" at start
    - Call URLValidator to check URL reachability
    - Call PDFDownloader to download file
    - Call MinIOStorage to upload file
    - Create DocumentFile record in database
    - Update DownloadTask with file_id and status "success"
    - Implement exponential backoff retry logic (5s, 25s, 125s)
    - Catch exceptions and update status to "failed" with error message after max retries
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [x] 8. Implement FastAPI routes

  - [x] 8.1 Create download routes in app/routes/download.py

    - Implement POST /download endpoint that accepts {"url": "..."} in request body
    - Create DownloadTask record with status "pending"
    - Enqueue task to Celery
    - Return {"task_id": "...", "status": "pending"} within 200ms
    - Add validation for missing URL field (return HTTP 422)
    - _Requirements: 1.1, 1.2, 1.3, 1.5_

  - [x] 8.2 Implement GET /download/{task_id} endpoint

    - Query DownloadTask by task_id
    - Return HTTP 404 if task not found
    - Return task details with status, error_message, created_at, updated_at
    - Include presigned URL from MinIOStorage when status is "success"
    - Return null for file_url when status is pending/downloading/failed
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 9. Create FastAPI application entry point

  - [x] 9.1 Create main.py with FastAPI app initialization

    - Initialize FastAPI app
    - Include download router
    - Add startup event to initialize database tables
    - Add health check endpoint GET /health
    - Configure CORS if needed
    - _Requirements: 1.1, 1.2_

- [x] 10. Create Docker deployment configuration

  - [x] 10.1 Create Dockerfile

    - Use Python 3.10+ base image
    - Copy requirements.txt and install dependencies
    - Copy application code
    - Set working directory
    - Expose port 8000
    - Default command to run uvicorn
    - _Requirements: 8.1, 8.2_

  - [x] 10.2 Create docker-compose.yml

    - Define app service (FastAPI) with port 8000 exposed
    - Define celery service with worker command
    - Define redis service with port 6379
    - Define minio service with ports 9000 and 9001, environment variables MINIO_ROOT_USER and MINIO_ROOT_PASSWORD
    - Define postgres service with database initialization
    - Set up service dependencies (app and celery depend on db, redis, minio)
    - Configure environment variables for all services
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 11. Implement end-to-end integration tests

  - [x] 11.1 Create test_download_integration.py in tests/

    - Set up pytest fixtures for test database and services
    - Implement test_full_download_pipeline that:
      - Submits POST /download request with real PDF URL (https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf)
      - Starts Celery worker subprocess
      - Polls GET /download/{task_id} every 2 seconds for up to 60 seconds
      - Asserts status becomes "success"
      - Verifies presigned URL is accessible (HTTP 200)
      - Validates Content-Type is application/pdf
      - Cleans up test files from MinIO
      - Terminates worker process
    - Add test for failed download scenario
    - Add cleanup fixtures to remove test data after tests
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

- [ ]\* 11.2 Add unit tests for core components

  - Write unit tests for URLValidator in tests/test_validator.py
  - Write unit tests for PDFDownloader in tests/test_downloader.py
  - Write unit tests for MinIOStorage in tests/test_storage.py
  - Write unit tests for API endpoints in tests/test_api.py
  - _Requirements: 9.1_

- [-] 12. Add documentation and final touches

  - [x] 12.1 Create README.md with setup instructions

    - Document prerequisites (Docker, Docker Compose)
    - Add quick start guide (docker-compose up)
    - Document API endpoints with examples
    - Add testing instructions (pytest)
    - Include environment variable reference
    - _Requirements: 8.1_

  - [ ]\* 12.2 Add logging configuration
    - Configure structured logging in app/main.py
    - Add log statements for key operations (task creation, download start/complete, errors)
    - Set appropriate log levels
    - _Requirements: 2.1, 2.5, 2.6_
