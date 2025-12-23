import os
import sys
import json
from typing import List, Dict, Any

import httpx


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
from . import config  # noqa: E402


class OverviewToolService(BaseToolService):
    """
    Overview ToolService：输入多篇论文的 llm_summary，生成固定英文模板的领域综述。

    输入（storage key 对应 payload）：
    {
      "summaries": [
        {"paper": {"title": "...", "authors": [...], "pdf_url": "..."}, "llm_summary": "..."},
        ...
      ],
      "domain": "optional short domain name",
      "style": "optional, e.g. academic / concise",
      "target_lang": "en"   # 固定 en
    }

    输出：
    - output_key: data:overview:{input_key}
    - 存储内容：{ "overview_md": "...", "meta": {...} }
    """

    def __init__(self):
        super().__init__(service_name="overview", cmd_routing_key="cmd.overview.start")

    async def do_work(self, input_key: str, params: dict) -> str:
        payload = await MockStorage.get(input_key)
        if not payload:
            raise ValueError(f"input_key={input_key} not found in storage")
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")

        if not config.SILICONFLOW2_API_KEY:
            raise RuntimeError("SILICONFLOW2_API_KEY is required for overview generation")

        summaries = payload.get("summaries") or []
        if not isinstance(summaries, list) or not summaries:
            raise ValueError("summaries is required and must be a non-empty list")

        domain = (payload.get("domain") or "").strip()
        style = (payload.get("style") or "").strip()

        prompt = self._build_prompt(summaries=summaries, domain=domain, style=style)
        overview_md = await self._call_siliconflow2(prompt)

        output_key = f"data:overview:{input_key}"
        await MockStorage.save(
            output_key,
            {
                "overview_md": overview_md,
                "meta": {
                    "model": config.SILICONFLOW2_MODEL,
                    "paper_count": len(summaries),
                    "domain": domain,
                    "style": style,
                },
            },
        )
        return output_key

    def _build_prompt(self, summaries: List[Dict[str, Any]], domain: str, style: str) -> str:
        # 去重 + 截断，避免 prompt 过长
        chunks: List[str] = []
        total = 0
        seen = set()

        for item in summaries:
            if not isinstance(item, dict):
                continue
            llm_summary = (item.get("llm_summary") or "").strip()
            paper = item.get("paper") or {}
            if not llm_summary:
                continue

            title = ""
            pdf_url = ""
            authors: List[str] = []
            if isinstance(paper, dict):
                title = (paper.get("title") or "").strip()
                pdf_url = (paper.get("pdf_url") or "").strip()
                authors = paper.get("authors") or []
                if not isinstance(authors, list):
                    authors = []

            key = (title, pdf_url, llm_summary[:80])
            if key in seen:
                continue
            seen.add(key)

            llm_summary = llm_summary[: config.MAX_SUMMARY_CHARS_EACH]
            block = (
                f"- Title: {title or 'N/A'}\n"
                f"  Authors: {', '.join([str(a) for a in authors]) if authors else 'N/A'}\n"
                f"  PDF: {pdf_url or 'N/A'}\n"
                f"  Summary: {llm_summary}\n"
            )

            if total + len(block) > config.MAX_TOTAL_SUMMARY_CHARS:
                break
            chunks.append(block)
            total += len(block)

        if not chunks:
            raise ValueError("no valid llm_summary found in summaries")

        domain_line = f"Domain: {domain}\n" if domain else ""
        style_line = f"Style: {style}\n" if style else ""

        return (
            "You are an expert research survey writer.\n"
            f"{domain_line}"
            f"{style_line}"
            "Given the following paper summaries, write a high-quality domain survey.\n"
            "Return STRICT Markdown with EXACT section headings in this order:\n"
            "## Background\n"
            "## Themes and Methods\n"
            "## Key Findings\n"
            "## Gaps and Limitations\n"
            "## Future Work\n"
            "## References\n"
            "In References, list each paper as a bullet with Title, Authors, and PDF URL.\n\n"
            "Paper summaries:\n"
            + "\n".join(chunks)
        )

    async def _call_siliconflow2(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {config.SILICONFLOW2_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config.SILICONFLOW2_MODEL,
            "messages": [
                {"role": "system", "content": "You follow instructions precisely and output markdown only."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": config.OVERVIEW_MAX_TOKENS,
            "temperature": config.OVERVIEW_TEMPERATURE,
            "top_p": config.OVERVIEW_TOP_P,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(config.SILICONFLOW2_API_BASE, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices") or []
        content = ""
        if choices and isinstance(choices[0], dict):
            msg = choices[0].get("message") or {}
            if isinstance(msg, dict):
                content = (msg.get("content") or "").strip()

        if not content:
            raise RuntimeError("empty overview model response")

        # 简单校验模板头
        if "## Background" not in content or "## References" not in content:
            raise RuntimeError("overview output missing required headings")
        return content


if __name__ == "__main__":
    service = OverviewToolService()
    try:
        import asyncio

        asyncio.run(service.start())
    except KeyboardInterrupt:
        pass

