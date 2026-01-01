import time
from enum import Enum
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel
import asyncio
import os
from io import BytesIO
import json
import pickle

try:
    from minio import Minio
    from minio.error import S3Error
except Exception:  # pragma: no cover
    Minio = None  # type: ignore
    S3Error = Exception  # type: ignore

# --- 1. RabbitMQ 配置 ---
class RabbitConfig:
    # 假设 demo 使用本地默认配置。生产环境请使用环境变量。
    URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    
    # 交换机定义
    CMD_EXCHANGE = "nexus.cmd.exchange"   # 指令交换机 (Direct)
    EVT_EXCHANGE = "nexus.evt.exchange"   # 事件交换机 (Topic)
    DLX_EXCHANGE = "nexus.dlx.exchange"   # 死信交换机 (Direct)
    
    # 队列定义
    DLQ_QUEUE = "q.nexus.dead_letter"     # 死信队列
    # 命令队列 TTL（毫秒）。
    # 默认值从 60s 提高到 15min，避免 MORNING_REPORT / SUMMARY_REPORT fan-out 时因 prefetch=1 导致队列等待过久而被 DLQ。
    # 如需禁用 TTL，可设置 NEXUS_CMD_TTL_MS<=0（BaseToolService 会跳过 x-message-ttl）。
    TTL_MS = int(os.getenv("NEXUS_CMD_TTL_MS", "900000"))

# 约定的服务路由表，便于各服务/文档统一引用
SERVICE_ROUTING = {
    # Discovery: 基于 OpenAlex 的外部资源发现
    "discovery": {
        "cmd": "cmd.discovery.start",
        "evt_finished": "evt.discovery.finished",
        "evt_failed": "evt.discovery.failed",
        "queue": "q.tool.discovery",
    },
    # Download: PDF 下载
    "downloader": {
        "cmd": "cmd.downloader.start",
        "evt_finished": "evt.downloader.finished",
        "evt_failed": "evt.downloader.failed",
        "queue": "q.tool.downloader",
    },
    # Parser: PDF 解析 -> 标准产物
    "parser": {
        "cmd": "cmd.parser.start",
        "evt_finished": "evt.parser.finished",
        "evt_failed": "evt.parser.failed",
        "queue": "q.tool.parser",
    },
    # Indexer: 入库/向量索引
    "indexer": {
        "cmd": "cmd.indexer.start",
        "evt_finished": "evt.indexer.finished",
        "evt_failed": "evt.indexer.failed",
        "queue": "q.tool.indexer",
    },
    # Retrieval: 统一检索编排
    "retrieval": {
        "cmd": "cmd.retrieval.start",
        "evt_finished": "evt.retrieval.finished",
        "evt_failed": "evt.retrieval.failed",
        "queue": "q.tool.retrieval",
    },
    # Translator: 多模态翻译
    "translator": {
        "cmd": "cmd.translator.start",
        "evt_finished": "evt.translator.finished",
        "evt_failed": "evt.translator.failed",
        "queue": "q.tool.translator",
    },
    "overview": {
        "cmd": "cmd.overview.start",
        "evt_finished": "evt.overview.finished",
        "evt_failed": "evt.overview.failed",
        "queue": "q.tool.overview",
    },
}

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
    input_key: str = ""
    params: Dict[str, Any] = {}
    # Optional v1 fields (ignored by legacy services)
    version: Optional[str] = None
    command: Optional[str] = None
    trace_id: Optional[str] = None
    work_key: Optional[str] = None
    input_ref: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None

class EventPayload(BaseModel):
    status: str          # "SUCCESS" / "FAIL"
    output_key: Optional[str] = None
    input_key: Optional[str] = None
    error_msg: Optional[str] = None
    # Optional v1 fields
    version: Optional[str] = None
    event: Optional[str] = None
    trace_id: Optional[str] = None
    work_key: Optional[str] = None
    result_ref: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None

class MessagePackage(BaseModel):
    header: MsgHeader
    payload: Dict[str, Any] # 包含 CommandPayload 或 EventPayload 的内容

