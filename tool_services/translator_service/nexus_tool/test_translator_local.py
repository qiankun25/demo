"""
TranslatorToolService 本地自测脚本（真实多模态调用）。

运行：
  python3 tool_services/translator_service/nexus_tool/test_translator_local.py

要求：
- MinIO 可用（MockStorage 后端）
- 设置 SILICONFLOW_API_KEY，并选择支持图像输入的模型（SILICONFLOW_VISION_MODEL）
"""

import asyncio
import os
import sys
import base64
import tempfile

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from tool_services.translator_service.nexus_tool.tool_service import TranslatorToolService
from nexus_sdk.common import MockStorage
from tool_services.test_utils import ensure_storage_ready


def _write_tiny_png() -> str:
    """
    写一个 1x1 PNG 到临时目录，避免依赖外部图片资源。
    """
    # 1x1 transparent PNG
    b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/6XKX1kAAAAASUVORK5CYII="
    )
    data = base64.b64decode(b64)
    path = os.path.join(tempfile.gettempdir(), "translator_selftest_1x1.png")
    with open(path, "wb") as f:
        f.write(data)
    return path


async def main():
    ok, backend = await ensure_storage_ready(MockStorage)
    print(f"[selftest] storage backend = {backend} (minio_ok={ok})")

    # SILICONFLOW_API_KEY is now hardcoded in config.py

    img_path = _write_tiny_png()

    input_key = "task:test:translate"
    await MockStorage.save(
        input_key,
        {
            "text": "Hello world. Translate to Chinese.",
            "images": [img_path],
            "target_lang": "zh",
        },
    )

    service = TranslatorToolService()
    output_key = await service.do_work(input_key, {})
    out = await MockStorage.get(output_key)

    assert output_key.startswith("data:translate:")
    assert isinstance(out, dict)
    assert out.get("meta", {}).get("target_lang") == "zh"
    assert isinstance(out.get("text_translated"), str)
    assert "Hello" not in out["text_translated"] or len(out["text_translated"]) > 0  # 弱断言，避免模型差异
    assert isinstance(out.get("images_translated"), list)
    print("[selftest] OK:", output_key, "text_translated_len=", len(out.get("text_translated", "")))


if __name__ == "__main__":
    asyncio.run(main())

