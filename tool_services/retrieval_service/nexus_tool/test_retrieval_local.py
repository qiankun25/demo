"""
RetrievalToolService 本地自测脚本（离线可跑）。

运行：
  python3 tool_services/retrieval_service/nexus_tool/test_retrieval_local.py
"""

import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from tool_services.retrieval_service.nexus_tool.tool_service import RetrievalToolService
from nexus_sdk.common import MockStorage
from tool_services.test_utils import ensure_storage_ready


async def main():
    ok, backend = await ensure_storage_ready(MockStorage)
    print(f"[selftest] storage backend = {backend} (minio_ok={ok})")

    # 先准备一些本地 parse 产物（Retrieval 会 list_keys("data:parse:") 并扫描 chunks）
    await MockStorage.save(
        "data:parse:task:test:doc1",
        {
            "doc_id": "doc1",
            "chunks": [
                {"chunk_id": "d1c1", "text": "LLM safety alignment is important", "page": 1, "hash": "h1"},
                {"chunk_id": "d1c2", "text": "retrieval augmented generation", "page": 2, "hash": "h2"},
            ],
        },
    )
    await MockStorage.save(
        "data:parse:task:test:doc2",
        {
            "doc_id": "doc2",
            "chunks": [
                {"chunk_id": "d2c1", "text": "computer vision and diffusion models", "page": 1, "hash": "h3"},
            ],
        },
    )

    input_key = "task:test:retrieval"
    await MockStorage.save(
        input_key,
        {
            "query": "LLM safety",
            "top_k": 3,
        },
    )

    # 提高扫描上限（如果你本机 MinIO 里已有很多 parse 对象）
    os.environ.setdefault("RETRIEVAL_LOCAL_SCAN_LIMIT", "1000")

    service = RetrievalToolService()
    output_key = await service.do_work(input_key, {})
    out = await MockStorage.get(output_key)

    assert output_key.startswith("data:retrieval:")
    assert out["query"] == "LLM safety"
    assert isinstance(out["local_hits"], list) and len(out["local_hits"]) >= 1
    assert out["external_hits"] == []
    assert isinstance(out["combined"], list) and len(out["combined"]) >= 1
    print("[selftest] OK:", output_key, "local_hits=", len(out["local_hits"]))

    # 再测：无命中时应返回空（不做外部发现，也不报错）
    input_key2 = "task:test:retrieval:nohit"
    await MockStorage.save(
        input_key2,
        {
            "query": "this_query_should_not_match_anything_xyz",
            "top_k": 3,
        },
    )
    output_key2 = await service.do_work(input_key2, {})
    out2 = await MockStorage.get(output_key2)
    assert out2["local_hits"] == []
    assert out2["external_hits"] == []
    assert out2["combined"] == []
    print("[selftest] OK (no-hit):", output_key2)


if __name__ == "__main__":
    asyncio.run(main())