# --- 3. 模拟存储 (Claim Check 模式) ---
# 生产环境中请替换为 Redis / MinIO 客户端
class MockStorage:
    """
    Claim Check 存储（MinIO 后端）。
    保持 async 接口；内部通过 asyncio.to_thread 调用阻塞的 minio-py。

    环境变量（带默认值，方便本地 demo）：
    - MINIO_ENDPOINT: 默认 localhost:9000
    - MINIO_ACCESS_KEY: 默认 minioadmin
    - MINIO_SECRET_KEY: 默认 minioadmin
    - MINIO_BUCKET: 默认 papers
    - MINIO_SECURE: 默认 false
    - NEXUS_STORAGE_PREFIX: 默认 claimcheck/
    """

    _client: Optional["Minio"] = None
    _bucket: Optional[str] = None
    _secure: Optional[bool] = None
    _prefix: str = "claimcheck/"

    _MAGIC = b"NEXUS_CLAIMCHECK_V1\n"

    @classmethod
    def _bool_env(cls, name: str, default: bool) -> bool:
        v = os.getenv(name)
        if v is None:
            return default
        return str(v).strip().lower() in ("1", "true", "yes", "y", "on")

    @classmethod
    def _init(cls) -> None:
        if cls._client is not None:
            return
        if Minio is None:
            raise RuntimeError(
                "MinIO client not available. Please install dependency 'minio' (minio-py)."
            )

        endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        bucket = os.getenv("MINIO_BUCKET", "papers")
        secure = cls._bool_env("MINIO_SECURE", False)
        prefix = os.getenv("NEXUS_STORAGE_PREFIX", "claimcheck/")

        cls._client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=os.getenv("AWS_REGION", "us-east-1"),
        )
        cls._bucket = bucket
        cls._secure = secure
        cls._prefix = prefix.lstrip("/")
        if cls._prefix and not cls._prefix.endswith("/"):
            cls._prefix += "/"

    @classmethod
    def _ensure_bucket_exists_sync(cls) -> None:
        assert cls._client is not None
        assert cls._bucket is not None
        if not cls._client.bucket_exists(cls._bucket):
            cls._client.make_bucket(cls._bucket)

    @classmethod
    def _object_name(cls, key: str) -> str:
        cls._init()
        k = str(key).lstrip("/")
        return f"{cls._prefix}{k}" if cls._prefix else k

    @classmethod
    def _encode_payload(cls, data: Any) -> Tuple[bytes, str]:
        if isinstance(data, (bytes, bytearray, memoryview)):
            return bytes(data), "raw"
        try:
            body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            return body, "json"
        except Exception:
            body = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
            return body, "pickle"

    @classmethod
    def _wrap(cls, body: bytes, encoding: str) -> bytes:
        header = cls._MAGIC + f"encoding:{encoding}\n\n".encode("utf-8")
        return header + body

    @classmethod
    def _unwrap(cls, raw: bytes) -> Any:
        if not raw.startswith(cls._MAGIC):
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return raw
        rest = raw[len(cls._MAGIC) :]
        sep = rest.find(b"\n\n")
        if sep < 0:
            return rest
        meta = rest[:sep].decode("utf-8", errors="replace")
        body = rest[sep + 2 :]
        encoding = "raw"
        for line in meta.splitlines():
            if line.startswith("encoding:"):
                encoding = line.split(":", 1)[1].strip()
                break
        if encoding == "json":
            return json.loads(body.decode("utf-8"))
        if encoding == "pickle":
            return pickle.loads(body)
        return body

    @classmethod
    async def save(cls, key: str, data: Any):
        cls._init()
        object_name = cls._object_name(key)
        body, encoding = cls._encode_payload(data)
        payload = cls._wrap(body, encoding)

        def _put() -> None:
            assert cls._client is not None
            assert cls._bucket is not None
            cls._ensure_bucket_exists_sync()
            cls._client.put_object(
                bucket_name=cls._bucket,
                object_name=object_name,
                data=BytesIO(payload),
                length=len(payload),
                content_type="application/octet-stream",
            )

        try:
            await asyncio.to_thread(_put)
            print(f"[Storage] Saved data to MinIO key: {key}")
        except S3Error as e:
            raise RuntimeError(f"MinIO save failed for key={key}: {e}") from e
        
    @classmethod
    async def get(cls, key: str):
        cls._init()
        object_name = cls._object_name(key)

        def _get_bytes() -> Optional[bytes]:
            assert cls._client is not None
            assert cls._bucket is not None
            try:
                resp = cls._client.get_object(cls._bucket, object_name)
            except S3Error as e:
                if "NoSuchKey" in str(e) or "Not Found" in str(e):
                    return None
                raise
            try:
                return resp.read()
            finally:
                try:
                    resp.close()
                    resp.release_conn()
                except Exception:
                    pass

        try:
            raw = await asyncio.to_thread(_get_bytes)
        except S3Error as e:
            raise RuntimeError(f"MinIO get failed for key={key}: {e}") from e
        if raw is None:
            return None
        return cls._unwrap(raw)

    @classmethod
    async def list_keys(cls, prefix: str = "") -> List[str]:
        cls._init()
        want = str(prefix or "")
        obj_prefix = cls._object_name(want) if want else cls._prefix

        def _list() -> List[str]:
            assert cls._client is not None
            assert cls._bucket is not None
            cls._ensure_bucket_exists_sync()
            out: List[str] = []
            for obj in cls._client.list_objects(cls._bucket, prefix=obj_prefix, recursive=True):
                name = getattr(obj, "object_name", "")
                if not name:
                    continue
                if cls._prefix and name.startswith(cls._prefix):
                    out.append(name[len(cls._prefix) :])
                else:
                    out.append(name)
            return out

        return await asyncio.to_thread(_list)
