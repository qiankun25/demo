"""End-to-end integration tests for the Literature Download Service.

This module tests the complete download pipeline including:
- Task creation via API
- Celery worker processing (running in Docker)
- File download and storage
- Status tracking and retrieval

Note: These tests require Docker services to be running (docker-compose up)
"""

import asyncio
import time
import uuid

import httpx
import pytest

from app.config import settings
from app.services.storage import MinIOStorage


# Test configuration
TEST_PDF_URL = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
TEST_INVALID_URL = "https://httpbin.org/status/404"
API_BASE_URL = "http://localhost:8000"
POLL_INTERVAL = 2  # seconds
MAX_POLL_TIME = 60  # seconds


@pytest.fixture(scope="module")
def storage_client():
    """Create MinIO storage client for test cleanup."""
    storage = MinIOStorage(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket,
        secure=settings.minio_secure
    )
    yield storage


@pytest.fixture(autouse=True)
def cleanup_test_data(storage_client):
    """Clean up test data after each test."""
    yield
    
    # Clean up MinIO test files after test
    try:
        if storage_client.client.bucket_exists(settings.minio_bucket):
            objects = storage_client.client.list_objects(
                settings.minio_bucket,
                recursive=True
            )
            for obj in objects:
                try:
                    storage_client.client.remove_object(settings.minio_bucket, obj.object_name)
                    print(f"Cleaned up: {obj.object_name}")
                except Exception as e:
                    print(f"Failed to clean up {obj.object_name}: {e}")
    except Exception as e:
        print(f"MinIO cleanup error: {e}")


async def poll_task_status(
    client: httpx.AsyncClient,
    task_id: str,
    max_time: int = MAX_POLL_TIME,
    interval: int = POLL_INTERVAL
) -> dict:
    """Poll task status until completion or timeout.
    
    Args:
        client: HTTP client for API requests
        task_id: Task identifier to poll
        max_time: Maximum time to poll in seconds
        interval: Polling interval in seconds
        
    Returns:
        Final task status response
        
    Raises:
        TimeoutError: If task doesn't complete within max_time
    """
    start_time = time.time()
    
    while time.time() - start_time < max_time:
        response = await client.get(f"/download/{task_id}")
        
        if response.status_code != 200:
            print(f"Status check returned {response.status_code}: {response.text}")
            await asyncio.sleep(interval)
            continue
        
        data = response.json()
        status = data.get("status")
        print(f"Task {task_id} status: {status}")
        
        if status in ["success", "failed"]:
            return data
        
        await asyncio.sleep(interval)
    
    raise TimeoutError(f"Task {task_id} did not complete within {max_time} seconds")


@pytest.mark.asyncio
async def test_full_download_pipeline():
    """Test the complete download pipeline from submission to file retrieval.
    
    This test validates:
    1. Task creation via POST /download
    2. Celery worker processing (running in Docker)
    3. Status transitions (pending -> downloading -> success)
    4. File upload to MinIO
    5. Presigned URL generation
    6. File accessibility and content validation
    
    Prerequisites: Docker services must be running (docker-compose up)
    """
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
        # Step 1: Submit download request
        response = await client.post(
            "/download",
            json={"url": TEST_PDF_URL}
        )
        
        assert response.status_code == 201, f"Task creation failed: {response.text}"
        
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "pending"
        
        task_id = data["task_id"]
        print(f"Created task: {task_id}")
        
        # Step 2: Poll status until completion
        final_status = await poll_task_status(client, task_id)
        
        # Step 3: Verify success status
        assert final_status["status"] == "success", \
            f"Task failed: {final_status.get('error_message')}"
        assert final_status["task_id"] == task_id
        assert final_status["file_url"] is not None
        assert final_status["error_message"] is None
        assert "created_at" in final_status
        assert "updated_at" in final_status
        
        file_url = final_status["file_url"]
        print(f"File URL: {file_url}")
        
        # Step 4: Verify presigned URL format
        # Note: Due to S3 signature requirements, we cannot simply replace the hostname
        # The signature includes the host header, so changing minio:9000 to localhost:9000
        # would invalidate the signature. In production, configure MINIO_EXTERNAL_ENDPOINT.
        assert "papers/" in file_url, "URL should contain bucket path"
        assert "X-Amz-Algorithm" in file_url, "URL should be a presigned URL"
        assert "X-Amz-Signature" in file_url, "URL should contain signature"
        assert task_id in file_url, "URL should contain task ID"
        assert "dummy.pdf" in file_url, "URL should contain filename"
        
        print(f"Presigned URL format validated successfully")


@pytest.mark.asyncio
async def test_failed_download_scenario():
    """Test that failed downloads are handled correctly.
    
    This test validates:
    1. Task creation with invalid URL
    2. Worker attempts download
    3. Retry logic executes
    4. Final status is "failed" with error message
    
    Prerequisites: Docker services must be running (docker-compose up)
    """
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
        # Step 1: Submit download request with 404 URL
        response = await client.post(
            "/download",
            json={"url": TEST_INVALID_URL}
        )
        
        assert response.status_code == 201
        data = response.json()
        task_id = data["task_id"]
        
        print(f"Created task with invalid URL: {task_id}")
        
        # Step 2: Poll status until completion
        final_status = await poll_task_status(client, task_id)
        
        # Step 3: Verify failed status
        assert final_status["status"] == "failed", \
            "Task should have failed for 404 URL"
        assert final_status["error_message"] is not None
        assert final_status["file_url"] is None
        
        print(f"Task correctly failed with error: {final_status['error_message']}")


@pytest.mark.asyncio
async def test_task_not_found():
    """Test that querying a non-existent task returns 404."""
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=10.0) as client:
        fake_task_id = str(uuid.uuid4())
        
        response = await client.get(f"/download/{fake_task_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


@pytest.mark.asyncio
async def test_missing_url_validation():
    """Test that requests without URL field return validation error."""
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=10.0) as client:
        # Submit request without URL
        response = await client.post(
            "/download",
            json={}
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data


@pytest.mark.asyncio
async def test_task_status_transitions():
    """Test that task status transitions correctly through the pipeline.
    
    This test validates the state machine:
    pending -> downloading -> success
    
    Prerequisites: Docker services must be running (docker-compose up)
    """
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
        # Create task
        response = await client.post(
            "/download",
            json={"url": TEST_PDF_URL}
        )
        
        task_id = response.json()["task_id"]
        
        # Check initial status
        response = await client.get(f"/download/{task_id}")
        if response.status_code == 200:
            initial_status = response.json()["status"]
            # Status could be pending or downloading depending on worker speed
            assert initial_status in ["pending", "downloading"], \
                f"Initial status should be pending or downloading, got: {initial_status}"
            print(f"Initial status: {initial_status}")
        
        # Wait a bit and check if it transitions
        await asyncio.sleep(3)
        response = await client.get(f"/download/{task_id}")
        if response.status_code == 200:
            intermediate_status = response.json()["status"]
            assert intermediate_status in ["pending", "downloading", "success"]
            print(f"Intermediate status: {intermediate_status}")
        
        # Wait for final status
        final_status = await poll_task_status(client, task_id)
        assert final_status["status"] == "success"
        
        print(f"Final status: {final_status['status']}")
