"""
OverviewToolService 本地自测脚本（真实调用 SiliconFlow2）。

运行：
  python3 tool_services/overview_service/nexus_tool/test_overview_local.py

要求：
- MinIO 可用（MockStorage 后端）
- 设置 SILICONFLOW2_API_KEY
"""

import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from tool_services.overview_service.nexus_tool.tool_service import OverviewToolService
from nexus_sdk.common import MockStorage
from tool_services.test_utils import ensure_storage_ready


async def main():
    ok, backend = await ensure_storage_ready(MockStorage)
    print(f"[selftest] storage backend = {backend} (minio_ok={ok})")

    # SILICONFLOW2_API_KEY is now hardcoded in config.py

    input_key = "task:test:overview"
    await MockStorage.save(
        input_key,
        {
            "summaries": [
                {
                    "paper": {"title": "Paper A", "authors": ["Alice"], "pdf_url": "https://example.com/a.pdf"},
                    "llm_summary": "This paper studies graph neural networks for molecular property prediction.",
                },
                {
                    "paper": {"title": "Paper B", "authors": ["Bob"], "pdf_url": "https://example.com/b.pdf"},
                    "llm_summary": "This paper proposes a new training objective for safer large language models.",
                },
            ],
            "domain": "Machine Learning",
            "style": "academic",
            "target_lang": "en",
        },
    )

    service = OverviewToolService()
    out_key = await service.do_work(input_key, {})
    out = await MockStorage.get(out_key)
    assert out_key.startswith("data:overview:")
    assert "## Background" in out.get("overview_md", "")
    assert "## References" in out.get("overview_md", "")
    print("[selftest] OK:", out_key)


if __name__ == "__main__":
    asyncio.run(main())

