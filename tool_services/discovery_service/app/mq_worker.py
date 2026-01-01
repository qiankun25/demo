from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional

import aio_pika
from aio_pika import ExchangeType, DeliveryMode, Message

from app.db import DiscoveryDB

logger = logging.getLogger(__name__)


CMD_EXCHANGE = os.getenv("NEXUS_CMD_EXCHANGE", "nexus.cmd.exchange")
EVT_EXCHANGE = os.getenv("NEXUS_EVT_EXCHANGE", "nexus.evt.exchange")
RABBIT_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

CMD_ROUTING_KEY = os.getenv("DISCOVERY_CMD_ROUTING_KEY", "cmd.discovery.start")
QUEUE_NAME = os.getenv("DISCOVERY_CMD_QUEUE", "q.discovery.worker")


def _mk_pkg(trace_id: str, task_type: str, sender: str, payload: Dict[str, Any]) -> bytes:
    pkg = {
        "header": {"trace_id": trace_id, "task_type": task_type, "sender": sender, "timestamp": time.time()},
        "payload": payload,
    }
    return json.dumps(pkg, ensure_ascii=False).encode("utf-8")


class MQWorker:
    def __init__(self, db: DiscoveryDB):
        self.db = db

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
                pending = await asyncio.to_thread(self.db.list_outbox_pending, limit=20)
                if not pending:
                    await asyncio.sleep(0.2)
                    continue
                for ev in pending:
                    payload = json.loads(str(ev.get("payload_json") or "{}"))
                    trace_id = str(payload.get("trace_id") or "")
                    body = _mk_pkg(trace_id=trace_id, task_type="discovery", sender="discovery", payload=payload)
                    await evt_ex.publish(
                        Message(body=body, delivery_mode=DeliveryMode.PERSISTENT, content_type="application/json"),
                        routing_key=str(ev.get("routing_key") or "evt.discovery.finished"),
                    )
                    await asyncio.to_thread(self.db.mark_outbox_published, event_id=str(ev.get("event_id")))

        pub_task = asyncio.create_task(_publisher_loop())

        async with q.iterator() as it:
            async for msg in it:
                async with msg.process():
                    body = json.loads(msg.body.decode("utf-8"))
                    header = body.get("header") or {}
                    payload = body.get("payload") or {}
                    trace_id = str(header.get("trace_id") or "")
                    task_id = str(payload.get("task_id") or trace_id)
                    work_key = payload.get("work_key") or (task_id if task_id != trace_id else None)
                    idem = str(payload.get("idempotency_key") or f"{CMD_ROUTING_KEY}:{trace_id}:{task_id}")

                    if not await asyncio.to_thread(
                        self.db.record_inbox, event_id=idem, routing_key=CMD_ROUTING_KEY, trace_id=trace_id
                    ):
                        logger.info("duplicate_cmd_skip", extra={"trace_id": trace_id, "idempotency_key": idem})
                        continue

                    try:
                        input_ref = payload.get("input_ref") or {}
                        params = payload.get("params") or {}
                        if not isinstance(input_ref, dict) or not input_ref:
                            raise ValueError("ref-only: missing input_ref")

                        # Reuse discovery logic
                        from nexus_tool.tool_service import DiscoveryToolService  # local import

                        svc = DiscoveryToolService()
                        result_ref, metrics = await svc.do_work(input_ref, params if isinstance(params, dict) else {})

                        evt_rk = "evt.discovery.finished"
                        evt_id = f"{evt_rk}:{trace_id}:{work_key or trace_id}"
                        evt_payload = {
                            "status": "SUCCESS",
                            "version": "v1",
                            "event": evt_rk,
                            "trace_id": trace_id,
                            "work_key": work_key,
                            "result_ref": result_ref,
                            "metrics": metrics or {},
                        }
                        await asyncio.to_thread(self.db.add_outbox, event_id=evt_id, routing_key=evt_rk, payload=evt_payload)
                    except Exception as e:
                        evt_rk = "evt.discovery.failed"
                        evt_id = f"{evt_rk}:{trace_id}:{work_key or trace_id}"
                        evt_payload = {
                            "status": "FAIL",
                            "version": "v1",
                            "event": evt_rk,
                            "trace_id": trace_id,
                            "work_key": work_key,
                            "result_ref": {"service": "discovery", "type": "error", "id": evt_id, "version": "v1"},
                            "error": {"code": "DISCOVERY_FAILED", "message": str(e), "details": {}},
                        }
                        await asyncio.to_thread(self.db.add_outbox, event_id=evt_id, routing_key=evt_rk, payload=evt_payload)

        pub_task.cancel()


