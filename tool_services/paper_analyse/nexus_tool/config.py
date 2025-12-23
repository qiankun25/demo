"""
Parser service configuration for SiliconFlow summarization.

注意：根据用户需求，密钥已硬编码。
"""

import os

SILICONFLOW_API_KEY = "sk-buicstsfegdrvyvakdtqvwyhydmqwrpldpsyiaocnmftqmca"
API_BASE = "https://api.siliconflow.cn/v1/chat/completions"
DEFAULT_MODEL = "deepseek-ai/DeepSeek-V3"

# chunk & summary params
CHUNK_SIZE = int(os.getenv("PARSER_CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("PARSER_CHUNK_OVERLAP", "200"))
MAX_TEXT_CHARS = int(os.getenv("PARSER_MAX_TEXT_CHARS", "200000"))  # 上限：避免 OOM
MAX_CHUNKS = int(os.getenv("PARSER_MAX_CHUNKS", "300"))

SUMMARY_MAX_TOKENS = int(os.getenv("PARSER_SUMMARY_MAX_TOKENS", "256"))
SUMMARY_TEMPERATURE = float(os.getenv("PARSER_SUMMARY_TEMPERATURE", "0.3"))
SUMMARY_TOP_P = float(os.getenv("PARSER_SUMMARY_TOP_P", "0.9"))

# heuristics
REFERENCE_KEYWORDS = ["references", "bibliography", "acknowledgement"]
