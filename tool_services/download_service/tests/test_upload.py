"""Tests for file upload endpoints."""

import pytest
import httpx
from io import BytesIO
from sqlalchemy import select

from app.models.file import DocumentFile


@pytest.mark.asyncio
async def test_upload_single_pdf_success(client: httpx.AsyncClient, async_session):
    """Test successful single PDF file upload."""
    # Create a fake PDF file
    pdf_content = b"%PDF-1.4\n%fake pdf content for testing\n%%EOF"
    files = {
        "files": ("test.pdf", BytesIO(pdf_content), "application/pdf")
    }
    
    response = await client.post("/upload", files=files)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["total"] == 1
    assert data["success"] == 1
    assert data["failed"] == 0
    assert len(data["results"]) == 1
    
    result = data["results"][0]
    assert result["status"] == "success"
    assert result["file_name"] == "test.pdf"
    assert result["file_size"] == len(pdf_content)
    assert result["mime_type"] == "application/pdf"
    assert result["presigned_url"] is not None
    assert result["file_id"] is not None
    assert result["expires_in"] == 3600  # default expiration
    
    # Verify database record
    file_result = await async_session.execute(
        select(DocumentFile).where(DocumentFile.file_name == "test.pdf")
    )
    db_file = file_result.scalar_one_or_none()
    assert db_file is not None
    assert db_file.file_size == len(pdf_content)


@pytest.mark.asyncio
async def test_upload_multiple_pdfs_all_success(client: httpx.AsyncClient, async_session):
    """Test successful upload of multiple PDF files."""
    pdf_content1 = b"%PDF-1.4\n%first pdf\n%%EOF"
    pdf_content2 = b"%PDF-1.4\n%second pdf\n%%EOF"
    pdf_content3 = b"%PDF-1.4\n%third pdf\n%%EOF"
    
    files = [
        ("files", ("file1.pdf", BytesIO(pdf_content1), "application/pdf")),
        ("files", ("file2.pdf", BytesIO(pdf_content2), "application/pdf")),
        ("files", ("file3.pdf", BytesIO(pdf_content3), "application/pdf")),
    ]
    
    response = await client.post("/upload", files=files)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["total"] == 3
    assert data["success"] == 3
    assert data["failed"] == 0
    assert len(data["results"]) == 3
    
    # Check all files succeeded
    for i, result in enumerate(data["results"], 1):
        assert result["status"] == "success"
        assert result["file_name"] == f"file{i}.pdf"
        assert result["presigned_url"] is not None
        assert result["file_id"] is not None


@pytest.mark.asyncio
async def test_upload_with_custom_expiration(client: httpx.AsyncClient):
    """Test upload with custom presigned URL expiration time."""
    pdf_content = b"%PDF-1.4\n%test content\n%%EOF"
    files = {
        "files": ("test.pdf", BytesIO(pdf_content), "application/pdf")
    }
    
    response = await client.post("/upload?expires=7200", files=files)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] == 1
    result = data["results"][0]
    assert result["expires_in"] == 7200


@pytest.mark.asyncio
async def test_upload_file_too_large(client: httpx.AsyncClient):
    """Test upload fails when file exceeds size limit."""
    # Create a file larger than 100MB (assuming default limit)
    large_content = b"X" * (105 * 1024 * 1024)  # 105MB
    files = {
        "files": ("large.pdf", BytesIO(large_content), "application/pdf")
    }
    
    response = await client.post("/upload", files=files)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["total"] == 1
    assert data["success"] == 0
    assert data["failed"] == 1
    
    result = data["results"][0]
    assert result["status"] == "failed"
    assert "exceeds limit" in result["error_message"].lower()


@pytest.mark.asyncio
async def test_upload_empty_file(client: httpx.AsyncClient):
    """Test upload fails for empty file."""
    empty_content = b""
    files = {
        "files": ("empty.pdf", BytesIO(empty_content), "application/pdf")
    }
    
    response = await client.post("/upload", files=files)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["total"] == 1
    assert data["success"] == 0
    assert data["failed"] == 1
    
    result = data["results"][0]
    assert result["status"] == "failed"
    assert "empty" in result["error_message"].lower()


@pytest.mark.asyncio
async def test_upload_non_pdf_file(client: httpx.AsyncClient):
    """Test upload fails for non-PDF file."""
    text_content = b"This is a text file, not a PDF"
    files = {
        "files": ("document.txt", BytesIO(text_content), "text/plain")
    }
    
    response = await client.post("/upload", files=files)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["total"] == 1
    assert data["success"] == 0
    assert data["failed"] == 1
    
    result = data["results"][0]
    assert result["status"] == "failed"
    assert "pdf" in result["error_message"].lower()


