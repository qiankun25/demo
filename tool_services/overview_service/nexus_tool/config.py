"""
Overview service configuration for SiliconFlow2 (domain survey generation).

注意：根据用户需求，密钥已硬编码。
"""

import os

SILICONFLOW2_API_KEY = "sk-buicstsfegdrvyvakdtqvwyhydmqwrpldpsyiaocnmftqmca"
SILICONFLOW2_API_BASE = "https://api.siliconflow.cn/v1/chat/completions"
SILICONFLOW2_MODEL = "deepseek-ai/DeepSeek-V3"

OVERVIEW_MAX_TOKENS = int(os.getenv("OVERVIEW_MAX_TOKENS", "1200"))
OVERVIEW_TEMPERATURE = float(os.getenv("OVERVIEW_TEMPERATURE", "0.2"))
OVERVIEW_TOP_P = float(os.getenv("OVERVIEW_TOP_P", "0.9"))

# 为避免 prompt 过长，限制摘要拼接字符数
MAX_SUMMARY_CHARS_EACH = int(os.getenv("OVERVIEW_MAX_SUMMARY_CHARS_EACH", "1200"))
MAX_TOTAL_SUMMARY_CHARS = int(os.getenv("OVERVIEW_MAX_TOTAL_SUMMARY_CHARS", "12000"))

