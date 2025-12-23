import os
import sys
import hashlib
from typing import Dict, Any, List


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _ensure_nexus_sdk_on_path() -> None:
    root = _repo_root()
    candidates = [
        os.path.join(root, "nexus_sdk"),
        os.path.join(root, "orchestration", "RabbitMQ", "nexus_sdk"),
    ]
    for c in candidates:
        if os.path.exists(c) and c not in sys.path:
            sys.path.append(c)


_ensure_nexus_sdk_on_path()

from nexus_sdk.base import BaseToolService  # noqa: E402
from nexus_sdk.common import MockStorage  # noqa: E402


class IndexerToolService(BaseToolService):
    """
    Indexer ToolService：将解析产物写入本地索引（简化版 hash embedding）。

    期望输入 (data:parse:*):
    {
        "doc_id": "...",
        "title": "...",
        "chunks": [{chunk_id, text, page, section_path}],
        "meta": {...}
    }

    输出：
    - output_key: data:index:{input_key}
    - 存储内容: { "doc_id", "chunk_count", "vector_count", "collection": "default" }
    """

    def __init__(self):
        super().__init__(service_name="indexer", cmd_routing_key="cmd.indexer.start")

    async def do_work(self, input_key: str, params: dict) -> str:
        payload = await MockStorage.get(input_key)
        if not payload:
            raise ValueError(f"input_key={input_key} not found in storage")

        doc_id = payload.get("doc_id")
        title = payload.get("title")
        fulltext_hash = payload.get("fulltext_hash")
        chunks: List[Dict[str, Any]] = payload.get("chunks") or []
        if not doc_id or not chunks:
            raise ValueError("doc_id or chunks missing for indexing")

        # ---- Vector DB (ChromaDB persistent) ----
        try:
            import chromadb  # noqa: WPS433
        except Exception as e:
            raise ImportError(
                "chromadb is required for indexing_service. Please install it (already in requirements.txt)."
            ) from e

        persist_dir = os.getenv("CHROMA_PERSIST_DIR") or os.path.join(_repo_root(), ".chroma")
        collection_name = os.getenv("CHROMA_COLLECTION") or "morning_report"
        client = chromadb.PersistentClient(path=persist_dir)
        collection = client.get_or_create_collection(name=collection_name)

        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        embeddings: List[List[float]] = []
        for c in chunks:
            cid = str(c.get("chunk_id") or "")
            if not cid:
                continue
            ids.append(cid)
            text = str(c.get("text") or "")
            documents.append(text)

            meta = {
                "doc_id": doc_id,
                "title": title,
                "page": c.get("page"),
                "hash": c.get("hash"),
                "fulltext_hash": fulltext_hash,
            }
            # Chroma metadata value 只允许：str/int/float/bool；且不能是 None
            meta = {k: v for k, v in meta.items() if v is not None}
            metadatas.append(meta)

            embeddings.append(self._hash_embed(text))

        vector_count = len(ids)

        if ids:
            # upsert: 幂等（重复跑不会报错）
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )

        output_key = f"data:index:{input_key}"
        await MockStorage.save(
            output_key,
            {
                "doc_id": doc_id,
                "chunk_count": len(chunks),
                "vector_count": vector_count,
                "collection": collection_name,
                "persist_dir": persist_dir,
            },
        )
        return output_key

    def _hash_embed(self, text: str, dim: int = 64) -> List[float]:
        # 简易 hash embedding，用于示例
        v = [0.0] * dim
        tokens = (text or "").split()
        for t in tokens:
            h = int(hashlib.sha256(t.encode("utf-8", errors="ignore")).hexdigest(), 16)
            idx = h % dim
            sign = 1.0 if (h & 1) == 0 else -1.0
            v[idx] += sign
        return v


if __name__ == "__main__":
    service = IndexerToolService()
    try:
        import asyncio

        asyncio.run(service.start())
    except KeyboardInterrupt:
        pass