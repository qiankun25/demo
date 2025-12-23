# nexus_tool_template.py
# ==============================================================================
# Nexus 微服务架构 - 工具服务开发模板 (Standalone)
# 
# 使用说明：
# 1. 安装依赖: pip install aio-pika pydantic
# 2. 将本文件复制到您的项目中
# 3. 修改 MyToolService 类实现您的业务逻辑
# 4. 运行: python nexus_tool_template.py
# ==============================================================================

import asyncio
import json
import time
import traceback
import uuid
from typing import Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel
import aio_pika
from aio_pika import ExchangeType, DeliveryMode, Message

# ==============================================================================
# 第一部分：核心配置与协议 (可根据需要修改)
# ==============================================================================

class RabbitConfig:
    """RabbitMQ 连接与拓扑配置"""
    # [可配置] MQ 连接地址
    URL = "amqp://guest:guest@localhost:5672/"
    
    # [核心] 交换机名称 (通常不需要修改)
    CMD_EXCHANGE = "nexus.cmd.exchange"   # 接收指令
    EVT_EXCHANGE = "nexus.evt.exchange"   # 发送事件
    DLX_EXCHANGE = "nexus.dlx.exchange"   # 死信处理
    
    # [核心] 死信队列
    DLQ_QUEUE = "q.nexus.dead_letter"
    TTL_MS = 60000  # 默认超时 60秒

# --- Pydantic 数据模型 ---

class MsgHeader(BaseModel):
    trace_id: str
    task_type: str
    sender: str
    timestamp: float = 0.0
    
    def __init__(self, **data):
        super().__init__(**data)
        if self.timestamp == 0.0:
            self.timestamp = time.time()

class CommandPayload(BaseModel):
    task_id: str
    input_key: str
    params: Dict[str, Any] = {}

class EventPayload(BaseModel):
    status: str
    output_key: Optional[str] = None
    error_msg: Optional[str] = None

class MessagePackage(BaseModel):
    header: MsgHeader
    payload: Dict[str, Any]

# --- 模拟存储适配器 (开发用) ---
class MockStorage:
    _store = {}
    
    @classmethod
    async def save(cls, key: str, data: Any):
        # [TODO] 生产环境请替换为 Redis/S3 客户端
        print(f"[Storage] Saved: {key} -> {str(data)[:50]}...")
        cls._store[key] = data
        
    @classmethod
    async def get(cls, key: str):
        # [TODO] 生产环境请替换为 Redis/S3 客户端
        return cls._store.get(key)

# ==============================================================================
# 第二部分：服务基类 (处理连接、监听、ACK)
# ==============================================================================

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
            # 1. 建立连接
            self.connection = await aio_pika.connect_robust(RabbitConfig.URL)
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=1)

            # 2. 声明基础设施 (交换机/队列)
            # 开发者可以在这里修改队列参数，例如优先级、持久化策略等
            cmd_exchange = await self.channel.declare_exchange(
                RabbitConfig.CMD_EXCHANGE, ExchangeType.DIRECT, durable=True
            )
            evt_exchange = await self.channel.declare_exchange(
                RabbitConfig.EVT_EXCHANGE, ExchangeType.TOPIC, durable=True
            )
            dlx_exchange = await self.channel.declare_exchange(
                RabbitConfig.DLX_EXCHANGE, ExchangeType.DIRECT, durable=True
            )

            # 绑定死信队列
            dlq = await self.channel.declare_queue(RabbitConfig.DLQ_QUEUE, durable=True)
            await dlq.bind(dlx_exchange, routing_key=self.cmd_routing_key)

            # 声明工作队列
            args = {
                'x-message-ttl': RabbitConfig.TTL_MS,
                'x-dead-letter-exchange': RabbitConfig.DLX_EXCHANGE,
                'x-dead-letter-routing-key': self.cmd_routing_key
            }
            queue = await self.channel.declare_queue(self.queue_name, durable=True, arguments=args)
            await queue.bind(cmd_exchange, routing_key=self.cmd_routing_key)

            print(f"[*] Waiting for tasks on: {self.cmd_routing_key}")

            # 3. 消费循环
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        await self._handle_message(message)

        except asyncio.CancelledError:
            print(f"[*] {self.service_name} Stopped.")
        except Exception as e:
            if "Channel closed" not in str(e):
                print(f"[FATAL] Service Crashed: {e}")
            if self.connection:
                await self.connection.close()

    async def _handle_message(self, message):
        try:
            # 反序列化
            data = json.loads(message.body.decode())
            pkg = MessagePackage(**data)
            cmd = CommandPayload(**pkg.payload)

            print(f"[{self.service_name}] >>> Task: {pkg.header.trace_id}")

            # --- 执行业务逻辑 ---
            output_key = await self.do_work(cmd.input_key, cmd.params)
            # ------------------

            # 发送成功事件
            await self._publish_event(pkg.header, EventPayload(status="SUCCESS", output_key=output_key))

        except Exception as e:
            print(f"[{self.service_name}] !!! Error: {e}")
            traceback.print_exc()
            # 发送失败事件 (确保 Nexus 知道任务失败了)
            if 'pkg' in locals():
                await self._publish_event(pkg.header, EventPayload(status="FAIL", error_msg=str(e)))
            else:
                # 连包都解不开，无法回传，直接丢弃（会进入 DLQ）
                raise e

    async def _publish_event(self, req_header, payload):
        new_header = req_header.model_copy()
        new_header.sender = self.service_name
        new_header.timestamp = time.time()
        
        resp_pkg = MessagePackage(header=new_header, payload=payload.model_dump())
        exchange = await self.channel.get_exchange(RabbitConfig.EVT_EXCHANGE)
        
        routing_key = f"evt.{self.service_name}.{'finished' if payload.status == 'SUCCESS' else 'failed'}"
        
        await exchange.publish(
            Message(body=resp_pkg.model_dump_json().encode(), delivery_mode=DeliveryMode.PERSISTENT),
            routing_key=routing_key
        )
        print(f"[{self.service_name}] <<< Event Sent: {routing_key}")

    async def do_work(self, input_key: str, params: dict) -> str:
        """[抽象方法] 子类必须实现具体的业务逻辑"""
        raise NotImplementedError

# ==============================================================================
# 第三部分：具体实现示例 (开发者只需修改这里)
# ==============================================================================

class MyCustomTool(BaseToolService):
    async def do_work(self, input_key: str, params: dict) -> str:
        """
        这里是您的业务逻辑代码。
        :param input_key: 输入数据的存储 Key (从 Redis/MinIO 读取)
        :param params: 任务参数
        :return: 结果数据的存储 Key
        """
        # 1. 模拟从存储获取数据
        # input_data = await redis.get(input_key)
        print(f"   [Logic] Processing data from {input_key}...")
        
        # 2. 模拟耗时操作
        await asyncio.sleep(2)
        
        # 3. 模拟保存结果
        output_key = f"result:{input_key}"
        await MockStorage.save(output_key, {"processed": True})
        
        return output_key

# ==============================================================================
# 第四部分：启动入口
# ==============================================================================

if __name__ == "__main__":
    # 配置服务名称和监听的指令 Key
    service = MyCustomTool(
        service_name="my_custom_tool", 
        cmd_routing_key="cmd.mytool.start"
    )
    
    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        pass
