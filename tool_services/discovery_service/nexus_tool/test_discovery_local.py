"""
DiscoveryToolService 本地自测脚本（真实请求 OpenAlex）。

运行：
  python3 tool_services/discovery_service/nexus_tool/test_discovery_local.py

可选环境变量（用于控制测试输入）：
- DISCOVERY_QUERY：默认 "large language model"
- DISCOVERY_LIMIT：默认 5
- DISCOVERY_LAST_N_DAYS：默认 30（最近 N 天，精确到天）
- DISCOVERY_JOURNAL：可选，期刊名模糊匹配（可能导致结果更少/不稳定）
- DISCOVERY_ISSN：可选，逗号分隔的 ISSN 列表（更严格，可能导致 0 结果）
- OPENALEX_MAILTO：可选，启用 polite pool（建议设置）
"""

import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from tool_services.discovery_service.nexus_tool.tool_service import DiscoveryToolService
from nexus_sdk.common import MockStorage
from tool_services.test_utils import ensure_storage_ready


async def main():
    ok, backend = await ensure_storage_ready(MockStorage)
    print(f"[selftest] storage backend = {backend} (minio_ok={ok})")

    query = os.getenv("DISCOVERY_QUERY", "large language model").strip()
    limit = int(os.getenv("DISCOVERY_LIMIT", "5"))
    last_n_days = int(os.getenv("DISCOVERY_LAST_N_DAYS", "30"))
    journal = (os.getenv("DISCOVERY_JOURNAL") or "").strip()
    issn_env = (os.getenv("DISCOVERY_ISSN") or "").strip()
    issn = [x.strip() for x in issn_env.split(",") if x.strip()] if issn_env else None

    input_key = "task:test:discovery"
    await MockStorage.save(
        input_key,
        {
            "query": query,
            "filters": {
                "last_n_days": last_n_days,
                # 可选：期刊/ISSN 过滤（更严格）
                **({"journal": journal} if journal else {}),
                **({"issn": issn} if issn else {}),
            },
            "limit": limit,
        },
    )

    service = DiscoveryToolService()
    output_key = await service.do_work(input_key, {})
    out = await MockStorage.get(output_key)

    assert output_key.startswith("data:discovery:")
    assert isinstance(out, dict)
    assert out.get("query") == query
    assert out.get("query_enhanced"), "query_enhanced should be present"
    assert isinstance(out.get("results"), list)
    assert out.get("request_url"), "request_url should be present"
    # 验证过滤确实写进了 URL（至少包含 from_publication_date）
    assert "from_publication_date" in out["request_url"]
    if journal:
        assert "primary_location.source.display_name.search" in out["request_url"]
    if issn:
        assert "primary_location.source.issn" in out["request_url"]
    # 默认应带 select 精简字段
    assert "select=" in out["request_url"]

    # 真实请求可能因过滤过严导致 0 结果，这里只要求可用性与结构正确；
    # 默认 last_n_days=30 + query 通常会有结果。
    print("[selftest] results:", len(out["results"]))
    print("[selftest] OK:", output_key)


if __name__ == "__main__":
    asyncio.run(main())

