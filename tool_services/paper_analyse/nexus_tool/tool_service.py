import os
import sys
import uuid
import hashlib
import tempfile
from io import BytesIO
import time
from typing import List, Dict, Any, Tuple, Optional

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
from .errors import DownloadFailed, ParseFailed, LLMFailed  # noqa: E402
from .logging_utils import log_json  # noqa: E402
from .extractors.chain import FallbackExtractorChain  # noqa: E402
from .extractors.external_cmd_extractor import ExternalCommandExtractor  # noqa: E402
from .extractors.ocr_tesseract_extractor import TesseractOCRExtractor  # noqa: E402
from .extractors.pdfplumber_extractor import PdfPlumberExtractor  # noqa: E402
from .extractors.pypdf2_extractor import PyPDF2Extractor  # noqa: E402
from .extractors.unstructured_extractor import UnstructuredExtractor  # noqa: E402
from .structure import iter_paragraphs, drop_references, pack_chunks_by_paragraphs  # noqa: E402


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
        t0 = time.monotonic()
        payload = await MockStorage.get(input_key)
        if not payload:
            raise ValueError(f"input_key={input_key} not found in storage")

        trace_id = self._infer_trace_id(input_key=input_key, params=params, payload=payload)

        output_key = f"data:parse:{input_key}"
        # Idempotency: if already processed for this input_key, reuse and optionally backfill missing fields
        existing = await MockStorage.get(output_key)
        if isinstance(existing, dict) and existing.get("doc_id") and isinstance(existing.get("chunks"), list):
            backfilled = False
            if (not (existing.get("llm_summary") or "").strip()) and config.SILICONFLOW_API_KEY:
                # best-effort backfill from existing chunks (avoid re-parse)
                prompt_text = self._prompt_text_from_chunks(existing.get("chunks") or [])
                if prompt_text:
                    existing["llm_summary"] = await self._summarize(
                        prompt_text,
                        title=str(existing.get("title") or ""),
                        source_url=(existing.get("meta") or {}).get("source_url") if isinstance(existing.get("meta"), dict) else None,
                        trace_id=trace_id,
                        input_key=input_key,
                        doc_id=str(existing.get("doc_id") or ""),
                    )
                    backfilled = True
            if backfilled:
                await MockStorage.save(output_key, existing)
            log_json(
                level="info",
                event="parse.cache_hit.by_input_key",
                trace_id=trace_id,
                input_key=input_key,
                doc_id=str(existing.get("doc_id") or ""),
                fields={
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                    "page_count": self._safe_page_count(existing),
                    "chunk_count": len(existing.get("chunks") or []),
                    "backfilled": backfilled,
                },
            )
            return output_key

        pdf_storage_key = (payload.get("pdf_storage_key") or "").strip() if isinstance(payload, dict) else ""
        pdf_url = payload.get("pdf_url") or payload.get("source_url")
        file_path = payload.get("file_path")

        # 优先级：pdf_storage_key > pdf_url > file_path
        pdf_bytes: Optional[bytes] = None
        if pdf_storage_key:
            b = await MockStorage.get(pdf_storage_key)
            if isinstance(b, (bytes, bytearray, memoryview)):
                pdf_bytes = bytes(b)
            else:
                raise ValueError(f"pdf_storage_key={pdf_storage_key} is not bytes")

        if pdf_bytes is None:
            # 用户选择：以 pdf_url 为主线；若 pdf_url 存在则优先走下载
            if pdf_url:
                # 不允许兜底：只要提供了 pdf_url，下载失败就直接抛错
                file_path = await self._materialize_pdf_from_url(str(pdf_url), trace_id=trace_id, input_key=input_key)

            if not file_path or not os.path.exists(file_path):
                raise ValueError(f"file_path missing or not exists: {file_path}")
            # Ensure bytes for external extractor and stable behaviour across extractors
            try:
                with open(file_path, "rb") as f:
                    pdf_bytes = f.read()
            except Exception as e:
                raise DownloadFailed(f"read local pdf failed: {file_path} err={e}", cause=e) from e

        filename = payload.get("filename") or (os.path.basename(file_path) if file_path else "")
        source_url = pdf_url or payload.get("source_url")

        log_json(level="info", event="parse.start", trace_id=trace_id, input_key=input_key, fields={"has_pdf_storage_key": bool(pdf_storage_key), "has_pdf_url": bool(pdf_url)})

        # Parse with fallback extractors
        try:
            pages_text, extractor_name, attempts = self._extract_pages_with_fallback(pdf_bytes=pdf_bytes, path=file_path)
        except Exception as e:
            log_json(
                level="error",
                event="parse.failed.extract",
                trace_id=trace_id,
                input_key=input_key,
                fields={"error": str(e), "duration_ms": int((time.monotonic() - t0) * 1000)},
            )
            raise ParseFailed("pdf text extraction failed", cause=e) from e

        cleaned_pages, full_hash, prompt_text = self._clean_hash_and_prompt(pages_text)
        if not cleaned_pages:
            raise ParseFailed("parsed text is empty after cleaning")

        doc_id = full_hash[:24]

        # Cache by fulltext_hash: reuse prior parse result (avoid re-LLM and/or re-chunk)
        cache_hit = False
        cached_parse_key = await self._cache_get_parse_key(full_hash)
        cached_result: Optional[Dict[str, Any]] = None
        if cached_parse_key:
            cd = await MockStorage.get(cached_parse_key)
            if isinstance(cd, dict) and cd.get("doc_id") and isinstance(cd.get("chunks"), list) and cd.get("fulltext_hash") == full_hash:
                cached_result = cd
                cache_hit = True

        if cache_hit and cached_result is not None:
            # Backfill missing summary if needed using current prompt_text (we already parsed for hash)
            if (not (cached_result.get("llm_summary") or "").strip()) and config.SILICONFLOW_API_KEY and prompt_text:
                cached_result["llm_summary"] = await self._summarize(
                    prompt_text,
                    title=filename,
                    source_url=source_url,
                    trace_id=trace_id,
                    input_key=input_key,
                    doc_id=doc_id,
                )
                try:
                    await MockStorage.save(cached_parse_key, cached_result)
                except Exception:
                    # best-effort; don't fail parse
                    pass
            result = cached_result
        else:
            chunks = self._chunk_from_pages(cleaned_pages)
            llm_summary = await self._summarize(prompt_text, title=filename, source_url=source_url, trace_id=trace_id, input_key=input_key, doc_id=doc_id)
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

        await MockStorage.save(output_key, result)

        # Update cache mapping (store a pointer to an existing data:parse:* key without creating new parse entries)
        try:
            await self._cache_put_parse_key(full_hash, output_key)
        except Exception:
            pass

        log_json(
            level="info",
            event="parse.done",
            trace_id=trace_id,
            input_key=input_key,
            doc_id=doc_id,
            fields={
                "duration_ms": int((time.monotonic() - t0) * 1000),
                "page_count": len(cleaned_pages),
                "chunk_count": len(result.get("chunks") or []),
                "extractor": extractor_name,
                "cache_hit": cache_hit,
                "extractor_attempts": [a.__dict__ for a in attempts],
            },
        )
        return output_key

    async def _materialize_pdf_from_url(self, pdf_url: str, *, trace_id: Optional[str] = None, input_key: Optional[str] = None) -> str:
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
                log_json(level="error", event="download.failed", trace_id=trace_id, input_key=input_key, fields={"pdf_url": u, "error": str(e)})
                raise DownloadFailed(f"download pdf_url failed: {u} err={e}", cause=e) from e

            tmp_dir = tempfile.gettempdir()
            name = f"{uuid.uuid4()}.pdf"
            out_path = os.path.join(tmp_dir, name)
            with open(out_path, "wb") as f:
                f.write(content)
            return out_path

        raise ValueError(f"unsupported pdf_url scheme: {u}")

    # --- PDF 解析（可插拔 + 降级） ---
    def _build_extractor_chain(self) -> FallbackExtractorChain:
        name_to_ex = {
            "external_cmd": ExternalCommandExtractor(),
            "pypdf2": PyPDF2Extractor(),
            "pdfplumber": PdfPlumberExtractor(),
            "unstructured": UnstructuredExtractor(),
            "ocr_tesseract": TesseractOCRExtractor(),
        }
        ex_list = []
        for n in (config.EXTRACTOR_ORDER or []):
            ex = name_to_ex.get(n)
            if ex is not None:
                ex_list.append(ex)
        if not ex_list:
            ex_list = [PyPDF2Extractor()]
        return FallbackExtractorChain(ex_list)

    def _extract_pages_with_fallback(
        self, *, pdf_bytes: Optional[bytes] = None, path: Optional[str] = None
    ) -> Tuple[List[str], str, List[Any]]:
        chain = self._build_extractor_chain()
        res, attempts = chain.extract_pages(pdf_bytes=pdf_bytes, path=path)
        return res.pages, res.extractor_name, attempts

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

        # paragraph/heading-aware chunking (schema stays the same)
        paras = list(iter_paragraphs(pages))
        paras = drop_references(paras, config.REFERENCE_KEYWORDS)
        packed = pack_chunks_by_paragraphs(paras, chunk_size=size, chunk_overlap=overlap, max_chunks=max_chunks)
        chunks: List[Dict[str, Any]] = []
        for page, chunk_text in packed:
            if not chunk_text:
                continue
            chunks.append(
                {
                    "chunk_id": str(uuid.uuid4()),
                    "text": chunk_text,
                    "page": page,
                    "hash": self._sha256(chunk_text),
                }
            )
        return chunks

    # --- LLM 总述 ---
    async def _summarize(
        self,
        text: str,
        title: str,
        source_url: str = None,
        *,
        trace_id: Optional[str] = None,
        input_key: Optional[str] = None,
        doc_id: Optional[str] = None,
    ) -> str:
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
            t0 = time.monotonic()
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(config.API_BASE, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices") or []
                if choices and "message" in choices[0]:
                    log_json(
                        level="info",
                        event="llm.summary.ok",
                        trace_id=trace_id,
                        input_key=input_key,
                        doc_id=doc_id,
                        fields={"duration_ms": int((time.monotonic() - t0) * 1000), "model": config.DEFAULT_MODEL},
                    )
                    return choices[0]["message"].get("content", "").strip()
                return ""
        except Exception as e:
            log_json(
                level="error",
                event="llm.summary.failed",
                trace_id=trace_id,
                input_key=input_key,
                doc_id=doc_id,
                fields={"error": str(LLMFailed(str(e), cause=e)), "model": config.DEFAULT_MODEL},
            )
            return ""

    # --- 工具函数 ---
    def _sha256(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()

    def _cache_key_fulltext_hash(self, fulltext_hash: str) -> str:
        return f"{config.CACHE_FULLTEXT_HASH_PREFIX}{fulltext_hash}"

    async def _cache_get_parse_key(self, fulltext_hash: str) -> Optional[str]:
        k = self._cache_key_fulltext_hash(fulltext_hash)
        v = await MockStorage.get(k)
        if isinstance(v, str) and v.startswith("data:parse:"):
            return v
        return None

    async def _cache_put_parse_key(self, fulltext_hash: str, parse_key: str) -> None:
        k = self._cache_key_fulltext_hash(fulltext_hash)
        await MockStorage.save(k, str(parse_key))

    def _infer_trace_id(self, *, input_key: str, params: dict, payload: Any) -> str:
        # 1) params override (if upstream puts it here)
        if isinstance(params, dict):
            for k in ("trace_id", "request_id", "rid"):
                v = (params.get(k) or "").strip() if isinstance(params.get(k), str) else ""
                if v:
                    return v
        # 2) payload may include it (best-effort)
        if isinstance(payload, dict):
            v = (payload.get("trace_id") or "").strip() if isinstance(payload.get("trace_id"), str) else ""
            if v:
                return v
        # 3) infer from input_key patterns: task:{trace_id}:... or task-...
        ik = str(input_key or "")
        if ik.startswith("task:"):
            parts = ik.split(":")
            if len(parts) >= 2 and parts[1]:
                return parts[1]
        return ""

    def _prompt_text_from_chunks(self, chunks: List[Dict[str, Any]]) -> str:
        parts: List[str] = []
        total = 0
        for c in chunks or []:
            t = c.get("text") if isinstance(c, dict) else ""
            if not isinstance(t, str) or not t:
                continue
            take = min(len(t), 20000 - total)
            if take <= 0:
                break
            parts.append(t[:take])
            total += take
        return "\n\n".join(parts).strip()

    def _safe_page_count(self, parsed: Dict[str, Any]) -> int:
        # existing outputs don't store page_count explicitly; approximate via max(page) in chunks
        chunks = parsed.get("chunks") or []
        if not isinstance(chunks, list):
            return 0
        mx = 0
        for c in chunks:
            if not isinstance(c, dict):
                continue
            p = c.get("page")
            if isinstance(p, int) and p > mx:
                mx = p
        return mx


if __name__ == "__main__":
    service = ParserToolService()
    try:
        import asyncio

        asyncio.run(service.start())
    except KeyboardInterrupt:
        pass