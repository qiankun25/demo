from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional

import aio_pika
from aio_pika import ExchangeType, DeliveryMode, Message
import httpx
import chromadb

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.mq_events import InboxEvent, OutboxEvent
from app.services.indexer import IndexerService
from app.schemas.api_models import IndexRequest, DocIn, ChunkIn

logger = logging.getLogger(__name__)


CMD_EXCHANGE = os.getenv("NEXUS_CMD_EXCHANGE", "nexus.cmd.exchange")
EVT_EXCHANGE = os.getenv("NEXUS_EVT_EXCHANGE", "nexus.evt.exchange")
RABBIT_URL = os.getenv("RABBITMQ_URL", settings.RABBITMQ_URL)

CMD_ROUTING_KEY = os.getenv("INDEX_CMD_ROUTING_KEY", "cmd.indexer.start")
QUEUE_NAME = os.getenv("INDEX_CMD_QUEUE", "q.index.worker")


def _mk_pkg(trace_id: str, task_type: str, sender: str, payload: Dict[str, Any]) -> bytes:
    pkg = {
        "header": {"trace_id": trace_id, "task_type": task_type, "sender": sender, "timestamp": time.time()},
        "payload": payload,
    }
    return json.dumps(pkg, ensure_ascii=False).encode("utf-8")


