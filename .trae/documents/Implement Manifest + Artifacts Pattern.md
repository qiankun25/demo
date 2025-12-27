# API Implementation for Manifest + Artifacts Pattern

I have successfully implemented the "Manifest + Artifacts" data retrieval pattern in Nexus.

## 1. API Models Update (`api_models.py`)
- Updated `JobStatusResponse` to include an `artifacts` field.
- `artifacts` is a dictionary mapping logical keys (e.g., "search_result") to download URLs.
- Removed the deprecated `report_key` field.

## 2. State Management Update (`state_models.py`)
- Updated `JobContext` to track `artifacts` (mapping of logical keys to storage paths).
- This allows the workflow engine to register outputs dynamically during execution.

## 3. Storage Layer Update (`storage.py`)
- Added `get_stream(key)` method to `StorageBackend` and `MinIOStorage`.
- Implemented **Stream Passthrough**: The method returns a generator that yields data chunks directly from MinIO response stream, avoiding memory buffering.
- Handles `Content-Type` detection from MinIO metadata.

## 4. Service Layer Update (`status_service.py`)
- Updated `get_job_status` to construct full download URLs for artifacts in the response.
- Added `get_artifact_stream(trace_id, artifact_key)` method:
    - Verifies the artifact belongs to the job (security check).
    - Resolves the logical artifact key to the physical storage path.
    - Returns the storage stream.

## 5. API Routes Update (`routes.py`)
- Added new endpoint: `GET /jobs/{trace_id}/artifacts/{artifact_key}`.
- Uses FastAPI's `StreamingResponse` to pipe the data from MinIO -> Nexus -> Client.
- Handles 404s for missing jobs or artifacts.

## 6. Verification
- Created unit tests in `tests/unit/test_api_routes.py`.
- Verified:
    - Job status response contains the artifacts map.
    - Artifact endpoint returns data stream with correct content type.
    - Error handling for invalid jobs/artifacts.
- All tests passed.
