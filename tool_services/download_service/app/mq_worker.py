"""RabbitMQ worker for `cmd.downloader.start` (strict microservices migration).

This worker allows Nexus orchestrator to trigger downloads via MQ directly,
without relying on the legacy `download_tool` adapter.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional, Tuple

import aio_pika
from aio_pika import ExchangeType, DeliveryMode, Message
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import SessionLocal
from app.models.task import DownloadTask, TaskStatus
from app.models.file import DocumentFile
from app.models.mq_events import InboxEvent, OutboxEvent, OutboxStatus
from app.services.validator import URLValidator
from app.services.downloader import PDFDownloader
from app.services.storage import MinIOStorage
from app.config import settings


logger = logging.getLogger(__name__)


CMD_EXCHANGE = os.getenv("NEXUS_CMD_EXCHANGE", "nexus.cmd.exchange")
EVT_EXCHANGE = os.getenv("NEXUS_EVT_EXCHANGE", "nexus.evt.exchange")
RABBIT_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
CMD_ROUTING_KEY = os.getenv("DOWNLOAD_CMD_ROUTING_KEY", "cmd.downloader.start")
QUEUE_NAME = os.getenv("DOWNLOAD_CMD_QUEUE", "q.download.worker")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _extract_url(payload: Dict[str, Any], _db: Session) -> str:
    """Ref-only: URL comes from input_ref.fetch.url (preferred) or params.url."""
    input_ref = payload.get("input_ref") or {}
    if isinstance(input_ref, dict):
        fetch = input_ref.get("fetch") or {}
        if isinstance(fetch, dict):
            u = str(fetch.get("url") or "").strip()
            if u:
                return u
    params = payload.get("params") or {}
    if isinstance(params, dict):
        u2 = str(params.get("url") or "").strip()
        if u2:
            return u2
    return ""


def _mk_event(trace_id: str, task_type: str, sender: str, payload: Dict[str, Any]) -> bytes:
    pkg = {
        "header": {"trace_id": trace_id, "task_type": task_type, "sender": sender, "timestamp": time.time()},
        "payload": payload,
    }
    return json.dumps(pkg, ensure_ascii=False).encode("utf-8")


async def _publish_event(channel: aio_pika.abc.AbstractChannel, routing_key: str, body: bytes) -> None:
    ex = await channel.declare_exchange(EVT_EXCHANGE, ExchangeType.TOPIC, durable=True)
    await ex.publish(
        Message(body=body, delivery_mode=DeliveryMode.PERSISTENT, content_type="application/json"),
        routing_key=routing_key,
    )


def _ensure_inbox(db: Session, inbox_id: str, routing_key: str, trace_id: str) -> bool:
    """Return True if this is a new message, False if already processed."""
    if db.query(InboxEvent).filter(InboxEvent.id == inbox_id).first():
        return False
    db.add(InboxEvent(id=inbox_id, routing_key=routing_key, trace_id=trace_id))
    db.commit()
    return True


def _create_outbox(db: Session, routing_key: str, payload: Dict[str, Any]) -> OutboxEvent:
    trace_id = str(payload.get("trace_id") or "")
    work_key = str(payload.get("work_key") or trace_id)
    event_id = f"{routing_key}:{trace_id}:{work_key}"
    ev = OutboxEvent(
        event_id=event_id,
        routing_key=routing_key,
        payload_json=json.dumps(payload, ensure_ascii=False),
        status=OutboxStatus.PENDING,
    )
    db.add(ev)
    return ev


def _mark_outbox_published(db: Session, ev: OutboxEvent) -> None:
    ev.status = OutboxStatus.PUBLISHED
    ev.published_at = datetime.utcnow()
    db.add(ev)


def _mark_outbox_failed(db: Session, ev: OutboxEvent, err: str) -> None:
    ev.status = OutboxStatus.FAILED
    ev.last_error = (err or "")[:2000]
    db.add(ev)


def _get_pending_outbox(db: Session, limit: int = 50) -> list[OutboxEvent]:
    return (
        db.query(OutboxEvent)
        .filter(OutboxEvent.status == OutboxStatus.PENDING)
        .order_by(OutboxEvent.created_at.asc())
        .limit(limit)
        .all()
    )


async def _handle_cmd(message: aio_pika.IncomingMessage, channel: aio_pika.abc.AbstractChannel) -> None:
    async with message.process():
        t0 = time.monotonic()
        body = json.loads(message.body.decode("utf-8"))
        header = body.get("header") or {}
        payload = body.get("payload") or {}

        trace_id = str(header.get("trace_id") or "")
        task_type = str(header.get("task_type") or "downloader")
        task_id = str(payload.get("task_id") or trace_id or uuid.uuid4())
        work_key = payload.get("work_key") or (task_id if task_id != trace_id else None)
        inbox_id = str(payload.get("idempotency_key") or f"{CMD_ROUTING_KEY}:{trace_id}:{task_id}")

        db = SessionLocal()
        try:
            if not _ensure_inbox(db, inbox_id=inbox_id, routing_key=CMD_ROUTING_KEY, trace_id=trace_id):
                logger.info("cmd.dedup.skip", extra={"trace_id": trace_id, "task_id": task_id})
                return

            url = _extract_url(payload, db)
            if not url:
                raise ValueError("ref-only: missing url in input_ref.fetch.url or params.url")

            # Validate + download (outside DB tx)
            validator = URLValidator()
            ok, err = await validator.is_reachable(url)
            if not ok:
                raise ValueError(f"url not reachable: {err}")

            downloader = PDFDownloader()
            content, filename = await downloader.download(url)
            file_size = len(content)

            storage = MinIOStorage(
                endpoint=settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                bucket=settings.minio_bucket,
                secure=settings.minio_secure,
                external_endpoint=settings.minio_external_endpoint,
                region=settings.aws_region,
            )

            # Isolated prefix for strict microservices; default to "download/"
            prefix = (os.getenv("DOWNLOAD_MINIO_PREFIX") or "download/").strip().lstrip("/")

            # Transaction: write business rows + outbox together
            with db.begin():
                task = DownloadTask(url=url, status=TaskStatus.PENDING)
                db.add(task)
                db.flush()

                object_name = f"{prefix}{task.id}/{filename}"

                def _put() -> str:
                    from io import BytesIO

                    storage.ensure_bucket_exists()
                    storage.client.put_object(
                        bucket_name=settings.minio_bucket,
                        object_name=object_name,
                        data=BytesIO(content),
                        length=len(content),
                        content_type="application/pdf",
                    )
                    return object_name

                object_name_uploaded = await asyncio.to_thread(_put)

                doc_file = DocumentFile(
                    file_name=filename,
                    minio_bucket=settings.minio_bucket,
                    minio_object=object_name_uploaded,
                    mime_type="application/pdf",
                    file_size=file_size,
                )
                db.add(doc_file)
                db.flush()

                task.status = TaskStatus.SUCCESS
                task.file_id = doc_file.id

                file_ref = {"service": "download", "type": "file", "id": str(doc_file.id), "version": "v1"}
                evt_payload = {
                    "status": "SUCCESS",
                    "version": "v1",
                    "event": "evt.downloader.finished",
                    "trace_id": trace_id,
                    "work_key": work_key,
                    "result_ref": file_ref,
                    "metrics": {"duration_ms": int((time.monotonic() - t0) * 1000), "file_size": file_size},
                }
                _create_outbox(db, routing_key="evt.downloader.finished", payload=evt_payload)
        except Exception as e:
            logger.exception("cmd.download.failed", extra={"trace_id": trace_id})
            err_payload = {
                "status": "FAIL",
                "version": "v1",
                "event": "evt.downloader.failed",
                "trace_id": trace_id,
                "work_key": work_key,
                "error_msg": str(e),
                "error": {"code": "DOWNLOAD_FAILED", "message": str(e)},
            }
            try:
                with db.begin():
                    _create_outbox(db, routing_key="evt.downloader.failed", payload=err_payload)
            except Exception:
                pass
            raise
        finally:
            db.close()


async def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    connection = await aio_pika.connect_robust(RABBIT_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=int(os.getenv("NEXUS_PREFETCH", "4")))

    cmd_ex = await channel.declare_exchange(CMD_EXCHANGE, ExchangeType.DIRECT, durable=True)
    queue = await channel.declare_queue(QUEUE_NAME, durable=True)
    await queue.bind(cmd_ex, routing_key=CMD_ROUTING_KEY)

    logger.info("download.mq_worker.started", extra={"queue": QUEUE_NAME, "routing_key": CMD_ROUTING_KEY})

    async def _publisher_loop() -> None:
        """Publish pending outbox events with retry on restart."""
        while True:
            db = SessionLocal()
            try:
                pending = _get_pending_outbox(db, limit=20)
                if not pending:
                    await asyncio.sleep(0.2)
                    continue
                for ev in pending:
                    try:
                        payload = json.loads(ev.payload_json)
                        body = _mk_event(str(payload.get("trace_id") or ""), "downloader", "downloader", payload)
                        await _publish_event(channel, ev.routing_key, body)
                        with db.begin():
                            _mark_outbox_published(db, ev)
                    except Exception as e:
                        with db.begin():
                            _mark_outbox_failed(db, ev, str(e))
            finally:
                db.close()

    asyncio.create_task(_publisher_loop())

    await queue.consume(lambda msg: _handle_cmd(msg, channel))
    # run forever
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())