class MQWorker:
    def __init__(self) -> None:
        os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        self.collection = self.chroma_client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION,
            metadata={"hnsw:space": settings.CHROMA_DISTANCE},
        )
        self.indexer = IndexerService(self.chroma_client, self.collection)

    async def run(self) -> None:
        conn = await aio_pika.connect_robust(RABBIT_URL)
        channel = await conn.channel()
        await channel.set_qos(prefetch_count=int(os.getenv("NEXUS_PREFETCH", "4")))

        cmd_ex = await channel.declare_exchange(CMD_EXCHANGE, ExchangeType.DIRECT, durable=True)
        evt_ex = await channel.declare_exchange(EVT_EXCHANGE, ExchangeType.TOPIC, durable=True)

        q = await channel.declare_queue(QUEUE_NAME, durable=True)
        await q.bind(cmd_ex, routing_key=CMD_ROUTING_KEY)

        async def _publisher_loop() -> None:
            while True:
                db = SessionLocal()
                try:
                    pending = (
                        db.query(OutboxEvent)
                        .filter(OutboxEvent.status == "PENDING")
                        .order_by(OutboxEvent.created_at_unix.asc())
                        .limit(20)
                        .all()
                    )
                    if not pending:
                        await asyncio.sleep(0.2)
                        continue
                    for ev in pending:
                        try:
                            payload = json.loads(ev.payload_json)
                            trace_id = str(payload.get("trace_id") or "")
                            body = _mk_pkg(trace_id, "indexer", "indexing", payload)
                            await evt_ex.publish(
                                Message(body=body, delivery_mode=DeliveryMode.PERSISTENT, content_type="application/json"),
                                routing_key=ev.routing_key,
                            )
                            ev.status = "PUBLISHED"
                            ev.published_at_unix = int(time.time())
                            db.add(ev)
                            db.commit()
                        except Exception as e:
                            ev.status = "FAILED"
                            ev.last_error = (str(e) or "")[:2000]
                            db.add(ev)
                            db.commit()
                finally:
                    db.close()

        asyncio.create_task(_publisher_loop())

        async with q.iterator() as it:
            async for msg in it:
                async with msg.process():
                    body = json.loads(msg.body.decode("utf-8"))
                    header = body.get("header") or {}
                    payload = body.get("payload") or {}
                    trace_id = str(header.get("trace_id") or "")
                    task_id = str(payload.get("task_id") or trace_id)
                    work_key = payload.get("work_key") or (task_id if task_id != trace_id else None)
                    idem = str(payload.get("idempotency_key") or f"{CMD_ROUTING_KEY}:{trace_id}:{work_key or trace_id}")

                    db = SessionLocal()
                    try:
                        if db.query(InboxEvent).filter(InboxEvent.event_id == idem).first():
                            continue
                        db.add(InboxEvent(event_id=idem, routing_key=CMD_ROUTING_KEY, trace_id=trace_id))
                        db.commit()

                        input_ref = payload.get("input_ref") or {}
                        if not isinstance(input_ref, dict) or input_ref.get("type") != "parsed_doc" or not input_ref.get("id"):
                            raise ValueError("ref-only: cmd.indexer.start requires input_ref.type=parsed_doc with id")
                        doc_id = str(input_ref.get("id"))

                        base = os.getenv("INDEX_PARSER_BASE_URL", "http://localhost:8031").rstrip("/")
                        url = f"{base}/v1/parsed/{doc_id}"
                        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                            r = await client.get(url)
                            r.raise_for_status()
                            pdata = r.json()
                        parsed = pdata.get("data") if isinstance(pdata, dict) else None
                        if not isinstance(parsed, dict):
                            raise ValueError("parser_service returned invalid shape")

                        paper = (payload.get("params") or {}).get("paper") if isinstance(payload.get("params"), dict) else {}
                        if not isinstance(paper, dict):
                            paper = {}

                        chunks_data = parsed.get("chunks") or []
                        if not isinstance(chunks_data, list) or not chunks_data:
                            raise ValueError("missing chunks")

                        doc_in = DocIn(
                            doc_id=str(parsed.get("doc_id") or doc_id),
                            canonical_id=str(paper.get("canonical_id") or paper.get("openalex_id") or "") or None,
                            doc_type="paper",
                            title=str(paper.get("title") or "") or None,
                            authors=[str(a) for a in (paper.get("authors") or [])] if isinstance(paper.get("authors"), list) else [],
                            year=None,
                            pdf_object_key=None,
                            pdf_sha256=str(parsed.get("fulltext_hash") or "") or None,
                            extra={k: v for k, v in paper.items() if k in ["pdf_url", "doi", "publication_date"] and v},
                            created_at_unix=int(time.time()),
                        )

                        chunks_in = []
                        for c in chunks_data:
                            if not isinstance(c, dict):
                                continue
                            chunks_in.append(
                                ChunkIn(
                                    chunk_id=str(c.get("chunk_id") or ""),
                                    doc_id=str(parsed.get("doc_id") or doc_id),
                                    text=str(c.get("text") or ""),
                                    span={"page": c.get("page")} if c.get("page") is not None else None,
                                    section_path=str(c.get("section_path") or ""),
                                )
                            )

                        req = IndexRequest(doc=doc_in, chunks=chunks_in, upsert=True)
                        await self.indexer.index_document(db, req)

                        evt_rk = "evt.indexer.finished"
                        evt_payload = {
                            "status": "SUCCESS",
                            "version": "v1",
                            "event": evt_rk,
                            "trace_id": trace_id,
                            "work_key": work_key,
                            "result_ref": {"service": "indexing", "type": "index_record", "id": str(doc_in.doc_id), "version": "v1"},
                            "metrics": {"chunk_count": len(chunks_in)},
                        }
                        event_id = f"{evt_rk}:{trace_id}:{work_key or trace_id}"
                        db.add(
                            OutboxEvent(
                                event_id=event_id,
                                routing_key=evt_rk,
                                payload_json=json.dumps(evt_payload, ensure_ascii=False),
                                status="PENDING",
                                created_at_unix=int(time.time()),
                            )
                        )
                        db.commit()
                    except Exception as e:
                        evt_rk = "evt.indexer.failed"
                        evt_payload = {
                            "status": "FAIL",
                            "version": "v1",
                            "event": evt_rk,
                            "trace_id": trace_id,
                            "work_key": work_key,
                            "result_ref": {"service": "indexing", "type": "error", "id": f"{evt_rk}:{trace_id}:{work_key or trace_id}", "version": "v1"},
                            "error": {"code": "INDEX_FAILED", "message": str(e), "details": {}},
                        }
                        try:
                            event_id = f"{evt_rk}:{trace_id}:{work_key or trace_id}"
                            db.add(
                                OutboxEvent(
                                    event_id=event_id,
                                    routing_key=evt_rk,
                                    payload_json=json.dumps(evt_payload, ensure_ascii=False),
                                    status="PENDING",
                                    created_at_unix=int(time.time()),
                                )
                            )
                            db.commit()
                        except Exception:
                            pass
                        raise
                    finally:
                        db.close()


