"""
Overview service configuration for SiliconFlow2 (domain survey generation).

注意：
- 不要在代码里硬编码密钥。
- 请通过环境变量注入（例如 docker-compose 的 environment / .env 文件）。
"""

import os

SILICONFLOW2_API_KEY = (os.getenv("SILICONFLOW2_API_KEY") or "").strip()
SILICONFLOW2_API_BASE = (os.getenv("SILICONFLOW2_API_BASE") or "https://api.siliconflow.cn/v1/chat/completions").strip()
SILICONFLOW2_MODEL = (os.getenv("SILICONFLOW2_MODEL") or "deepseek-ai/DeepSeek-V3").strip()

OVERVIEW_MAX_TOKENS = int(os.getenv("OVERVIEW_MAX_TOKENS", "1200"))
OVERVIEW_TEMPERATURE = float(os.getenv("OVERVIEW_TEMPERATURE", "0.2"))
OVERVIEW_TOP_P = float(os.getenv("OVERVIEW_TOP_P", "0.9"))

# 为避免 prompt 过长，限制摘要拼接字符数
MAX_SUMMARY_CHARS_EACH = int(os.getenv("OVERVIEW_MAX_SUMMARY_CHARS_EACH", "1200"))
MAX_TOTAL_SUMMARY_CHARS = int(os.getenv("OVERVIEW_MAX_TOTAL_SUMMARY_CHARS", "12000"))

