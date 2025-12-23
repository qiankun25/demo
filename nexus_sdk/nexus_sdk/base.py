import asyncio
import json
import traceback
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
            
            # QoS: 预取 1
            await self.channel.set_qos(prefetch_count=1)

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
                'x-message-ttl': RabbitConfig.TTL_MS,
                'x-dead-letter-exchange': RabbitConfig.DLX_EXCHANGE,
                'x-dead-letter-routing-key': self.cmd_routing_key
            }
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
        try:
            # A. 反序列化
            body_str = message.body.decode()
            data = json.loads(body_str)
            pkg = MessagePackage(**data)
            cmd = CommandPayload(**pkg.payload)

            print(f"[{self.service_name}] Received Task: {pkg.header.trace_id}")

            # B. 执行业务逻辑 (抽象)
            output_key = await self.do_work(cmd.input_key, cmd.params)

            # C. 构建成功事件
            resp_payload = EventPayload(status="SUCCESS", output_key=output_key)
            routing_key = f"evt.{self.service_name}.finished"

        except Exception as e:
            print(f"[ERROR] {self.service_name} Failed: {e}")
            traceback.print_exc()
            # D. 构建失败事件
            if 'pkg' in locals():
                # 注意：失败事件也携带 input_key，便于编排层做“部分失败”聚合
                in_key = cmd.input_key if 'cmd' in locals() else None
                resp_payload = EventPayload(status="FAIL", input_key=in_key, error_msg=str(e))
                routing_key = f"evt.{self.service_name}.failed"
            else:
                print("Could not deserialize message, sending to DLQ (handled by nack/reject implicitly if exception propagates)")
                raise e

        # E. 发布事件
        if 'pkg' in locals():
            await self._publish_event(pkg.header, resp_payload, routing_key)

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

    async def do_work(self, input_key: str, params: dict) -> str:
        """
        [抽象] 业务逻辑
        :return: output_key
        """
        raise NotImplementedError
