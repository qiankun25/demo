"""Orchestration DB (jobs/work_items/artifacts/outbox/inbox).

This is a minimal SQLAlchemy Core implementation to persist job contexts outside MinIO.
It is intentionally synchronous; async call sites use `asyncio.to_thread(...)`.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    select,
    update,
    insert,
)
from sqlalchemy.engine import Engine


metadata = MetaData()


jobs = Table(
    "jobs",
    metadata,
    Column("trace_id", String(64), primary_key=True),
    Column("task_type", String(64), nullable=False),
    Column("status", String(32), nullable=False, default="init"),
    Column("requested_limit", Integer, nullable=False, default=5),
    Column("metadata_json", Text, nullable=False, default="{}"),
    Column("context_json", Text, nullable=False, default="{}"),
    Column("created_at_unix", Integer, nullable=False, default=lambda: int(time.time())),
    Column("updated_at_unix", Integer, nullable=False, default=lambda: int(time.time())),
)

work_items = Table(
    "work_items",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trace_id", String(64), nullable=False),
    Column("work_key", String(128), nullable=False),
    Column("stage", String(64), nullable=False, default="init"),
    Column("status", String(32), nullable=False, default="PENDING"),
    Column("attempt", Integer, nullable=False, default=0),
    Column("next_run_at_unix", Integer, nullable=True),
    Column("last_error", Text, nullable=True),
    Column("stage_output_refs_json", Text, nullable=False, default="{}"),
    Column("created_at_unix", Integer, nullable=False, default=lambda: int(time.time())),
    Column("updated_at_unix", Integer, nullable=False, default=lambda: int(time.time())),
)


artifacts_index = Table(
    "artifacts_index",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trace_id", String(64), nullable=False),
    Column("work_key", String(128), nullable=True),
    Column("name", String(128), nullable=False),
    Column("ref_json", Text, nullable=False),
    Column("created_at_unix", Integer, nullable=False, default=lambda: int(time.time())),
)


inbox_events = Table(
    "inbox_events",
    metadata,
    Column("event_id", String(128), primary_key=True),
    Column("trace_id", String(64), nullable=False),
    Column("received_at_unix", Integer, nullable=False, default=lambda: int(time.time())),
)


outbox_events = Table(
    "outbox_events",
    metadata,
    Column("event_id", String(128), primary_key=True),
    Column("routing_key", String(256), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("status", String(32), nullable=False, default="PENDING"),
    Column("created_at_unix", Integer, nullable=False, default=lambda: int(time.time())),
)


@dataclass
class OrchestrationDB:
    engine: Engine

    @classmethod
    def from_url(cls, url: str) -> "OrchestrationDB":
        engine = create_engine(url, pool_pre_ping=True, future=True)
        return cls(engine=engine)

    def init_schema(self) -> None:
        # Deprecated in P0: schema changes must be applied via Alembic migrations job.
        metadata.create_all(self.engine)

    # ---- jobs ----
    def get_job_row(self, trace_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.begin() as conn:
            row = conn.execute(select(jobs).where(jobs.c.trace_id == trace_id)).mappings().fetchone()
            return dict(row) if row else None

    # ---- work items ----
    def list_work_items(self, trace_id: str) -> list[Dict[str, Any]]:
        with self.engine.begin() as conn:
            rows = conn.execute(select(work_items).where(work_items.c.trace_id == trace_id).order_by(work_items.c.id)).mappings().all()
            return [dict(r) for r in rows]

    def upsert_work_item(
        self,
        *,
        trace_id: str,
        work_key: str,
        stage: str,
        status: str,
        attempt: int = 0,
        next_run_at_unix: Optional[int] = None,
        last_error: Optional[str] = None,
        stage_output_refs: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = int(time.time())
        refs_raw = json.dumps(stage_output_refs or {}, ensure_ascii=False)
        with self.engine.begin() as conn:
            existing = conn.execute(
                select(work_items.c.id).where(
                    (work_items.c.trace_id == trace_id) & (work_items.c.work_key == work_key)
                )
            ).fetchone()
            if existing:
                conn.execute(
                    update(work_items)
                    .where((work_items.c.trace_id == trace_id) & (work_items.c.work_key == work_key))
                    .values(
                        stage=stage,
                        status=status,
                        attempt=attempt,
                        next_run_at_unix=next_run_at_unix,
                        last_error=last_error,
                        stage_output_refs_json=refs_raw,
                        updated_at_unix=now,
                    )
                )
            else:
                conn.execute(
                    insert(work_items).values(
                        trace_id=trace_id,
                        work_key=work_key,
                        stage=stage,
                        status=status,
                        attempt=attempt,
                        next_run_at_unix=next_run_at_unix,
                        last_error=last_error,
                        stage_output_refs_json=refs_raw,
                        created_at_unix=now,
                        updated_at_unix=now,
                    )
                )

    # ---- artifacts refs ----
    def list_artifact_refs(self, trace_id: str) -> list[Dict[str, Any]]:
        with self.engine.begin() as conn:
            rows = conn.execute(select(artifacts_index).where(artifacts_index.c.trace_id == trace_id).order_by(artifacts_index.c.id)).mappings().all()
            return [dict(r) for r in rows]

    def upsert_artifact_ref(self, *, trace_id: str, name: str, ref_obj: Dict[str, Any], work_key: Optional[str] = None) -> None:
        now = int(time.time())
        raw = json.dumps(ref_obj, ensure_ascii=False)
        with self.engine.begin() as conn:
            # keep last-write-wins: delete existing same key then insert
            conn.execute(
                artifacts_index.delete().where(
                    (artifacts_index.c.trace_id == trace_id)
                    & (artifacts_index.c.name == name)
                    & (artifacts_index.c.work_key == work_key)
                )
            )
            conn.execute(
                insert(artifacts_index).values(
                    trace_id=trace_id,
                    work_key=work_key,
                    name=name,
                    ref_json=raw,
                    created_at_unix=now,
                )
            )

    # ---- jobs/context ----
    def get_job_context_json(self, trace_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.begin() as conn:
            row = conn.execute(select(jobs.c.context_json).where(jobs.c.trace_id == trace_id)).fetchone()
            if not row:
                return None
            raw = row[0] or "{}"
            try:
                return json.loads(raw)
            except Exception:
                return None

    def upsert_job_context_json(
        self,
        *,
        trace_id: str,
        task_type: str,
        requested_limit: int,
        metadata_obj: Dict[str, Any],
        context_obj: Dict[str, Any],
    ) -> None:
        now = int(time.time())
        ctx_raw = json.dumps(context_obj, ensure_ascii=False)
        meta_raw = json.dumps(metadata_obj, ensure_ascii=False)
        with self.engine.begin() as conn:
            exists = conn.execute(select(jobs.c.trace_id).where(jobs.c.trace_id == trace_id)).fetchone()
            if exists:
                conn.execute(
                    update(jobs)
                    .where(jobs.c.trace_id == trace_id)
                    .values(
                        task_type=task_type,
                        requested_limit=requested_limit,
                        metadata_json=meta_raw,
                        context_json=ctx_raw,
                        updated_at_unix=now,
                    )
                )
            else:
                conn.execute(
                    insert(jobs).values(
                        trace_id=trace_id,
                        task_type=task_type,
                        status=context_obj.get("current_stage", "init"),
                        requested_limit=requested_limit,
                        metadata_json=meta_raw,
                        context_json=ctx_raw,
                        created_at_unix=now,
                        updated_at_unix=now,
                    )
                )

    def update_job_context_json(self, trace_id: str, context_obj: Dict[str, Any]) -> None:
        now = int(time.time())
        ctx_raw = json.dumps(context_obj, ensure_ascii=False)
        status = str(context_obj.get("current_stage") or "init")
        with self.engine.begin() as conn:
            conn.execute(
                update(jobs)
                .where(jobs.c.trace_id == trace_id)
                .values(context_json=ctx_raw, status=status, updated_at_unix=now)
            )


