"""RabbitMQ worker for parser-service (`cmd.parser.start`)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from typing import Any, Dict

import aio_pika
from aio_pika import ExchangeType, DeliveryMode, Message
import httpx
from PyPDF2 import PdfReader

from app.settings import settings
from app.db import ParserDB


def _ensure_nexus_sdk_on_path() -> None:
    # Needed for migration: read legacy MinIO claimcheck keys.
    import sys

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    p = os.path.join(root, "nexus_sdk")
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)


_ensure_nexus_sdk_on_path()

from nexus_sdk.common import MockStorage  # noqa: E402


db = ParserDB.from_url(settings.database_url)
# P0: schema must be managed by Alembic migrations job, not at runtime.


def _mk_pkg(trace_id: str, task_type: str, sender: str, payload: Dict[str, Any]) -> bytes:
    pkg = {
        "header": {"trace_id": trace_id, "task_type": task_type, "sender": sender, "timestamp": time.time()},
        "payload": payload,
    }
    return json.dumps(pkg, ensure_ascii=False).encode("utf-8")


async def _publish_evt(channel: aio_pika.abc.AbstractChannel, routing_key: str, body: bytes) -> None:
    ex = await channel.declare_exchange(settings.evt_exchange, ExchangeType.TOPIC, durable=True)
    await ex.publish(
        Message(body=body, delivery_mode=DeliveryMode.PERSISTENT, content_type="application/json"),
        routing_key=routing_key,
    )


async def _get_signed_url(file_id: str) -> str:
    path = settings.download_signed_url_path_tpl.format(file_id=file_id)
    url = settings.download_base_url.rstrip("/") + path
    async with httpx.AsyncClient(timeout=settings.http_timeout, trust_env=False) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()
        return str(data.get("url") or "")


def _parse_pdf_bytes(pdf_bytes: bytes) -> Dict[str, Any]:
    reader = PdfReader(stream=pdf_bytes)
    chunks = []
    full_text_parts = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text = text.strip()
        if not text:
            continue
        full_text_parts.append(text)
        chunks.append(
            {
                "chunk_id": f"p{i}",
                "text": text,
                "page": i + 1,
            }
        )
    full_text = "\n\n".join(full_text_parts)
    sha = hashlib.sha256(full_text.encode("utf-8", errors="ignore")).hexdigest()
    return {"chunks": chunks, "fulltext_hash": sha, "page_count": len(reader.pages)}


async def _handle_cmd(msg: aio_pika.IncomingMessage, channel: aio_pika.abc.AbstractChannel) -> None:
    async with msg.process():
        t0 = time.monotonic()
        body = json.loads(msg.body.decode("utf-8"))
        header = body.get("header") or {}
        payload = body.get("payload") or {}

        trace_id = str(header.get("trace_id") or "")
        task_type = str(header.get("task_type") or "parser")
        task_id = str(payload.get("task_id") or trace_id)
        work_key = payload.get("work_key") or (task_id if task_id != trace_id else None)
        idempotency_key = str(payload.get("idempotency_key") or f"{settings.cmd_routing_key}:{trace_id}:{work_key or trace_id}")

        if not await asyncio.to_thread(db.record_inbox, event_id=idempotency_key, routing_key=settings.cmd_routing_key, trace_id=trace_id):
            return

        # Ref-only: must be file_ref
        input_ref = payload.get("input_ref") or {}
        if not isinstance(input_ref, dict) or input_ref.get("type") != "file" or not input_ref.get("id"):
            raise ValueError("ref-only: cmd.parser.start requires input_ref.type=file with id")
        file_id = str(input_ref.get("id") or "")

        # Download PDF bytes via download-service signed URL
        signed_url = await _get_signed_url(file_id)
        if not signed_url:
            raise RuntimeError("download-service signed_url empty")

        async with httpx.AsyncClient(timeout=settings.http_timeout, trust_env=False) as client:
            r = await client.get(signed_url)
            r.raise_for_status()
            pdf_bytes = r.content

        parsed = _parse_pdf_bytes(pdf_bytes)
        # doc_id stable derived from file_id
        doc_id = hashlib.sha256(file_id.encode("utf-8")).hexdigest()[:32]

        output_key = f"parser/parsed/{doc_id}.json"
        payload_obj = {
            "doc_id": doc_id,
            "file_id": file_id,
            "chunks": parsed.get("chunks") or [],
            "fulltext_hash": parsed.get("fulltext_hash"),
            "meta": {"page_count": parsed.get("page_count"), "source": "parser_service"},
        }

        try:
            await MockStorage.save(output_key, payload_obj)
            await asyncio.to_thread(db.put_doc, doc_id=doc_id, file_id=file_id, output_key=output_key)

            evt_rk = "evt.parser.finished"
            evt_id = f"{evt_rk}:{trace_id}:{work_key or trace_id}"
            evt_payload = {
                "status": "SUCCESS",
                "version": "v1",
                "event": evt_rk,
                "trace_id": trace_id,
                "work_key": work_key,
                "result_ref": {"service": "parser", "type": "parsed_doc", "id": doc_id, "version": "v1"},
                "metrics": {"duration_ms": int((time.monotonic() - t0) * 1000), "pdf_bytes": len(pdf_bytes)},
            }
            await asyncio.to_thread(db.add_outbox, event_id=evt_id, routing_key=evt_rk, payload=evt_payload)
        except Exception as e:
            evt_rk = "evt.parser.failed"
            evt_id = f"{evt_rk}:{trace_id}:{work_key or trace_id}"
            evt_payload = {
                "status": "FAIL",
                "version": "v1",
                "event": evt_rk,
                "trace_id": trace_id,
                "work_key": work_key,
                "result_ref": {"service": "parser", "type": "error", "id": evt_id, "version": "v1"},
                "error": {"code": "PARSER_FAILED", "message": str(e), "details": {}},
            }
            await asyncio.to_thread(db.add_outbox, event_id=evt_id, routing_key=evt_rk, payload=evt_payload)
            raise


async def main() -> None:
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=int(os.getenv("NEXUS_PREFETCH", "4")))

    cmd_ex = await channel.declare_exchange(settings.cmd_exchange, ExchangeType.DIRECT, durable=True)
    queue = await channel.declare_queue(settings.queue_name, durable=True)
    await queue.bind(cmd_ex, routing_key=settings.cmd_routing_key)

    async def _publisher_loop() -> None:
        while True:
            pending = await asyncio.to_thread(db.list_outbox_pending, limit=20)
            if not pending:
                await asyncio.sleep(0.2)
                continue
            for ev in pending:
                event_id = str(ev.get("event_id") or "")
                routing_key = str(ev.get("routing_key") or "")
                raw = str(ev.get("payload_json") or "{}")
                try:
                    payload = json.loads(raw)
                    trace_id = str(payload.get("trace_id") or "")
                    body = _mk_pkg(trace_id, "parser", "parser", payload)
                    await _publish_evt(channel, routing_key, body)
                    await asyncio.to_thread(db.mark_outbox_published, event_id=event_id)
                except Exception as e:
                    await asyncio.to_thread(db.mark_outbox_failed, event_id=event_id, err=str(e))

    asyncio.create_task(_publisher_loop())

    await queue.consume(lambda m: _handle_cmd(m, channel))
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())


