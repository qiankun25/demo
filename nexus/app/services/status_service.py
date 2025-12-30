from typing import Optional
from app.engine.orchestrator import WorkflowOrchestrator
from app.models.api_models import JobStatusResponse

class StatusService:
    def __init__(self, orchestrator: WorkflowOrchestrator):
        self.orchestrator = orchestrator

    def _extract_work_key(self, storage_key: str) -> Optional[str]:
        marker = "data:work:"
        i = storage_key.rfind(marker)
        if i < 0:
            return None
        wk = storage_key[i + len(marker) :]
        return wk or None

    def _is_authorized_storage_key(self, trace_id: str, task_type: str, storage_key: str, work_keys: list[str]) -> bool:
        if not storage_key:
            return False
        if task_type == "MORNING_REPORT" and storage_key == f"data:manifest:{trace_id}":
            return True
        if storage_key.startswith("data:discovery:") and trace_id in storage_key:
            return True
        wk = self._extract_work_key(storage_key)
        if wk and wk in set(work_keys or []):
            return True
        return False

    async def _fallback_storage_key(self, trace_id: str, task_type: str, artifact_key: str) -> Optional[str]:
        if task_type == "MORNING_REPORT" and artifact_key == "detailed_manifest":
            storage_key = f"data:manifest:{trace_id}"
            if await self.orchestrator.storage.exists(storage_key):
                return storage_key
        return None

    async def get_job_status(self, trace_id: str) -> Optional[JobStatusResponse]:
        context = await self.orchestrator.get_job_status(trace_id)
        if not context:
            return None

        # Best-effort reconciliation to avoid a known stuck state:
        # SUMMARY_REPORT can end up with completed=total but status remains "processing" if overview triggering was missed.
        # This call is idempotent and will only do work when the job is objectively ready to advance.
        try:
            if (
                context.task_type == "SUMMARY_REPORT"
                and context.current_stage == "processing"
                and len(context.work_keys) > 0
                and (len(context.completed_work_keys) + len(context.failures)) >= len(context.work_keys)
            ):
                await self.orchestrator._check_completion(trace_id)
                context = await self.orchestrator.get_job_status(trace_id) or context
        except Exception:
            # Never fail the status endpoint due to reconciliation issues.
            pass
            
        total = len(context.work_keys)
        completed = len(context.completed_work_keys)
        failed = len(context.failures)
        # Ensure pending is not negative (though logic should prevent it)
        pending = max(0, total - completed - failed)
            
        artifacts = {
            k: f"/api/v1/jobs/{context.trace_id}/artifacts/{k}"
            for k, v in context.artifacts.items()
        }

        if context.current_stage == "completed":
            storage_key = await self._fallback_storage_key(context.trace_id, context.task_type, "detailed_manifest")
            if storage_key and "detailed_manifest" not in artifacts:
                artifacts["detailed_manifest"] = f"/api/v1/jobs/{context.trace_id}/artifacts/detailed_manifest"

        return JobStatusResponse(
            trace_id=context.trace_id,
            task_type=context.task_type,
            status=context.current_stage,
            total_work_items=total,
            completed_count=completed,
            failed_count=failed,
            pending_count=pending,
            artifacts=artifacts,
            failures=[f.model_dump() for f in context.failures]
        )

    async def get_artifact_stream(self, trace_id: str, artifact_key: str):
        """Get artifact stream for a specific job"""
        # 1. Get job context to verify artifact belongs to job
        context = await self.orchestrator.get_job_status(trace_id)
        if not context:
            raise ValueError(f"Job {trace_id} not found")
            
        storage_key = context.artifacts.get(artifact_key)
        if not storage_key:
            storage_key = await self._fallback_storage_key(trace_id, context.task_type, artifact_key)
        if not storage_key:
            if isinstance(artifact_key, str) and artifact_key.startswith("data:"):
                if self._is_authorized_storage_key(trace_id, context.task_type, artifact_key, context.work_keys):
                    try:
                        if await self.orchestrator.storage.exists(artifact_key):
                            storage_key = artifact_key
                    except Exception:
                        storage_key = None
        if not storage_key:
            raise ValueError(f"Artifact {artifact_key} not found in job {trace_id}")
        
        # 4. Get stream from storage
        return await self.orchestrator.storage.get_stream(storage_key)
