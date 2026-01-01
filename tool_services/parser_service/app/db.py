from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy import Column, Integer, MetaData, String, Table, Text, create_engine, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine


metadata = MetaData()

parsed_docs = Table(
    "parsed_docs",
    metadata,
    Column("doc_id", String(64), primary_key=True),
    Column("file_id", String(64), nullable=True),
    Column("output_key", Text, nullable=False),
    Column("created_at_unix", Integer, nullable=False, default=lambda: int(time.time())),
)

inbox_events = Table(
    "inbox_events",
    metadata,
    Column("event_id", String(256), primary_key=True),
    Column("routing_key", String(256), nullable=False),
    Column("trace_id", String(64), nullable=False),
    Column("received_at_unix", Integer, nullable=False, default=lambda: int(time.time())),
)

outbox_events = Table(
    "outbox_events",
    metadata,
    Column("event_id", String(256), primary_key=True),
    Column("routing_key", String(256), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("status", String(32), nullable=False, default="PENDING"),
    Column("created_at_unix", Integer, nullable=False, default=lambda: int(time.time())),
    Column("published_at_unix", Integer, nullable=True),
    Column("last_error", Text, nullable=True),
)


@dataclass
class ParserDB:
    engine: Engine

    @classmethod
    def from_url(cls, url: str) -> "ParserDB":
        return cls(engine=create_engine(url, pool_pre_ping=True, future=True))

    def init_schema(self) -> None:
        # Deprecated in P0: schema changes must be applied via Alembic migrations job.
        metadata.create_all(self.engine)

    def put_doc(self, *, doc_id: str, file_id: str, output_key: str) -> None:
        with self.engine.begin() as conn:
            stmt = pg_insert(parsed_docs).values(
                doc_id=doc_id,
                file_id=file_id or None,
                output_key=output_key,
                created_at_unix=int(time.time()),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[parsed_docs.c.doc_id],
                set_={"file_id": file_id or None, "output_key": output_key, "created_at_unix": int(time.time())},
            )
            conn.execute(stmt)

    def get_output_key(self, doc_id: str) -> Optional[str]:
        with self.engine.begin() as conn:
            row = conn.execute(select(parsed_docs.c.output_key).where(parsed_docs.c.doc_id == doc_id)).fetchone()
            if not row:
                return None
            return str(row[0])

    def record_inbox(self, *, event_id: str, routing_key: str, trace_id: str) -> bool:
        with self.engine.begin() as conn:
            row = conn.execute(select(inbox_events.c.event_id).where(inbox_events.c.event_id == event_id)).fetchone()
            if row:
                return False
            conn.execute(
                insert(inbox_events).values(
                    event_id=event_id,
                    routing_key=routing_key,
                    trace_id=trace_id,
                    received_at_unix=int(time.time()),
                )
            )
            return True

    def add_outbox(self, *, event_id: str, routing_key: str, payload: Dict[str, Any]) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                insert(outbox_events).values(
                    event_id=event_id,
                    routing_key=routing_key,
                    payload_json=json.dumps(payload, ensure_ascii=False),
                    status="PENDING",
                    created_at_unix=int(time.time()),
                )
            )

    def list_outbox_pending(self, *, limit: int = 50) -> list[Dict[str, Any]]:
        with self.engine.begin() as conn:
            rows = (
                conn.execute(
                    select(outbox_events)
                    .where(outbox_events.c.status == "PENDING")
                    .order_by(outbox_events.c.created_at_unix.asc())
                    .limit(limit)
                )
                .mappings()
                .all()
            )
            return [dict(r) for r in rows]

    def mark_outbox_published(self, *, event_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                update(outbox_events)
                .where(outbox_events.c.event_id == event_id)
                .values(status="PUBLISHED", published_at_unix=int(time.time()))
            )

    def mark_outbox_failed(self, *, event_id: str, err: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                update(outbox_events)
                .where(outbox_events.c.event_id == event_id)
                .values(status="FAILED", last_error=(err or "")[:2000])
            )


