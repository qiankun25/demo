from typing import Optional, Any, Dict, Tuple
import io
import json
import httpx
from app.engine.orchestrator import WorkflowOrchestrator
from app.models.api_models import JobStatusResponse

class StatusService:
    def __init__(self, orchestrator: WorkflowOrchestrator):
        self.orchestrator = orchestrator

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
            
        # Ref-only: expose refs via a stable endpoint
        artifacts: Dict[str, str] = {}
        refs = getattr(context, "artifacts_refs", {}) or {}
        if isinstance(refs, dict):
            for k in sorted(refs.keys()):
                artifacts[str(k)] = f"/api/v1/jobs/{context.trace_id}/artifacts/{k}"

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
        """Get artifact payload via Query APIs based on stored refs (ref-only)."""
        context = await self.orchestrator.get_job_status(trace_id)
        if not context:
            raise ValueError(f"Job {trace_id} not found")

        refs = getattr(context, "artifacts_refs", {}) or {}
        ref = refs.get(artifact_key) if isinstance(refs, dict) else None
        if not isinstance(ref, dict):
            raise ValueError(f"Artifact {artifact_key} not found in job {trace_id}")

        svc = str(ref.get("service") or "")
        rtype = str(ref.get("type") or "")
        rid = str(ref.get("id") or "")
        if not (svc and rtype and rid):
            raise ValueError("Invalid ref stored for artifact")

        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            if svc == "discovery" and rtype == "search_result":
                url = self.orchestrator.settings.discovery_base_url.rstrip("/") + f"/v1/results/{rid}"
                resp = await client.get(url)
                resp.raise_for_status()
                payload = resp.json()
            elif svc == "parser" and rtype == "parsed_doc":
                url = self.orchestrator.settings.parser_base_url.rstrip("/") + f"/v1/parsed/{rid}"
                resp = await client.get(url)
                resp.raise_for_status()
                payload = resp.json()
            elif svc == "download" and rtype == "file":
                url = self.orchestrator.settings.download_base_url.rstrip("/") + f"/v1/files/{rid}/signed_url"
                resp = await client.get(url)
                resp.raise_for_status()
                payload = resp.json()
            elif svc == "overview" and rtype == "overview_report":
                url = self.orchestrator.settings.overview_base_url.rstrip("/") + f"/v1/reports/{rid}"
                resp = await client.get(url)
                resp.raise_for_status()
                payload = resp.json()
            else:
                raise ValueError(f"Unsupported artifact ref: service={svc}, type={rtype}")

        b = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return io.BytesIO(b), "application/json"
