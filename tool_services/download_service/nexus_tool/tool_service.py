import os
import sys
import uuid
import tempfile
from typing import List, Any, Dict, Optional, Tuple
from urllib.parse import urlparse


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

def _ensure_download_service_on_path() -> None:
    """
    确保 `tool_services/download_service` 在 sys.path 中，
    这样 `from app...`（download_service 内部包）可以被导入。
    """
    download_service_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if os.path.exists(download_service_root):
        if download_service_root in sys.path:
            sys.path.remove(download_service_root)
        sys.path.insert(0, download_service_root)


_ensure_nexus_sdk_on_path()
_ensure_download_service_on_path()

from nexus_sdk.base import BaseToolService  # noqa: E402
from nexus_sdk.common import MockStorage  # noqa: E402

# 复用下载服务实现
from app.services.downloader import PDFDownloader  # noqa: E402


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

    async def do_work(self, input_key: str, params: dict) -> str:
        task_data = await MockStorage.get(input_key)
        if not task_data:
            raise ValueError(f"input_key={input_key} not found in storage")

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

        # 将文件落到临时目录，返回引用路径（可替换为 MinIO/S3）
        temp_dir = tempfile.gettempdir()
        object_name = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(temp_dir, object_name)
        with open(file_path, "wb") as f:
            f.write(content)

        output_key = f"data:download:{input_key}"
        await MockStorage.save(
            output_key,
            {
                # 供下游解析的关键信息（用户希望以 url 作为主线）
                "pdf_url": chosen_url,
                "file_path": file_path,
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
        - best_oa_location.pdf_url
        - locations[].pdf_url
        - arXiv /abs/ -> /pdf/xxx.pdf 的兜底
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
            # best_oa_location.pdf_url
            bol = w.get("best_oa_location") or {}
            if isinstance(bol, dict):
                u = _normalize_pdf_url(_safe_str(bol.get("pdf_url")))
                if u:
                    out.append((u, meta))
                    continue

            # locations[].pdf_url
            locs = w.get("locations") or []
            if isinstance(locs, list):
                for loc in locs:
                    if not isinstance(loc, dict):
                        continue
                    u = _normalize_pdf_url(_safe_str(loc.get("pdf_url")))
                    if u:
                        out.append((u, meta))
                        break

            # 兜底：尝试从 landing_page_url 推断 arXiv abs
            if not any(x[1].get("id") == meta.get("id") for x in out):
                # try best_oa_location.landing_page_url
                if isinstance(bol, dict):
                    lp = _normalize_pdf_url(_safe_str(bol.get("landing_page_url")))
                    if lp and "arxiv.org/abs/" in lp:
                        out.append((lp, meta))
                        continue

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