@pytest.mark.asyncio
async def test_upload_wrong_mime_type(client: httpx.AsyncClient):
    """Test upload fails when MIME type doesn't match PDF."""
    pdf_content = b"%PDF-1.4\n%content\n%%EOF"
    files = {
        "files": ("test.pdf", BytesIO(pdf_content), "image/jpeg")
    }
    
    response = await client.post("/upload", files=files)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["failed"] == 1
    result = data["results"][0]
    assert result["status"] == "failed"
    assert "mime type" in result["error_message"].lower()


@pytest.mark.asyncio
async def test_upload_partial_success(client: httpx.AsyncClient, async_session):
    """Test batch upload with some files succeeding and some failing."""
    valid_pdf = b"%PDF-1.4\n%valid content\n%%EOF"
    invalid_file = b"Not a PDF file"
    
    files = [
        ("files", ("valid1.pdf", BytesIO(valid_pdf), "application/pdf")),
        ("files", ("invalid.txt", BytesIO(invalid_file), "text/plain")),
        ("files", ("valid2.pdf", BytesIO(valid_pdf), "application/pdf")),
    ]
    
    response = await client.post("/upload", files=files)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["total"] == 3
    assert data["success"] == 2
    assert data["failed"] == 1
    
    # Check individual results
    assert data["results"][0]["status"] == "success"
    assert data["results"][0]["file_name"] == "valid1.pdf"
    
    assert data["results"][1]["status"] == "failed"
    assert data["results"][1]["file_name"] == "invalid.txt"
    
    assert data["results"][2]["status"] == "success"
    assert data["results"][2]["file_name"] == "valid2.pdf"
    
    # Verify only valid files are in database
    file_result = await async_session.execute(
        select(DocumentFile).where(
            DocumentFile.file_name.in_(["valid1.pdf", "valid2.pdf"])
        )
    )
    db_files = file_result.scalars().all()
    assert len(db_files) == 2


@pytest.mark.asyncio
async def test_upload_no_files_provided(client: httpx.AsyncClient):
    """Test upload fails when no files are provided."""
    response = await client.post("/upload")
    
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_upload_special_characters_in_filename(client: httpx.AsyncClient):
    """Test upload with special characters in filename."""
    pdf_content = b"%PDF-1.4\n%content\n%%EOF"
    files = {
        "files": ("test file (2023) [final].pdf", BytesIO(pdf_content), "application/pdf")
    }
    
    response = await client.post("/upload", files=files)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] == 1
    result = data["results"][0]
    assert result["status"] == "success"
    assert result["file_name"] == "test file (2023) [final].pdf"


@pytest.mark.asyncio
async def test_upload_duplicate_filenames(client: httpx.AsyncClient, async_session):
    """Test uploading multiple files with the same name creates separate records."""
    pdf_content1 = b"%PDF-1.4\n%first version\n%%EOF"
    pdf_content2 = b"%PDF-1.4\n%second version\n%%EOF"
    
    files = [
        ("files", ("duplicate.pdf", BytesIO(pdf_content1), "application/pdf")),
        ("files", ("duplicate.pdf", BytesIO(pdf_content2), "application/pdf")),
    ]
    
    response = await client.post("/upload", files=files)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] == 2
    # Both should have different file IDs even with same name
    assert data["results"][0]["file_id"] != data["results"][1]["file_id"]
    
    # Verify both are in database
    file_result = await async_session.execute(
        select(DocumentFile).where(DocumentFile.file_name == "duplicate.pdf")
    )
    db_files = file_result.scalars().all()
    assert len(db_files) == 2


@pytest.mark.asyncio
async def test_upload_expiration_bounds(client: httpx.AsyncClient):
    """Test expiration time validation (min 60s, max 7 days)."""
    pdf_content = b"%PDF-1.4\n%content\n%%EOF"
    
    # Test too short expiration
    files = {
        "files": ("test.pdf", BytesIO(pdf_content), "application/pdf")
    }
    response = await client.post("/upload?expires=30", files=files)
    assert response.status_code == 422
    
    # Test too long expiration
    files = {
        "files": ("test.pdf", BytesIO(pdf_content), "application/pdf")
    }
    response = await client.post("/upload?expires=700000", files=files)
    assert response.status_code == 422
    
    # Test valid expiration at boundaries
    files = {
        "files": ("test1.pdf", BytesIO(pdf_content), "application/pdf")
    }
    response = await client.post("/upload?expires=60", files=files)
    assert response.status_code == 200
    
    files = {
        "files": ("test2.pdf", BytesIO(pdf_content), "application/pdf")
    }
    response = await client.post("/upload?expires=604800", files=files)
    assert response.status_code == 200

