import asyncio
import json
import traceback
import time
import os
import aio_pika
from aio_pika import ExchangeType, DeliveryMode, Message

# 导入包内的 common 模块
from .common import RabbitConfig, MessagePackage, MsgHeader, EventPayload, CommandPayload

class BaseToolService:
    def __init__(self, service_name: str, cmd_routing_key: str):
        self.service_name = service_name
        self.cmd_routing_key = cmd_routing_key
        self.connection = None
        self.channel = None
        self.queue_name = f"q.tool.{service_name}"

    async def start(self):
        print(f"[*] {self.service_name} Service Starting...")
        try:
            # 1. 连接
            self.connection = await aio_pika.connect_robust(RabbitConfig.URL)
            self.channel = await self.connection.channel()
            
            # QoS: 默认预取 1（可通过环境变量调整，减少 fan-out 堆积导致的 TTL/DLQ）
            try:
                prefetch = int(os.getenv("NEXUS_PREFETCH", "1"))
            except Exception:
                prefetch = 1
            prefetch = max(1, min(prefetch, 100))
            await self.channel.set_qos(prefetch_count=prefetch)

            # 2. 声明交换机
            cmd_exchange = await self.channel.declare_exchange(
                RabbitConfig.CMD_EXCHANGE, ExchangeType.DIRECT, durable=True
            )
            evt_exchange = await self.channel.declare_exchange(
                RabbitConfig.EVT_EXCHANGE, ExchangeType.TOPIC, durable=True
            )
            dlx_exchange = await self.channel.declare_exchange(
                RabbitConfig.DLX_EXCHANGE, ExchangeType.DIRECT, durable=True
            )

            # 3. 声明死信队列 (DLQ)
            dlq = await self.channel.declare_queue(RabbitConfig.DLQ_QUEUE, durable=True)
            await dlq.bind(dlx_exchange, routing_key=self.cmd_routing_key)

            # 4. 声明工作队列
            args = {
                'x-dead-letter-exchange': RabbitConfig.DLX_EXCHANGE,
                'x-dead-letter-routing-key': self.cmd_routing_key
            }
            # TTL<=0 视为禁用（避免消息在队列等待过久被死信，导致编排侧永远 pending）
            if int(getattr(RabbitConfig, "TTL_MS", 0) or 0) > 0:
                args['x-message-ttl'] = int(RabbitConfig.TTL_MS)
            queue = await self.channel.declare_queue(
                self.queue_name, durable=True, arguments=args
            )
            await queue.bind(cmd_exchange, routing_key=self.cmd_routing_key)

            print(f"[*] {self.service_name} Waiting for commands on '{self.cmd_routing_key}'...")

            # 5. 开始消费
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        await self._on_message(message)

        except asyncio.CancelledError:
            print(f"[*] {self.service_name} Service Stopped.")
        except Exception as e:
            # 过滤掉关闭时的噪音错误
            if "Channel closed by RPC timeout" in str(e):
                print(f"[*] {self.service_name} connection closed.")
            else:
                print(f"[FATAL] {self.service_name} crashed: {e}")
            
            if self.connection:
                await self.connection.close()

    async def _on_message(self, message: aio_pika.abc.AbstractIncomingMessage):
        """核心消息处理逻辑"""
        t0 = time.monotonic()
        try:
            # A. 反序列化
            body_str = message.body.decode()
            data = json.loads(body_str)
            pkg = MessagePackage(**data)
            cmd = CommandPayload(**pkg.payload)

            print(
                json.dumps(
                    {
                        "ts": time.time(),
                        "level": "INFO",
                        "svc": self.service_name,
                        "event": "cmd.received",
                        "trace_id": pkg.header.trace_id,
                        "task_type": pkg.header.task_type,
                        "sender": pkg.header.sender,
                        "task_id": cmd.task_id,
                        "input_key": cmd.input_key,
                        "params_keys": sorted(list((cmd.params or {}).keys())),
                    },
                    ensure_ascii=False,
                )
            )

            # B. 执行业务逻辑（ref-only）：必须基于 input_ref + params 产出 result_ref
            input_ref = cmd.input_ref or {}
            if not isinstance(input_ref, dict) or not input_ref:
                raise ValueError("ref-only: missing input_ref in command payload")

            result_ref, metrics = await self.do_work(input_ref, cmd.params or {})
            if not isinstance(result_ref, dict) or not result_ref.get("id") or not result_ref.get("type"):
                raise ValueError(f"invalid result_ref returned by do_work: {result_ref!r}")

            # C. 构建成功事件（ref-only：不再依赖 output_key）
            resp_payload = EventPayload(status="SUCCESS")
            resp_payload.version = "v1"
            resp_payload.event = f"evt.{self.service_name}.finished"
            resp_payload.trace_id = pkg.header.trace_id
            resp_payload.work_key = getattr(cmd, "work_key", None) or (
                cmd.task_id if cmd.task_id != pkg.header.trace_id else None
            )
            resp_payload.result_ref = result_ref
            resp_payload.metrics = metrics or {"duration_ms": int((time.monotonic() - t0) * 1000)}
            routing_key = f"evt.{self.service_name}.finished"

        except Exception as e:
            print(
                json.dumps(
                    {
                        "ts": time.time(),
                        "level": "ERROR",
                        "svc": self.service_name,
                        "event": "cmd.failed",
                        "trace_id": pkg.header.trace_id if "pkg" in locals() else None,
                        "task_type": pkg.header.task_type if "pkg" in locals() else None,
                        "task_id": cmd.task_id if "cmd" in locals() else None,
                        "input_key": cmd.input_key if "cmd" in locals() else None,
                        "error": str(e),
                    },
                    ensure_ascii=False,
                )
            )
            traceback.print_exc()
            # D. 构建失败事件
            if 'pkg' in locals():
                resp_payload = EventPayload(status="FAIL", error_msg=str(e))
                try:
                    resp_payload.version = "v1"
                    resp_payload.event = f"evt.{self.service_name}.failed"
                    resp_payload.trace_id = pkg.header.trace_id
                    resp_payload.work_key = getattr(cmd, "work_key", None) or (cmd.task_id if cmd.task_id != pkg.header.trace_id else None)
                    resp_payload.error = {"code": "EXCEPTION", "message": str(e)}
                except Exception:
                    pass
                routing_key = f"evt.{self.service_name}.failed"
            else:
                print("Could not deserialize message, sending to DLQ (handled by nack/reject implicitly if exception propagates)")
                raise e

        # E. 发布事件
        if 'pkg' in locals():
            await self._publish_event(pkg.header, resp_payload, routing_key)
            print(
                json.dumps(
                    {
                        "ts": time.time(),
                        "level": "INFO",
                        "svc": self.service_name,
                        "event": "evt.published",
                        "trace_id": pkg.header.trace_id,
                        "task_type": pkg.header.task_type,
                        "routing_key": routing_key,
                        "status": resp_payload.status,
                        "output_key": getattr(resp_payload, "output_key", None),
                        "input_key": getattr(resp_payload, "input_key", None),
                        "duration_ms": int((time.monotonic() - t0) * 1000),
                    },
                    ensure_ascii=False,
                )
            )

    async def _publish_event(self, req_header: MsgHeader, payload: EventPayload, routing_key: str):
        # 更新 Header
        new_header = req_header.model_copy()
        new_header.sender = self.service_name
        import time
        new_header.timestamp = time.time()

        resp_pkg = MessagePackage(header=new_header, payload=payload.model_dump())
        
        exchange = await self.channel.get_exchange(RabbitConfig.EVT_EXCHANGE)
        
        await exchange.publish(
            Message(
                body=resp_pkg.model_dump_json().encode(),
                delivery_mode=DeliveryMode.PERSISTENT
            ),
            routing_key=routing_key
        )
        print(f"[{self.service_name}] Sent Event: {routing_key}")

    async def do_work(self, input_ref: dict, params: dict) -> tuple[dict, dict]:
        """
        [抽象] 业务逻辑
        :return: (result_ref, metrics)
        """
        raise NotImplementedError
