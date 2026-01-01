"""
Translator service configuration for SiliconFlow multimodal translation.

注意：不要在仓库里硬编码密钥；请通过环境变量注入。
"""

import os

# Required in production; service will error if missing when calling SiliconFlow.
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "").strip()
API_BASE = os.getenv("SILICONFLOW_API_BASE", "https://api.siliconflow.cn/v1/chat/completions").strip()

# 需要使用“支持图像输入”的模型（名称依你在 SiliconFlow 控制台可用模型而定）
DEFAULT_MODEL = os.getenv("SILICONFLOW_VISION_MODEL", "").strip() or os.getenv("SILICONFLOW_MODEL", "deepseek-ai/DeepSeek-V3").strip()

# 翻译参数
TRANSLATE_MAX_TOKENS = int(os.getenv("TRANSLATE_MAX_TOKENS", "800"))
TRANSLATE_TEMPERATURE = float(os.getenv("TRANSLATE_TEMPERATURE", "0.2"))
TRANSLATE_TOP_P = float(os.getenv("TRANSLATE_TOP_P", "0.9"))

