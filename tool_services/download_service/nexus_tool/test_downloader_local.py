"""
DownloaderToolService (nexus_tool) 本地自测脚本（真实请求）。

注意：这个脚本测试的是 tool_services/download_service/nexus_tool/tool_service.py
里 “DownloaderToolService” 的逻辑（会把 bytes 写入本机临时目录，并把路径元数据写入 MockStorage）。

运行：
  python3 tool_services/download_service/nexus_tool/test_downloader_local.py
"""

import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import tool_services.download_service.nexus_tool.tool_service as mod
from tool_services.discovery_service.nexus_tool.tool_service import DiscoveryToolService
from nexus_sdk.common import MockStorage  # 由 tool_service 内的 path helper 保证可导入
from tool_services.test_utils import ensure_storage_ready


async def main():
    ok, backend = await ensure_storage_ready(MockStorage)
    print(f"[selftest] storage backend = {backend} (minio_ok={ok})")

    # 1) 先真实调用 discovery 拿 results
    discovery_in = "task:test:downloader:discovery_in"
    await MockStorage.save(
        discovery_in,
        {
            "query": "large language model",
            "filters": {
                # 设宽松一点，尽量保证能拿到 OA 结果
                "last_n_days": 365,
                "is_oa": "true",
            },
            "limit": 10,
        },
    )

    discovery = DiscoveryToolService()
    discovery_out_key = await discovery.do_work(discovery_in, {})

    # 2) 把 discovery 的输出 key 直接交给 downloader（内部会从 results 提取 pdf_url 并下载）
    downloader = mod.DownloaderToolService()
    download_out_key = await downloader.do_work(discovery_out_key, {})
    out = await MockStorage.get(download_out_key)

    assert download_out_key.startswith("data:download:")
    assert isinstance(out, dict)
    assert out.get("content_type") == "application/pdf"
    assert isinstance(out.get("size_bytes"), int) and out["size_bytes"] > 0
    assert os.path.exists(out["file_path"]), f"downloaded file not found: {out['file_path']}"
    assert out.get("pdf_url"), "pdf_url should be present"
    assert isinstance(out.get("work"), dict)

    print("[selftest] OK:", download_out_key, "->", out["file_path"])


if __name__ == "__main__":
    asyncio.run(main())

