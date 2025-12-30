"""
Parser service configuration for SiliconFlow summarization.

注意：
- 不要在代码里硬编码密钥。
- 请通过环境变量注入（例如 docker-compose 的 environment / .env 文件）。
"""

import os

SILICONFLOW_API_KEY = (os.getenv("SILICONFLOW_API_KEY") or "").strip()
API_BASE = (os.getenv("SILICONFLOW_API_BASE") or "https://api.siliconflow.cn/v1/chat/completions").strip()
DEFAULT_MODEL = (os.getenv("SILICONFLOW_MODEL") or "deepseek-ai/DeepSeek-V3").strip()

# extractors (ordered by priority; unavailable ones will be skipped)
# Supported: external_cmd, pypdf2, pdfplumber, unstructured, ocr_tesseract
EXTRACTOR_ORDER = [
    "external_cmd",
    "pypdf2",
    "pdfplumber",
    "unstructured",
    "ocr_tesseract",
]

# cache keys (DO NOT use 'data:parse:' prefix to avoid polluting retrieval scans)
CACHE_FULLTEXT_HASH_PREFIX = os.getenv("PARSER_CACHE_FULLTEXT_HASH_PREFIX", "cache:parse:fulltext_hash:")

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
