import re
from typing import Tuple, List


_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[`\"“”‘’]")


def enhance_query(raw_query: str) -> Tuple[str, str]:
    """
    轻量输入增强（不会破坏原有含义，偏保守）：
    - 清洗：去掉引号类符号、压缩空白
    - 增强：如果包含多个 token，构造 `"phrase" OR phrase`，提升短语匹配质量

    返回：(cleaned_query, enhanced_query)
    """
    q = (raw_query or "").strip()
    q = _PUNCT_RE.sub(" ", q)
    q = _WS_RE.sub(" ", q).strip()
    if not q:
        return "", ""

    tokens = _tokens(q)
    if len(tokens) >= 2:
        phrase = " ".join(tokens)
        enhanced = f"\"{phrase}\" OR {phrase}"
        return phrase, enhanced
    return q, q


def _tokens(q: str) -> List[str]:
    # 简单 token：按空格分；同时对连字符做一次归一（deep-learning -> deep learning）
    q = q.replace("-", " ")
    q = _WS_RE.sub(" ", q).strip()
    toks = [t for t in q.split(" ") if t]
    # 去重但保持顺序
    seen = set()
    out = []
    for t in toks:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out

