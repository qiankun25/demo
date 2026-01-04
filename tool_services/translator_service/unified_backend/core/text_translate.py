"""
基于 DashScope Qwen 模型的文本翻译实现
"""

from dashscope import Generation
import httpx

from ..config import settings
from tool_services.translator_service import prompt_config


def translate_text(
    text: str,
    source_lang: str = "en",
    target_lang: str = "zh",
) -> str:
    """
    使用 Qwen 大模型进行翻译

    :param text: 原文
    :param source_lang: 源语言
    :param target_lang: 目标语言
    :return: 翻译后的文本
    """

    if not text or not text.strip():
        return ""

    prompt = f"""
你是一个专业的学术翻译助手。
请将以下文本从 {source_lang} 翻译为 {target_lang}。
只返回翻译结果，不要添加解释或额外内容。

文本：
{text}
"""

    # 优先走 DashScope（如果配置了 key）
    if settings.DASHSCOPE_API_KEY:
        try:
            response = Generation.call(
                model="qwen-plus",  # 默认使用 qwen-plus
                api_key=settings.DASHSCOPE_API_KEY,
                prompt=prompt,
                temperature=0.3,
                max_tokens=2000,
                result_format="message",
            )
        except Exception as e:
            raise RuntimeError(f"[QWEN API 调用异常] {e}")

        try:
            if response.status_code != 200:
                raise RuntimeError(response.message)

            content = response.output.choices[0].message.content

            if isinstance(content, list):
                return content[0].get("text", "").strip()

            if isinstance(content, str):
                return content.strip()

            raise RuntimeError(f"未知返回格式: {content}")

        except Exception as e:
            raise RuntimeError(f"[QWEN 响应解析失败] {e}")

    # 否则回退到 SiliconFlow（与旧 translator_service 保持一致）
    if not settings.SILICONFLOW_API_KEY:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY，且未配置 SILICONFLOW_API_KEY，无法翻译文本")

    system_prompt = prompt_config.render_prompt(
        "text_translation", source_lang=source_lang, target_lang=target_lang
    )

    headers = {
        "Authorization": f"Bearer {settings.SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.SILICONFLOW_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "max_tokens": 2000,
        "temperature": 0.2,
        "top_p": 0.9,
    }

    try:
        resp = httpx.post(settings.SILICONFLOW_API_BASE, headers=headers, json=payload, timeout=90.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"[SiliconFlow API 调用异常] {e}")

    choices = data.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        raise RuntimeError("SiliconFlow 返回为空")
    msg = choices[0].get("message") or {}
    content = (msg.get("content") or "").strip() if isinstance(msg, dict) else ""
    if not content:
        raise RuntimeError("SiliconFlow 返回 content 为空")
    return content
