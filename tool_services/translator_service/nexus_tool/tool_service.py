import os
import sys
import json
import base64
import mimetypes
import tempfile
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


class TranslatorToolService(BaseToolService):
    """
    Translator ToolService：支持文本 + 图片的多模态翻译（SiliconFlow，多模态模型）。

    期望输入 (存储 key 数据结构示例):
    {
        "text": "原文内容",
        "images": ["/tmp/a.png", "https://.../b.jpg"],   # 可选：本地路径或 URL
        "target_lang": "zh"                               # 目标语言（如 zh/en/ja）
    }

    输出：
    - output_key: data:translate:{input_key}
    - 存储内容:
      {
        "text_translated": "...",
        "images_translated": [{"input": "...", "caption": "...", "extracted_text": "...", "translated_text": "..."}],
        "meta": {"target_lang": "...", "image_count": n, "model": "..."}
      }
    """

    def __init__(self):
        super().__init__(service_name="translator", cmd_routing_key="cmd.translator.start")

    async def do_work(self, input_key: str, params: dict) -> str:
        payload = await MockStorage.get(input_key)
        if not payload:
            raise ValueError(f"input_key={input_key} not found in storage")

        text = payload.get("text", "")
        images: List[str] = payload.get("images") or []
        target_lang = payload.get("target_lang", "en")

        if not config.SILICONFLOW_API_KEY:
            raise RuntimeError("SILICONFLOW_API_KEY is required for multimodal translation")

        result = await self._translate_multimodal(text=text, images=images, target_lang=target_lang)

        output = dict(result)
        output.setdefault("meta", {})
        if isinstance(output["meta"], dict):
            output["meta"].update({"target_lang": target_lang, "image_count": len(images), "model": config.DEFAULT_MODEL})

        output_key = f"data:translate:{input_key}"
        await MockStorage.save(output_key, output)
        return output_key

    def _to_image_part(self, image_ref: str) -> Dict[str, Any]:
        """
        将 image_ref（本地路径或 http(s) URL）转换为 OpenAI 兼容的 image_url 内容块。
        - 本地路径：转为 data URL（base64）
        - URL：直接传 url
        """
        ref = (image_ref or "").strip()
        if not ref:
            raise ValueError("empty image ref")

        if ref.startswith("http://") or ref.startswith("https://"):
            return {"type": "image_url", "image_url": {"url": ref}}

        # file path
        if not os.path.exists(ref):
            raise FileNotFoundError(f"image file not found: {ref}")

        mime, _ = mimetypes.guess_type(ref)
        if not mime:
            mime = "application/octet-stream"
        with open(ref, "rb") as f:
            b = f.read()
        b64 = base64.b64encode(b).decode("utf-8")
        return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}

    async def _translate_multimodal(self, text: str, images: List[str], target_lang: str) -> Dict[str, Any]:
        """
        调用 SiliconFlow Chat Completions 做多模态翻译。
        输出尽量为 JSON；若模型未返回 JSON，则回退包装为 text_translated。

        注意：这里不做“伪造兜底”，网络/鉴权失败会直接抛错。
        """
        system_prompt = (
            "You are a professional multilingual translator.\n"
            "You will be given text and optionally images.\n"
            "Task:\n"
            f"1) Translate the given text into {target_lang}.\n"
            f"2) For each image, produce a caption in {target_lang}. If there is readable text, extract it and translate it into {target_lang}.\n"
            "Return STRICT JSON with this schema:\n"
            '{\"text_translated\": string, \"images_translated\": [{\"input\": string, \"caption\": string, \"extracted_text\": string, \"translated_text\": string}]}'
        )

        user_parts: List[Dict[str, Any]] = []
        if text:
            user_parts.append({"type": "text", "text": f"Text to translate:\n{text}"})
        else:
            user_parts.append({"type": "text", "text": "No text provided. Only process images."})

        for img in images or []:
            user_parts.append({"type": "text", "text": f"Image input: {img}"})
            user_parts.append(self._to_image_part(img))

        headers = {
            "Authorization": f"Bearer {config.SILICONFLOW_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config.DEFAULT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_parts},
            ],
            "max_tokens": config.TRANSLATE_MAX_TOKENS,
            "temperature": config.TRANSLATE_TEMPERATURE,
            "top_p": config.TRANSLATE_TOP_P,
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(config.API_BASE, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices") or []
        content = ""
        if choices and isinstance(choices[0], dict):
            msg = choices[0].get("message") or {}
            if isinstance(msg, dict):
                content = (msg.get("content") or "").strip()

        if not content:
            raise RuntimeError("empty model response")

        # 解析 JSON（模型可能包裹 ```json）
        cleaned = content
        if cleaned.startswith("```"):
            cleaned = cleaned.strip().strip("`")
            # 尝试去掉开头的 json 标识
            cleaned = cleaned.replace("json\n", "", 1).strip()

        try:
            out = json.loads(cleaned)
            if not isinstance(out, dict):
                raise ValueError("model output is not a dict")
            out.setdefault("text_translated", "")
            out.setdefault("images_translated", [])
            # 补齐 input 字段（若模型漏了）
            if isinstance(out.get("images_translated"), list):
                fixed = []
                for i, item in enumerate(out["images_translated"]):
                    if not isinstance(item, dict):
                        continue
                    item.setdefault("input", images[i] if i < len(images) else "")
                    item.setdefault("caption", "")
                    item.setdefault("extracted_text", "")
                    item.setdefault("translated_text", "")
                    fixed.append(item)
                out["images_translated"] = fixed
            return out
        except Exception:
            # 不伪造图片翻译结果；只返回原始文本翻译内容（仍是模型输出）
            return {
                "text_translated": content,
                "images_translated": [],
            }


if __name__ == "__main__":
    service = TranslatorToolService()
    try:
        import asyncio

        asyncio.run(service.start())
    except KeyboardInterrupt:
        pass
