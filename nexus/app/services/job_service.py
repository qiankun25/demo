from app.engine.orchestrator import WorkflowOrchestrator
from app.models.api_models import JobSubmitRequest, JobSubmitResponse

class JobService:
    def __init__(self, orchestrator: WorkflowOrchestrator):
        self.orchestrator = orchestrator

    async def submit_job(self, request: JobSubmitRequest) -> JobSubmitResponse:
        trace_id = await self.orchestrator.submit_job(
            task_type=request.task_type,
            params=request.parameters
        )
        
        return JobSubmitResponse(
            trace_id=trace_id,
            status="submitted",
            message="Job submitted successfully"
        )
