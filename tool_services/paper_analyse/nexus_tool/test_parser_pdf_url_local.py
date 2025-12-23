"""
ParserToolService 本地自测脚本：以 pdf_url 作为输入（离线可跑）。

说明：
- 为了避免依赖外网，这里使用 file:// URL 指向仓库内自带 PDF 文件。
- 这能覆盖 MORNING_REPORT 里“按 url 下载/解析”的代码路径（file:// 也属于 url）。

运行：
  python3 tool_services/paper_analyse/nexus_tool/test_parser_pdf_url_local.py
"""

import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from tool_services.paper_analyse.nexus_tool.tool_service import ParserToolService
from nexus_sdk.common import MockStorage
from tool_services.test_utils import ensure_storage_ready


PDF_PATH = "/Users/h/Desktop/2025_au/mic/demo-main/tool_services/paper_analyse/nexus_tool/2105.13495v2.pdf"


async def main():
    ok, backend = await ensure_storage_ready(MockStorage)
    print(f"[selftest] storage backend = {backend} (minio_ok={ok})")

    if not PDF_PATH or not os.path.exists(PDF_PATH):
        raise RuntimeError("Please set PDF_PATH to an existing PDF file.")

    input_key = "task:test:pdf_url"
    await MockStorage.save(
        input_key,
        {
            "pdf_url": "file://" + PDF_PATH,
            "filename": os.path.basename(PDF_PATH),
            "source_url": "file://" + PDF_PATH,
            "size_bytes": os.path.getsize(PDF_PATH),
            "content_type": "application/pdf",
        },
    )

    service = ParserToolService()
    output_key = await service.do_work(input_key, {})
    result = await MockStorage.get(output_key)

    assert output_key.startswith("data:parse:")
    assert result.get("doc_id")
    assert result.get("fulltext_hash")
    assert isinstance(result.get("chunks", []), list) and len(result["chunks"]) > 0
    print("[selftest] OK:", output_key, "chunks=", len(result["chunks"]))


if __name__ == "__main__":
    asyncio.run(main())

