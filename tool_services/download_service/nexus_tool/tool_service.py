import os
import sys
import uuid
import re
from typing import List, Any, Dict, Optional, Tuple
from urllib.parse import urlparse

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

class PDFDownloader:
    """
    轻量 PDF 下载器（Downloader MQ tool 自包含实现）：
    - 避免依赖 download_service/app 的顶层包名 `app`，从根上消除包冲突
    - 返回 (content_bytes, filename)
    """

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    async def download(self, url: str) -> Tuple[bytes, str]:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()

                content_type = (response.headers.get("content-type") or "").lower()
                if "pdf" not in content_type and "application/pdf" not in content_type:
                    raise ValueError(f"Invalid content type: {content_type}. Expected PDF content.")

                filename = self._extract_filename(response.headers, url)

                buf = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    buf += chunk
                return bytes(buf), filename

    def _extract_filename(self, headers: httpx.Headers, url: str) -> str:
        cd = headers.get("content-disposition", "") or ""
        if cd:
            m = re.search(r'filename\*?=(["\']?)(.+?)\1(?:;|$)', cd, re.IGNORECASE)
            if m:
                name = re.sub(r"^UTF-8''", "", m.group(2), flags=re.IGNORECASE).strip()
                if name:
                    return name

        parsed = urlparse(url)
        name = (parsed.path.split("/")[-1] or "").strip()
        if not name.lower().endswith(".pdf"):
            name = "document.pdf"
        return name


