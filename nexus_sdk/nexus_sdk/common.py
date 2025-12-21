import time
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel
import asyncio

# --- 1. RabbitMQ 配置 ---
class RabbitConfig:
    # 假设 demo 使用本地默认配置。生产环境请使用环境变量。
    URL = "amqp://guest:guest@localhost:5672/"
    
    # 交换机定义
    CMD_EXCHANGE = "nexus.cmd.exchange"   # 指令交换机 (Direct)
    EVT_EXCHANGE = "nexus.evt.exchange"   # 事件交换机 (Topic)
    DLX_EXCHANGE = "nexus.dlx.exchange"   # 死信交换机 (Direct)
    
    # 队列定义
    DLQ_QUEUE = "q.nexus.dead_letter"     # 死信队列
    TTL_MS = 60000                        # 消息超时时间 (60秒)

# --- 2. 消息协议 (Pydantic 模型) ---

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
    status: str          # "SUCCESS" / "FAIL"
    output_key: Optional[str] = None
    error_msg: Optional[str] = None

class MessagePackage(BaseModel):
    header: MsgHeader
    payload: Dict[str, Any] # 包含 CommandPayload 或 EventPayload 的内容

# --- 3. 模拟存储 (Claim Check 模式) ---
# 生产环境中请替换为 Redis / MinIO 客户端
class MockStorage:
    _store = {}
    
    @classmethod
    async def save(cls, key: str, data: Any):
        print(f"[Storage] Saved data to key: {key}")
        cls._store[key] = data
        # 模拟 I/O 延迟
        await asyncio.sleep(0.01)
        
    @classmethod
    async def get(cls, key: str):
        # 模拟 I/O 延迟
        await asyncio.sleep(0.01)
        return cls._store.get(key)
