import os
import sys
import uuid
import hashlib
import tempfile
from typing import List, Dict, Any, Tuple

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


class ParserToolService(BaseToolService):
    """
    Parser ToolService：解析 PDF -> 清洗 -> 分块 -> 哈希 -> 调用 SiliconFlow 生成总述。

    输入 (Storage key 数据结构):
    {
        "file_path": "/tmp/xxx.pdf",       # 可选：若存在则直接解析
        "pdf_url": "https://.../paper.pdf",# 可选：用于下载后解析（优先符合 MORNING_REPORT 主线）
        "filename": "paper.pdf",
        "source_url": "...",
        "size_bytes": 1234
    }

    输出 (data:parse:{input_key}):
    {
        "doc_id": "...",
        "title": "...",
        "chunks": [{"chunk_id","text","page","hash"}],
        "fulltext_hash": "...",
        "llm_summary": "English overview ...",
        "meta": {...}
    }
    """

    def __init__(self):
        super().__init__(service_name="parser", cmd_routing_key="cmd.parser.start")

    async def do_work(self, input_key: str, params: dict) -> str:
        payload = await MockStorage.get(input_key)
        if not payload:
            raise ValueError(f"input_key={input_key} not found in storage")

        pdf_url = payload.get("pdf_url") or payload.get("source_url")
        file_path = payload.get("file_path")

        # 用户选择：以 pdf_url 为主线；若 pdf_url 存在则优先走下载
        if pdf_url:
            # 不允许兜底：只要提供了 pdf_url，下载失败就直接抛错
            file_path = await self._materialize_pdf_from_url(str(pdf_url))

        if not file_path or not os.path.exists(file_path):
            raise ValueError(f"file_path missing or not exists: {file_path}")

        filename = payload.get("filename") or os.path.basename(file_path)
        source_url = pdf_url or payload.get("source_url")

        pages_text = self._extract_pdf(file_path)
        cleaned_pages, full_hash, prompt_text = self._clean_hash_and_prompt(pages_text)
        if not cleaned_pages:
            raise ValueError("parsed text is empty after cleaning")

        chunks = self._chunk_from_pages(cleaned_pages)
        doc_id = full_hash[:24]

        llm_summary = await self._summarize(prompt_text, title=filename, source_url=source_url)

        result = {
            "doc_id": doc_id,
            "title": filename,
            "chunks": chunks,
            "fulltext_hash": full_hash,
            "llm_summary": llm_summary,
            "meta": {
                "source_url": source_url,
                "filename": filename,
                "size_bytes": payload.get("size_bytes"),
                "content_type": payload.get("content_type"),
            },
        }

        output_key = f"data:parse:{input_key}"
        await MockStorage.save(output_key, result)
        return output_key

    async def _materialize_pdf_from_url(self, pdf_url: str) -> str:
        """
        将 pdf_url 下载到本地临时文件并返回路径。
        - 支持 http(s) url
        - 支持 file:// url（便于本地测试）
        """
        u = (pdf_url or "").strip()
        if not u:
            raise ValueError("pdf_url is empty")

        if u.startswith("file://"):
            local_path = u[len("file://") :]
            return local_path

        if u.startswith("http://") or u.startswith("https://"):
            try:
                async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                    resp = await client.get(u)
                    resp.raise_for_status()
                    content = resp.content
            except Exception as e:
                raise RuntimeError(f"download pdf_url failed: {u} err={e}") from e

            tmp_dir = tempfile.gettempdir()
            name = f"{uuid.uuid4()}.pdf"
            out_path = os.path.join(tmp_dir, name)
            with open(out_path, "wb") as f:
                f.write(content)
            return out_path

        raise ValueError(f"unsupported pdf_url scheme: {u}")

    # --- PDF 解析与清洗 ---
    def _extract_pdf(self, path: str) -> List[str]:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            raise ImportError("PyPDF2 is required for PDF parsing. Please install it.")

        reader = PdfReader(path)
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages.append(text)
        return pages

    def _clean_text(self, pages: List[str]) -> List[str]:
        if not pages:
            return []
        cleaned_pages = []
        stop = False
        for idx, txt in enumerate(pages):
            lower = (txt or "").lower()
            # 若检测到参考文献标题，截断后续内容
            if any(k in lower for k in config.REFERENCE_KEYWORDS):
                stop = True
                break
            lines = [l.strip() for l in (txt or "").splitlines()]
            lines = [l for l in lines if l]
            cleaned_pages.append(" ".join(lines))
        return cleaned_pages if not stop else cleaned_pages

    def _clean_hash_and_prompt(self, pages: List[str]) -> Tuple[List[str], str, str]:
        """
        清洗 + 计算全文 hash（流式）+ 生成用于 LLM 的 prompt_text（截断，避免超大输入）。
        """
        cleaned_pages: List[str] = []
        h = hashlib.sha256()
        prompt_parts: List[str] = []
        prompt_len = 0
        stop = False

        for txt in pages or []:
            lower = (txt or "").lower()
            if any(k in lower for k in config.REFERENCE_KEYWORDS):
                stop = True
                break
            lines = [l.strip() for l in (txt or "").splitlines()]
            lines = [l for l in lines if l]
            cleaned = " ".join(lines)
            if not cleaned:
                continue

            # 控制最大处理字符，避免内存/存储过大
            if sum(len(p) for p in cleaned_pages) >= config.MAX_TEXT_CHARS:
                break

            cleaned_pages.append(cleaned)

            # hash 流式更新
            h.update(cleaned.encode("utf-8", errors="ignore"))
            h.update(b"\n\n")

            # prompt_text 只取前 MAX_TEXT_CHARS 的一小部分（更省 token）
            if prompt_len < min(config.MAX_TEXT_CHARS, 20000):
                take = min(len(cleaned), min(config.MAX_TEXT_CHARS, 20000) - prompt_len)
                if take > 0:
                    prompt_parts.append(cleaned[:take])
                    prompt_len += take

        full_hash = h.hexdigest()
        prompt_text = "\n\n".join(prompt_parts).strip()
        return cleaned_pages, full_hash, prompt_text

    # --- 分块与哈希（基于页面，避免拼接巨大 full_text） ---
    def _chunk_from_pages(self, pages: List[str]) -> List[Dict[str, Any]]:
        size = config.CHUNK_SIZE
        overlap = config.CHUNK_OVERLAP
        max_chunks = config.MAX_CHUNKS

        chunks: List[Dict[str, Any]] = []
        buf = ""
        page_idx = 0

        for page_idx, page_text in enumerate(pages, start=1):
            if not page_text:
                continue
            # 将页面文本追加到 buffer
            if buf:
                buf += "\n\n"
            buf += page_text

            # 从 buffer 中切 chunk
            while len(buf) >= size and len(chunks) < max_chunks:
                chunk_text = buf[:size]
                chunks.append(
                    {
                        "chunk_id": str(uuid.uuid4()),
                        "text": chunk_text,
                        "page": page_idx,
                        "hash": self._sha256(chunk_text),
                    }
                )
                # 滑窗：保留 overlap
                buf = buf[size - overlap :] if overlap > 0 else buf[size:]

            if len(chunks) >= max_chunks:
                break

        # 最后剩余 buffer
        if buf.strip() and len(chunks) < max_chunks:
            chunk_text = buf[:size]
            chunks.append(
                {
                    "chunk_id": str(uuid.uuid4()),
                    "text": chunk_text,
                    "page": page_idx if page_idx else None,
                    "hash": self._sha256(chunk_text),
                }
            )
        return chunks

    # --- LLM 总述 ---
    async def _summarize(self, text: str, title: str, source_url: str = None) -> str:
        if not config.SILICONFLOW_API_KEY:
            return ""
        # 限制输入长度，防止超大 prompt
        prompt_text = (text or "")[: min(len(text or ""), 20000)]
        system_prompt = "You are an expert academic summarizer. Provide a concise English overview of the paper."
        user_prompt = f"Title: {title}\nSource: {source_url or 'N/A'}\nContent:\n{prompt_text}"

        headers = {
            "Authorization": f"Bearer {config.SILICONFLOW_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config.DEFAULT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": config.SUMMARY_MAX_TOKENS,
            "temperature": config.SUMMARY_TEMPERATURE,
            "top_p": config.SUMMARY_TOP_P,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(config.API_BASE, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices") or []
                if choices and "message" in choices[0]:
                    return choices[0]["message"].get("content", "").strip()
                return ""
        except Exception as e:
            print(f"[parser] LLM summary failed: {e}")
            return ""

    # --- 工具函数 ---
    def _sha256(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


if __name__ == "__main__":
    service = ParserToolService()
    try:
        import asyncio

        asyncio.run(service.start())
    except KeyboardInterrupt:
        pass