import os
import sys
import asyncio
from typing import Dict, Any, List


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _ensure_nexus_sdk_on_path() -> None:
    """
    支持两种目录布局：
    1) 本仓库根目录的 nexus_sdk
    2) 兼容旧路径 orchestration/RabbitMQ/nexus_sdk
    """
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

from . import config  # noqa: E402
from .filters import encode_filters  # noqa: E402
from .openalex_client import build_works_url, fetch_json_with_retry  # noqa: E402
from .query_enhance import enhance_query  # noqa: E402
from .reducer import reduce_works  # noqa: E402


class DiscoveryToolService(BaseToolService):
    """
    Discovery ToolService：通过 OpenAlex API 做学术资源发现。

    期望输入 (存储 key 对应的数据结构示例):
    {
        "query": "large language model",
        "filters": {
            // 过滤条件（可选；为空/缺失则不按该条件过滤）
            // --- 时间 ---
            // 最近 N 天（精确到天，会转换成 from_publication_date:YYYY-MM-DD）
            "last_n_days": 30,
            // 或者直接指定日期范围（YYYY-MM-DD）
            "from_date": "2024-01-01",
            "to_date": "2024-12-31",
            // --- 期刊/会议（Venue）---
            // 期刊/会议名模糊匹配（OpenAlex: primary_location.source.display_name.search）
            "journal": "Nature",
            // ISSN 精确匹配（OpenAlex: primary_location.source.issn），可为字符串或列表
            "issn": ["0028-0836"],
            // 也可以直接传 OpenAlex 支持的原生字段（会透传）
            "publication_year": "2023",
            "is_oa": "true"
        },
        "limit": 20,           # 每次最大返回条数（默认 20，<=200）
        "sample": None,        # 可选：使用 OpenAlex sample 参数
        "seed": None           # 可选：sample 的 seed
    }

    输出：
    - output_key: data:discovery:{input_key}
    - 存储内容包含 meta + 截断后的 results
    """

    def __init__(self):
        super().__init__(service_name="discovery", cmd_routing_key="cmd.discovery.start")

    async def do_work(self, input_key: str, params: dict) -> str:
        payload = await MockStorage.get(input_key)
        if not payload:
            raise ValueError(f"input_key={input_key} not found in storage")

        raw_query = payload.get("query", "")
        _cleaned, enhanced_query = enhance_query(raw_query)
        filters = payload.get("filters", {}) or {}
        limit = min(int(payload.get("limit", 20)), 200)
        sample = payload.get("sample")
        seed = payload.get("seed")

        mailto = (payload.get("mailto") or config.OPENALEX_MAILTO or "").strip()
        select = (payload.get("select") or config.DEFAULT_SELECT or "").strip()

        filter_str = encode_filters(filters)
        url = build_works_url(
            search=enhanced_query,
            filter_str=filter_str,
            per_page=limit,
            sample=sample,
            seed=seed,
            select=select,
            mailto=mailto,
        )

        data, request_meta = await fetch_json_with_retry(url)

        results: List[Dict[str, Any]] = data.get("results", []) if isinstance(data, dict) else []
        meta = data.get("meta") if isinstance(data, dict) else None
        truncated = results[:limit]
        reduced = reduce_works(truncated)

        output_key = f"data:discovery:{input_key}"
        await MockStorage.save(
            output_key,
            {
                "query": (raw_query or "").strip(),
                "query_enhanced": enhanced_query,
                "filters": filters,
                "request_url": url,
                "request_meta": request_meta,
                "meta": meta,
                "results": reduced,
            },
        )
        return output_key

if __name__ == "__main__":
    service = DiscoveryToolService()
    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        pass
