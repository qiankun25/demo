import os
import sys
import asyncio
from typing import List, Dict, Any, Tuple
import hashlib


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


class RetrievalToolService(BaseToolService):
    """
    Retrieval ToolService：统一检索编排（仅本地检索，不做外部发现）。

    期望输入 (存储 key 数据结构示例):
    {
        "query": "LLM safety",
        "top_k": 5
    }

    输出：
    - output_key: data:retrieval:{input_key}
    - 存储内容: { "query", "local_hits": [...], "external_hits": [], "combined": [...] }

    约定：
    - 若本地无命中，不报错，直接返回空列表。
    """

    def __init__(self):
        super().__init__(service_name="retrieval", cmd_routing_key="cmd.retrieval.start")

    async def do_work(self, input_ref: dict, params: dict) -> tuple[dict, dict]:
        payload = params or {}
        if not isinstance(payload, dict):
            raise ValueError("params must be a dict")

        # Import settings to get config values
        from app.config import settings
        
        query = (payload.get("query") or "").strip()
        limits = settings.limits
        top_k = int(payload.get("top_k", limits.get("search_k_default", 5)))

        local_hits = await self._search_local(query, top_k)
        external_hits: List[Dict[str, Any]] = []  # 不做外部发现
        combined = local_hits[:top_k] if local_hits else []

        query_id_length = settings.query_id_hash_length
        out_id = hashlib.sha256(query.encode("utf-8")).hexdigest()[:query_id_length]
        constants = settings.constants
        storage = constants.get("storage", {})
        retrieval_results_prefix = storage.get("retrieval_results_prefix", "retrieval/results/")
        output_key = f"{retrieval_results_prefix}{out_id}.json"
        await MockStorage.save(
            output_key,
            {"query": query, "local_hits": local_hits, "external_hits": external_hits, "combined": combined},
        )
        return ({"service": "retrieval", "type": "retrieval_result", "id": out_id, "version": "v1"}, {"hit_count": len(combined)})

    async def _search_local(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """在 MinIO(Claim Check) 中遍历解析产物，做简单关键词匹配。"""
        from app.config import settings
        
        hits: List[Tuple[float, Dict[str, Any]]] = []
        scan_limit = settings.local_scan_limit
        # Ref-only mode: parse outputs live under parser/ prefix
        constants = settings.constants
        storage = constants.get("storage", {})
        parser_parsed_prefix = storage.get("parser_parsed_prefix", "parser/parsed:")
        keys = await MockStorage.list_keys(parser_parsed_prefix)
        for k in keys[:scan_limit]:
            v = await MockStorage.get(k)
            if not isinstance(v, dict):
                continue
            chunks = v.get("chunks") or []
            for c in chunks:
                if not isinstance(c, dict):
                    continue
                text = c.get("text", "")
                score = self._score_text(query, text)
                if score > 0:
                    hits.append(
                        (
                            score,
                            {
                                "chunk_id": c.get("chunk_id"),
                                "doc_id": v.get("doc_id"),
                                "text": text,
                                "score": score,
                                "source": "local",
                            },
                        )
                    )
        hits.sort(key=lambda x: x[0], reverse=True)
        return [h[1] for h in hits[:top_k]]

    def _score_text(self, query: str, text: str) -> float:
        if not query or not text:
            return 0.0
        q_tokens = set(query.lower().split())
        t_tokens = text.lower().split()
        if not t_tokens:
            return 0.0
        overlap = len(q_tokens.intersection(t_tokens))
        return overlap / len(q_tokens) if q_tokens else 0.0

if __name__ == "__main__":
    service = RetrievalToolService()
    try:
        import asyncio

        asyncio.run(service.start())
    except KeyboardInterrupt:
        pass