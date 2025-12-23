"""
IndexerToolService 本地自测脚本（离线可跑）。

运行：
  python3 tool_services/indexing_service/nexus_tool/test_indexer_local.py
"""

import asyncio
import os
import sys
import tempfile

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from tool_services.indexing_service.nexus_tool.tool_service import IndexerToolService
from nexus_sdk.common import MockStorage
from tool_services.test_utils import ensure_storage_ready


async def main():
    ok, backend = await ensure_storage_ready(MockStorage)
    print(f"[selftest] storage backend = {backend} (minio_ok={ok})")

    # 使用独立的 ChromaDB 持久化目录，避免污染正式数据
    persist_dir = os.path.join(tempfile.gettempdir(), "chroma_selftest")
    os.environ["CHROMA_PERSIST_DIR"] = persist_dir
    os.environ["CHROMA_COLLECTION"] = "selftest"

    input_key = "data:parse:task:test:indexer"
    await MockStorage.save(
        input_key,
        {
            "doc_id": "doc_123",
            "title": "Demo Paper",
            "fulltext_hash": "fullhash_123",
            "chunks": [
                {"chunk_id": "c1", "text": "hello world", "page": 1, "section_path": ["A"]},
                {"chunk_id": "c2", "text": "world safety alignment", "page": 2, "section_path": ["B"]},
            ],
            "meta": {"source_url": "local"},
        },
    )

    service = IndexerToolService()
    output_key = await service.do_work(input_key, {})
    out = await MockStorage.get(output_key)

    assert output_key.startswith("data:index:")
    assert out["doc_id"] == "doc_123"
    assert out["chunk_count"] == 2
    assert out["vector_count"] == 2
    assert out["collection"] == "selftest"
    assert out.get("persist_dir") == persist_dir
    print("[selftest] OK:", output_key)


if __name__ == "__main__":
    asyncio.run(main())

