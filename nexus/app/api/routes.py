from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from app.models.api_models import (
    JobSubmitRequest, 
    JobSubmitResponse, 
    JobStatusResponse
)
from app.services.job_service import JobService
from app.services.status_service import StatusService
from app.services.report_service import ReportService
from app.infrastructure.mq_manager import MQManager
from app.infrastructure.storage import StorageBackend
from app.api.dependencies import (
    get_job_service, 
    get_status_service,
    get_report_service,
    get_mq_manager,
    get_storage
)

router = APIRouter()

@router.post(
    "/jobs", 
    response_model=JobSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED
)
async def submit_job(
    request: JobSubmitRequest,
    service: JobService = Depends(get_job_service)
):
    try:
        return await service.submit_job(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get(
    "/jobs/{trace_id}",
    response_model=JobStatusResponse
)
async def get_job_status(
    trace_id: str,
    service: StatusService = Depends(get_status_service)
):
    response = await service.get_job_status(trace_id)
    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {trace_id} not found"
        )
    return response

@router.get("/jobs/{trace_id}/report")  # 必须在 /artifacts/{artifact_key} 之前定义（FastAPI 路由匹配顺序）
async def get_job_report(
    trace_id: str,
    report_service: ReportService = Depends(get_report_service)
):
    """
    Get a standardized report for a completed job.
    
    This endpoint aggregates all artifacts from a job into a unified, standardized format.
    Supports MORNING_REPORT and SUMMARY_REPORT task types.
    
    Returns 404 if job not found, 400 if job is not completed yet.
    """
    try:
        report = await report_service.build_report(trace_id)
        return report
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(e)}"
        )


@router.get(
    "/jobs/{trace_id}/artifacts/{artifact_key}",
    response_class=StreamingResponse
)
async def get_job_artifact(
    trace_id: str,
    artifact_key: str,
    service: StatusService = Depends(get_status_service)
):
    try:
        # Verify artifact exists and belongs to job
        artifact_stream, content_type = await service.get_artifact_stream(trace_id, artifact_key)
        
        return StreamingResponse(
            artifact_stream,
            media_type=content_type
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve artifact: {str(e)}"
        )


@router.get("/health")
async def health_check(
    mq: MQManager = Depends(get_mq_manager),
    storage: StorageBackend = Depends(get_storage)
):
    mq_healthy = await mq.is_healthy()
    storage_healthy = await storage.is_healthy()
    
    status_code = status.HTTP_200_OK if (mq_healthy and storage_healthy) else status.HTTP_503_SERVICE_UNAVAILABLE
    
    return {
        "status": "healthy" if (mq_healthy and storage_healthy) else "unhealthy",
        "details": {
            "mq": "healthy" if mq_healthy else "unhealthy",
            "storage": "healthy" if storage_healthy else "unhealthy"
        }
    }

@router.get("/ready")
async def readiness_check(
    mq: MQManager = Depends(get_mq_manager)
):
    # Check if we can accept traffic
    if await mq.is_healthy():
        return {"status": "ready"}
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Service not ready"
    )
