"""
Minimal local test for ParserToolService.
Run: python tool_services/paper_analyse/nexus_tool/test_parser_local.py

Requirements:
- PyPDF2 (for parsing)
- Place a PDF file path in PDF_PATH below.
"""

import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from tool_services.paper_analyse.nexus_tool.tool_service import ParserToolService
# 与 ParserToolService 保持一致，使用 nexus_sdk.common.MockStorage，避免两个独立存储实例
from nexus_sdk.common import MockStorage

PDF_PATH = "/Users/h/Desktop/2025_au/mic/demo-main/tool_services/paper_analyse/nexus_tool/2105.13495v2.pdf"


async def main():
    if not PDF_PATH or not os.path.exists(PDF_PATH):
        print("Please set PDF_PATH to an existing PDF file.")
        return

    input_key = "task:test:pdf"
    await MockStorage.save(
        input_key,
        {
            "file_path": PDF_PATH,
            "filename": os.path.basename(PDF_PATH),
            "source_url": "local",
            "size_bytes": os.path.getsize(PDF_PATH),
            "content_type": "application/pdf",
        },
    )

    service = ParserToolService()
    output_key = await service.do_work(input_key, {})
    result = await MockStorage.get(output_key)
    print("Output key:", output_key)
    print("Doc ID:", result.get("doc_id"))
    print("Fulltext hash:", result.get("fulltext_hash"))
    print("Chunks:", len(result.get("chunks", [])))
    print("LLM summary:", result.get("llm_summary"))


if __name__ == "__main__":
    asyncio.run(main())
