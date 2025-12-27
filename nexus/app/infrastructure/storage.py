import asyncio
import json
import pickle
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union, Callable
from minio import Minio
from minio.error import S3Error
import io

from app.core.config import Settings
from app.models.state_models import JobContext
from app.core.retry import with_retry, RetryConfig

logger = logging.getLogger(__name__)

class StorageBackend(ABC):
    """Abstract base class for storage backends"""
    
    @abstractmethod
    async def get(self, key: str) -> Any:
        """Retrieve data from storage"""
        pass

    @abstractmethod
    async def get_stream(self, key: str) -> tuple[Any, str]:
        """Retrieve data stream and content type from storage"""
        pass

    @abstractmethod
    async def put(self, key: str, data: Any) -> None:
        """Save data to storage"""
        pass
        
    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete data from storage"""
        pass
        
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        pass
        
    @abstractmethod
    async def is_healthy(self) -> bool:
        """Check storage health"""
        pass

class MinIOStorage(StorageBackend):
    """MinIO implementation of StorageBackend"""
    
    def __init__(self, settings: Settings):
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure
        )
        self.bucket = settings.minio_bucket
        self.prefix = settings.storage_prefix
        self._ensure_bucket()
        
    def _ensure_bucket(self):
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except Exception as e:
            logger.error(f"Failed to ensure bucket {self.bucket}: {e}")
            # We don't raise here to allow startup, but health check will fail

    def _get_object_name(self, key: str) -> str:
        k = str(key).lstrip("/")
        return f"{self.prefix}{k}" if self.prefix else k
            
    @with_retry()
    async def get(self, key: str) -> Any:
        return await asyncio.to_thread(self._get_sync, key)
    
    async def get_stream(self, key: str) -> tuple[Any, str]:
        """Get object as a stream (generator) and its content type.
        
        Returns:
            tuple: (generator, content_type)
        """
        # We don't use asyncio.to_thread here because we want to yield chunks
        # But MinIO get_object returns a blocking response object.
        # We need to run the initial request in thread, but the streaming part...
        # Actually, MinIO response.stream() is blocking.
        # So we should wrap the whole thing in a way that FastAPI can consume.
        # A simple way is to get the response object and wrap its stream method.
        
        def _get_response_sync():
            obj_name = self._get_object_name(key)
            try:
                # get_object returns a urllib3.response.HTTPResponse
                response = self.client.get_object(self.bucket, obj_name)
                # Determine content type (default to json if unknown)
                content_type = response.headers.get("Content-Type", "application/json")
                return response, content_type
            except S3Error as e:
                if e.code == "NoSuchKey":
                    raise ValueError(f"Artifact {key} not found")
                raise
                
        response, content_type = await asyncio.to_thread(_get_response_sync)
        
        async def _stream_generator():
            try:
                # Read in 32KB chunks
                for chunk in response.stream(32 * 1024):
                    yield chunk
            finally:
                response.close()
                response.release_conn()
                
        return _stream_generator(), content_type
        
    def _unwrap(self, raw: bytes) -> Any:
        MAGIC = b"NEXUS_CLAIMCHECK_V1\n"
        if not raw.startswith(MAGIC):
            return raw

        rest = raw[len(MAGIC) :]
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
             try:
                 return json.loads(body.decode("utf-8"))
             except Exception:
                 return body
        if encoding == "pickle":
             try:
                 return pickle.loads(body)
             except Exception:
                 return body
        return body

    def _get_sync(self, key: str) -> Any:
        try:
            obj_name = self._get_object_name(key)
            print(f"DEBUG: MinIO Get Bucket={self.bucket} Key={obj_name}")
            response = self.client.get_object(self.bucket, obj_name)
            data = response.read()
            print(f"DEBUG: MinIO Read {len(data)} bytes: {data[:100]}")
            response.close()
            response.release_conn()
            
            # Try to unwrap Nexus magic header
            unwrapped = self._unwrap(data)
            if unwrapped is not data and not isinstance(unwrapped, bytes):
                 # _unwrap already decoded it
                 return unwrapped
            
            data = unwrapped # Continue with unwrapped bytes if it was raw or failed decode
            
            # Try JSON decode
            try:
                return json.loads(data)
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
                # Try pickle
                try:
                    return pickle.loads(data)
                except:
                    # Return raw bytes
                    return data
        except S3Error as e:
            print(f"DEBUG: MinIO S3Error code={e.code} msg={e}")
            if e.code == "NoSuchKey":
                return None
            logger.error(f"MinIO get error for {key}: {e}")
            raise
        except Exception as e:
            logger.error(f"Storage get error for {key}: {e}")
            raise

    @with_retry()
    async def put(self, key: str, data: Any) -> None:
        await asyncio.to_thread(self._put_sync, key, data)
        
    def _put_sync(self, key: str, data: Any) -> None:
        try:
            obj_name = self._get_object_name(key)
            
            # Encode data
            if isinstance(data, (bytes, bytearray)):
                body = data
                content_type = "application/octet-stream"
            else:
                try:
                    body = json.dumps(data).encode("utf-8")
                    content_type = "application/json"
                except:
                    body = pickle.dumps(data)
                    content_type = "application/python-pickle"
                    
            self.client.put_object(
                self.bucket,
                obj_name,
                io.BytesIO(body),
                len(body),
                content_type=content_type
            )
        except Exception as e:
            logger.error(f"Storage put error for {key}: {e}")
            raise

    @with_retry()
    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._delete_sync, key)
        
    def _delete_sync(self, key: str) -> None:
        try:
            obj_name = self._get_object_name(key)
            self.client.remove_object(self.bucket, obj_name)
        except Exception as e:
            logger.error(f"Storage delete error for {key}: {e}")
            raise

    @with_retry()
    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._exists_sync, key)
        
    def _exists_sync(self, key: str) -> bool:
        try:
            obj_name = self._get_object_name(key)
            self.client.stat_object(self.bucket, obj_name)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            raise
        except Exception as e:
            logger.error(f"Storage exists error for {key}: {e}")
            raise

    async def is_healthy(self) -> bool:
        try:
            return await asyncio.to_thread(self.client.bucket_exists, self.bucket)
        except:
            return False

class StateManager:
    """Manages job state persistence"""
    
    def __init__(self, storage: StorageBackend):
        self.storage = storage
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
        
    def _get_ctx_key(self, trace_id: str) -> str:
        return f"task:{trace_id}:ctx"

    async def _get_lock(self, trace_id: str) -> asyncio.Lock:
        async with self._global_lock:
            if trace_id not in self._locks:
                self._locks[trace_id] = asyncio.Lock()
            return self._locks[trace_id]

    async def get_context(self, trace_id: str) -> Optional[JobContext]:
        key = self._get_ctx_key(trace_id)
        # For simple reads, we don't strictly need a lock if we accept eventual consistency,
        # but to be safe against partial writes (unlikely with MinIO put), we can skip lock.
        # However, to ensure we read the latest state committed by atomic_update,
        # we might want to lock. But read-only doesn't block read-only.
        # Let's keep it simple: no lock for pure get.
        data = await self.storage.get(key)
        if not data:
            return None
        return JobContext(**data)

    async def update_context(self, trace_id: str, updates: Dict[str, Any]) -> JobContext:
        """
        Non-atomic update (use with caution or for single-writer scenarios).
        It wraps atomic_update_context for backward compatibility but
        the 'read' part is implicit in the update dict, which might be stale.
        Better implementation: Just use the lock to protect the write.
        """
        lock = await self._get_lock(trace_id)
        async with lock:
            key = self._get_ctx_key(trace_id)
            current = await self.get_context(trace_id)
            if not current:
                raise ValueError(f"Context not found for trace_id: {trace_id}")
                
            current_dict = current.model_dump()
            current_dict.update(updates)
            updated_ctx = JobContext(**current_dict)
            
            await self.storage.put(key, updated_ctx.model_dump())
            return updated_ctx

    async def atomic_update_context(self, trace_id: str, update_func: Callable[[JobContext], Dict[str, Any]]) -> JobContext:
        """
        Atomically read-modify-write context using an in-memory lock.
        update_func receives current context and returns a dict of updates to apply.
        """
        lock = await self._get_lock(trace_id)
        async with lock:
            key = self._get_ctx_key(trace_id)
            
            # 1. Read fresh data under lock
            data = await self.storage.get(key)
            if not data:
                raise ValueError(f"Context not found for trace_id: {trace_id}")
            current = JobContext(**data)
            
            # 2. Compute updates
            updates = update_func(current)
            if not updates:
                return current
                
            # 3. Apply updates
            current_dict = current.model_dump()
            current_dict.update(updates)
            updated_ctx = JobContext(**current_dict)
            
            # 4. Write back
            await self.storage.put(key, updated_ctx.model_dump())
            return updated_ctx

    async def save_context(self, context: JobContext) -> None:
        key = self._get_ctx_key(context.trace_id)
        lock = await self._get_lock(context.trace_id)
        async with lock:
            await self.storage.put(key, context.model_dump())