class DownloaderToolService(BaseToolService):
    """
    Downloader ToolService：对接 download_service 的下载逻辑。

    期望输入 (存储 key 对应的数据结构示例):
    {
        "urls": ["https://arxiv.org/pdf/1234.5678.pdf"],
        "timeout": 30    # 可选
    }

    输出：
    - output_key: data:download:{input_key}
    - 存储内容: {"file_path", "filename", "size_bytes", "source_url", "content_type"}
    """

    def __init__(self):
        super().__init__(service_name="downloader", cmd_routing_key="cmd.downloader.start")

    async def do_work(self, input_ref: dict, params: dict) -> tuple[dict, dict]:
        # Deprecated in ref-only mode. Use `tool_services/download_service/app/mq_worker.py` instead.
        raise RuntimeError(
            "DownloaderToolService (nexus_tool) is deprecated in ref-only mode; "
            "use download-service mq_worker (cmd.downloader.start -> evt.downloader.finished file_ref)."
        )

        # 支持两种输入：
        # 1) 旧：{"urls":[...]}
        # 2) 新：discovery 输出：{"results":[...], ...}
        # 3) fan-out：单个 work：{"work":{...}, ...}
        candidates: List[Tuple[str, Dict[str, Any]]] = []
        if isinstance(task_data, dict) and isinstance(task_data.get("work"), dict):
            candidates = self._extract_pdf_candidates({"results": [task_data["work"]]})
        elif isinstance(task_data, dict) and (task_data.get("results") is not None):
            candidates = self._extract_pdf_candidates(task_data)
        else:
            urls: List[str] = (task_data.get("urls") or []) if isinstance(task_data, dict) else []
            for u in urls:
                if u:
                    candidates.append((str(u), {}))

        if not candidates:
            raise ValueError("No downloadable PDF url candidates found")

        timeout = int(task_data.get("timeout", 30))

        downloader = PDFDownloader(timeout=timeout)
        last_err: Optional[Exception] = None
        content: Optional[bytes] = None
        filename: Optional[str] = None
        chosen_url: Optional[str] = None
        chosen_meta: Dict[str, Any] = {}

        for u, meta in candidates:
            try:
                content, filename = await downloader.download(u)
                chosen_url = u
                chosen_meta = meta or {}
                break
            except Exception as e:
                last_err = e
                continue

        if content is None or filename is None or chosen_url is None:
            raise RuntimeError(f"All download attempts failed. last_error={last_err}")

        # 不再落盘到 /tmp：直接把 PDF bytes 存到 ClaimCheck（MinIO）
        safe_filename = (filename or "").strip().split("/")[-1].split("\\")[-1] or "document.pdf"
        pdf_storage_key = f"blob/pdf/{uuid.uuid4()}_{safe_filename}"
        await MockStorage.save(pdf_storage_key, content)

        output_key = f"data:download:{input_key}"
        await MockStorage.save(
            output_key,
            {
                # 供下游解析的关键信息（用户希望以 url 作为主线）
                "pdf_url": chosen_url,
                # 新主线：通过 MinIO ClaimCheck 交接 PDF bytes（跨容器稳定）
                "pdf_storage_key": pdf_storage_key,
                # 兼容字段：历史上会传 file_path；现在不再依赖本地文件
                "file_path": "",
                "filename": filename,
                "size_bytes": len(content),
                "source_url": chosen_url,
                "content_type": "application/pdf",
                "work": chosen_meta,
            },
        )
        return output_key

    def _extract_pdf_candidates(self, discovery_payload: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
        """
        从 OpenAlex discovery 的 results 中提取可下载 PDF 的候选 url。
        优先顺序：
        - work.pdf_url（discovery reducer 提供的最优直链）
        - best_oa_location.pdf_url
        - primary_location.pdf_url
        - locations[].pdf_url
        - landing_page_url/url（若看起来像 pdf 直链，或 arXiv abs 可推断）
        """
        results = discovery_payload.get("results") or []
        out: List[Tuple[str, Dict[str, Any]]] = []

        def _safe_str(x: Any) -> str:
            return str(x).strip() if x is not None else ""

        def _normalize_pdf_url(u: str) -> str:
            u = u.strip()
            if not u:
                return ""
            # arXiv abs -> pdf
            if "arxiv.org/abs/" in u:
                u = u.replace("arxiv.org/abs/", "arxiv.org/pdf/")
                if not u.lower().endswith(".pdf"):
                    u = u + ".pdf"
            return u

        def _maybe_pdf_url(u: str) -> str:
            """
            Accept URLs that are likely PDF:
            - explicit .pdf suffix
            - arXiv abs/pdf URLs (normalized)
            """
            u = (u or "").strip()
            if not u:
                return ""
            u2 = _normalize_pdf_url(u)
            if not u2:
                return ""
            ul = u2.lower()
            if ul.endswith(".pdf"):
                return u2
            if "arxiv.org/pdf/" in ul:
                return u2 if ul.endswith(".pdf") else (u2 + ".pdf")
            return ""

        def _extract_authors(work: Dict[str, Any]) -> List[str]:
            authorships = work.get("authorships") or []
            names: List[str] = []
            if isinstance(authorships, list):
                for a in authorships:
                    if not isinstance(a, dict):
                        continue
                    author = a.get("author") or {}
                    if isinstance(author, dict):
                        name = str(author.get("display_name") or "").strip()
                        if name:
                            names.append(name)
            # 去重保持顺序
            seen = set()
            out_names: List[str] = []
            for n in names:
                if n in seen:
                    continue
                seen.add(n)
                out_names.append(n)
            return out_names

        for w in results if isinstance(results, list) else []:
            if not isinstance(w, dict):
                continue
            meta = {
                "openalex_id": w.get("id"),
                "title": w.get("display_name") or w.get("title"),
                "doi": w.get("doi"),
                "publication_date": w.get("publication_date"),
                "authors": _extract_authors(w),
            }

            # 0) direct reduced field: work.pdf_url (preferred)
            u0 = _maybe_pdf_url(_safe_str(w.get("pdf_url")))
            if u0:
                out.append((u0, meta))
                continue

            # best_oa_location.pdf_url
            bol = w.get("best_oa_location") or {}
            if isinstance(bol, dict):
                u = _maybe_pdf_url(_safe_str(bol.get("pdf_url")))
                if u:
                    out.append((u, meta))
                    continue

                # best_oa_location.landing_page_url / url may be a pdf link or arXiv abs
                for k in ("landing_page_url", "url"):
                    u_lp = _maybe_pdf_url(_safe_str(bol.get(k)))
                    if u_lp:
                        out.append((u_lp, meta))
                        break
                if any(x[1].get("openalex_id") == meta.get("openalex_id") for x in out):
                    continue

            # primary_location.pdf_url / landing_page_url
            pl = w.get("primary_location") or {}
            if isinstance(pl, dict):
                u = _maybe_pdf_url(_safe_str(pl.get("pdf_url")))
                if u:
                    out.append((u, meta))
                    continue
                for k in ("landing_page_url", "url"):
                    u_lp = _maybe_pdf_url(_safe_str(pl.get(k)))
                    if u_lp:
                        out.append((u_lp, meta))
                        break
                if any(x[1].get("openalex_id") == meta.get("openalex_id") for x in out):
                    continue

            # locations[].pdf_url
            locs = w.get("locations") or []
            if isinstance(locs, list):
                for loc in locs:
                    if not isinstance(loc, dict):
                        continue
                    u = _maybe_pdf_url(_safe_str(loc.get("pdf_url")))
                    if u:
                        out.append((u, meta))
                        break

                    # Some sources only provide landing_page_url; accept if it looks like a pdf (or arXiv abs)
                    for k in ("landing_page_url", "url"):
                        u_lp = _maybe_pdf_url(_safe_str(loc.get(k)))
                        if u_lp:
                            out.append((u_lp, meta))
                            break
                    if any(x[1].get("openalex_id") == meta.get("openalex_id") for x in out):
                        break

            # 兜底：如果仍没有候选，尝试从 work.url / landing_page_url 推断 arXiv abs
            if not any(x[1].get("openalex_id") == meta.get("openalex_id") for x in out):
                for k in ("landing_page_url", "url"):
                    lp = _maybe_pdf_url(_safe_str(w.get(k)))
                    if lp:
                        out.append((lp, meta))
                        break

        # 去重（保持顺序）
        seen = set()
        dedup: List[Tuple[str, Dict[str, Any]]] = []
        for u, m in out:
            if not u:
                continue
            key = u
            if key in seen:
                continue
            seen.add(key)
            dedup.append((u, m))
        return dedup


if __name__ == "__main__":
    service = DownloaderToolService()
    try:
        import asyncio

        asyncio.run(service.start())
    except KeyboardInterrupt:
        pass