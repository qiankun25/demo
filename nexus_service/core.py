import asyncio
import json
import uuid
import sys
import os
import aio_pika
from aio_pika import ExchangeType, DeliveryMode, Message

# 将项目根目录添加到路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared.common import RabbitConfig, MessagePackage, MsgHeader, CommandPayload, MockStorage

class NexusService:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.queue_name = "q.nexus.orchestrator"

    async def connect(self):
        self.connection = await aio_pika.connect_robust(RabbitConfig.URL)
        self.channel = await self.connection.channel()
        
        # 声明交换机 (幂等)
        await self.channel.declare_exchange(RabbitConfig.CMD_EXCHANGE, ExchangeType.DIRECT, durable=True)
        evt_exchange = await self.channel.declare_exchange(RabbitConfig.EVT_EXCHANGE, ExchangeType.TOPIC, durable=True)
        
        # 声明监听队列
        queue = await self.channel.declare_queue(self.queue_name, durable=True)
        # 监听所有事件
        await queue.bind(evt_exchange, routing_key="evt.#")
        
        return queue

    async def start(self):
        print("[*] Nexus Orchestrator Started. Listening for events...")
        queue = await self.connect()
        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    await self._on_event(message)

    async def submit_job(self, task_type: str, initial_data: dict):
        """API 入口点"""
        # 如果单独调用，确保连接存在
        if not self.channel:
            await self.connect()
            
        trace_id = str(uuid.uuid4())
        print(f"\n[Nexus] >>> New Job Received: {task_type} | TraceID: {trace_id}")
        
        # 1. Claim Check (保存数据)
        input_key = f"task:{trace_id}:init"
        await MockStorage.save(input_key, initial_data)
        
        # 2. 触发第一步
        if task_type == "MORNING_REPORT":
            await self._send_command(trace_id, task_type, "cmd.downloader.start", input_key)
            
        return trace_id

    async def _on_event(self, message: aio_pika.abc.AbstractIncomingMessage):
        body_str = message.body.decode()
        pkg = MessagePackage(**json.loads(body_str))
        routing_key = message.routing_key
        trace_id = pkg.header.trace_id
        
        print(f"[Nexus] Received Event: {routing_key} | TraceID: {trace_id}")
        
        if pkg.payload['status'] == 'FAIL':
             print(f"[Nexus] 🚨 Task Failed at {pkg.header.sender}: {pkg.payload.get('error_msg')}")
             return

        # --- DAG 逻辑 ---
        if pkg.header.task_type == "MORNING_REPORT":
            
            if routing_key == "evt.downloader.finished":
                print("[Nexus] Scheduling Next Step: Parser")
                await self._send_command(trace_id, pkg.header.task_type, "cmd.parser.start", pkg.payload['output_key'])
                
            elif routing_key == "evt.parser.finished":
                print("[Nexus] Scheduling Next Step: Indexer")
                await self._send_command(trace_id, pkg.header.task_type, "cmd.indexer.start", pkg.payload['output_key'])
                
            elif routing_key == "evt.indexer.finished":
                print(f"[Nexus] ✅ Job {trace_id} Completed Successfully! Result at: {pkg.payload['output_key']}")

    async def _send_command(self, trace_id, task_type, routing_key, input_key):
        header = MsgHeader(trace_id=trace_id, task_type=task_type, sender="nexus")
        payload = CommandPayload(task_id=str(uuid.uuid4()), input_key=input_key)
        pkg = MessagePackage(header=header, payload=payload.model_dump())
        
        exchange = await self.channel.get_exchange(RabbitConfig.CMD_EXCHANGE)
        
        await exchange.publish(
            Message(
                body=pkg.model_dump_json().encode(),
                delivery_mode=DeliveryMode.PERSISTENT
            ),
            routing_key=routing_key
        )
        print(f"[Nexus] Sent Command: {routing_key}")
