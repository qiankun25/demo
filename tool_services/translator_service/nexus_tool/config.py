"""
Translator service configuration for SiliconFlow multimodal translation.

注意：根据用户需求，密钥已硬编码。
"""

import os

SILICONFLOW_API_KEY = "sk-buicstsfegdrvyvakdtqvwyhydmqwrpldpsyiaocnmftqmca"
API_BASE = "https://api.siliconflow.cn/v1/chat/completions"

# 需要使用“支持图像输入”的模型（名称依你在 SiliconFlow 控制台可用模型而定）
DEFAULT_MODEL = "deepseek-ai/DeepSeek-V3"

# 翻译参数
TRANSLATE_MAX_TOKENS = int(os.getenv("TRANSLATE_MAX_TOKENS", "800"))
TRANSLATE_TEMPERATURE = float(os.getenv("TRANSLATE_TEMPERATURE", "0.2"))
TRANSLATE_TOP_P = float(os.getenv("TRANSLATE_TOP_P", "0.9"))

