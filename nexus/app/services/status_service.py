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
            report_key=context.report_key,
            failures=[f.model_dump() for f in context.failures]
        )
