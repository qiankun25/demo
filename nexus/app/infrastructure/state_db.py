"""DB-backed StateManager for orchestration job contexts."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional, Callable

from app.infrastructure.orchestration_db import OrchestrationDB
from app.models.state_models import JobContext, FailureRecord


class DBStateManager:
    """Persist `JobContext` in orchestration DB instead of MinIO."""

    def __init__(self, db: OrchestrationDB):
        self.db = db
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def _get_lock(self, trace_id: str) -> asyncio.Lock:
        async with self._global_lock:
            if trace_id not in self._locks:
                self._locks[trace_id] = asyncio.Lock()
            return self._locks[trace_id]

    async def get_context(self, trace_id: str) -> Optional[JobContext]:
        job = await asyncio.to_thread(self.db.get_job_row, trace_id)
        if not job:
            return None

        # Base context from stored context_json (keeps metadata shape stable),
        # but work_items + artifacts_index are the fact source.
        ctx_raw = job.get("context_json") or "{}"
        try:
            base = json.loads(ctx_raw) if isinstance(ctx_raw, str) else {}
        except Exception:
            base = {}

        metadata_raw = job.get("metadata_json") or "{}"
        try:
            meta = json.loads(metadata_raw) if isinstance(metadata_raw, str) else {}
        except Exception:
            meta = {}

        wi_rows = await asyncio.to_thread(self.db.list_work_items, trace_id)
        work_keys = [r.get("work_key") for r in wi_rows if r.get("work_key")]
        completed = [r.get("work_key") for r in wi_rows if r.get("status") == "COMPLETED" and r.get("work_key")]
        failures = [
            FailureRecord(
                work_key=str(r.get("work_key") or ""),
                stage=str(r.get("stage") or ""),
                routing_key="unknown",
                input_key="",
                error_msg=str(r.get("last_error") or "failed"),
            )
            for r in wi_rows
            if r.get("status") == "FAILED" and r.get("work_key")
        ]

        refs_rows = await asyncio.to_thread(self.db.list_artifact_refs, trace_id)
        artifacts_refs: Dict[str, Any] = {}
        for r in refs_rows:
            name = r.get("name")
            raw = r.get("ref_json") or "{}"
            if not name:
                continue
            try:
                artifacts_refs[str(name)] = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                continue

        merged = dict(base or {})
        merged.update(
            {
                "trace_id": str(job.get("trace_id") or trace_id),
                "task_type": str(job.get("task_type") or base.get("task_type") or ""),
                "init_key": "",
                "requested_limit": int(job.get("requested_limit") or 5),
                "metadata": meta if isinstance(meta, dict) else {},
                "current_stage": str(job.get("status") or base.get("current_stage") or "init"),
                "work_keys": work_keys,
                "completed_work_keys": completed,
                "failures": failures,
                "artifacts": {},  # ref-only
                "artifacts_refs": artifacts_refs,
            }
        )
        return JobContext(**merged)

    async def save_context(self, context: JobContext) -> None:
        lock = await self._get_lock(context.trace_id)
        async with lock:
            await asyncio.to_thread(
                self.db.upsert_job_context_json,
                trace_id=context.trace_id,
                task_type=context.task_type,
                requested_limit=context.requested_limit,
                metadata_obj=context.metadata or {},
                context_obj=context.model_dump(),
            )
            # sync work_items and artifact refs
            for wk in context.work_keys or []:
                st = "PENDING"
                if wk in set(context.completed_work_keys or []):
                    st = "COMPLETED"
                if any(f.work_key == wk for f in (context.failures or [])):
                    st = "FAILED"
                await asyncio.to_thread(
                    self.db.upsert_work_item,
                    trace_id=context.trace_id,
                    work_key=wk,
                    stage=str(context.current_stage or "init"),
                    status=st,
                    attempt=0,
                )
            for name, ref in (getattr(context, "artifacts_refs", {}) or {}).items():
                if isinstance(ref, dict):
                    await asyncio.to_thread(self.db.upsert_artifact_ref, trace_id=context.trace_id, name=str(name), ref_obj=ref)

    async def update_context(self, trace_id: str, updates: Dict[str, Any]) -> JobContext:
        lock = await self._get_lock(trace_id)
        async with lock:
            current = await self.get_context(trace_id)
            if not current:
                raise ValueError(f"Context not found for trace_id: {trace_id}")
            current_dict = current.model_dump()
            current_dict.update(updates)
            updated = JobContext(**current_dict)
            await asyncio.to_thread(self.db.update_job_context_json, trace_id, updated.model_dump())
            # keep fact tables in sync
            for wk in updated.work_keys or []:
                st = "PENDING"
                if wk in set(updated.completed_work_keys or []):
                    st = "COMPLETED"
                if any(f.work_key == wk for f in (updated.failures or [])):
                    st = "FAILED"
                await asyncio.to_thread(
                    self.db.upsert_work_item,
                    trace_id=trace_id,
                    work_key=wk,
                    stage=str(updated.current_stage or "init"),
                    status=st,
                    attempt=0,
                )
            for name, ref in (getattr(updated, "artifacts_refs", {}) or {}).items():
                if isinstance(ref, dict):
                    await asyncio.to_thread(self.db.upsert_artifact_ref, trace_id=trace_id, name=str(name), ref_obj=ref)
            return updated

    async def atomic_update_context(
        self, trace_id: str, update_func: Callable[[JobContext], Dict[str, Any]]
    ) -> JobContext:
        lock = await self._get_lock(trace_id)
        async with lock:
            current = await self.get_context(trace_id)
            if not current:
                raise ValueError(f"Context not found for trace_id: {trace_id}")
            updates = update_func(current)
            if not updates:
                return current
            current_dict = current.model_dump()
            current_dict.update(updates)
            updated = JobContext(**current_dict)
            await asyncio.to_thread(self.db.update_job_context_json, trace_id, updated.model_dump())
            return updated


