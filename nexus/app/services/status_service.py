from typing import Optional
from app.engine.orchestrator import WorkflowOrchestrator
from app.models.api_models import JobStatusResponse

class StatusService:
    def __init__(self, orchestrator: WorkflowOrchestrator):
        self.orchestrator = orchestrator

    async def get_job_status(self, trace_id: str) -> Optional[JobStatusResponse]:
        context = await self.orchestrator.get_job_status(trace_id)
        if not context:
            return None
            
        total = len(context.work_keys)
        completed = len(context.completed_work_keys)
        failed = len(context.failures)
        # Ensure pending is not negative (though logic should prevent it)
        pending = max(0, total - completed - failed)
            
        return JobStatusResponse(
            trace_id=context.trace_id,
            task_type=context.task_type,
            status=context.current_stage,
            total_work_items=total,
            completed_count=completed,
            failed_count=failed,
            pending_count=pending,
            artifacts={
                k: f"/api/v1/jobs/{context.trace_id}/artifacts/{k}" 
                for k, v in context.artifacts.items()
            },
            failures=[f.model_dump() for f in context.failures]
        )

    async def get_artifact_stream(self, trace_id: str, artifact_key: str):
        """Get artifact stream for a specific job"""
        # 1. Get job context to verify artifact belongs to job
        context = await self.orchestrator.get_job_status(trace_id)
        if not context:
            raise ValueError(f"Job {trace_id} not found")
            
        # 2. Check if artifact key exists in job's artifacts
        if artifact_key not in context.artifacts:
            raise ValueError(f"Artifact {artifact_key} not found in job {trace_id}")
            
        # 3. Get actual storage key
        storage_key = context.artifacts[artifact_key]
        
        # 4. Get stream from storage
        return await self.orchestrator.storage.get_stream(storage_key)
