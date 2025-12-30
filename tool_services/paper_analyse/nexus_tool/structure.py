from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple


_WS_RE = re.compile(r"\s+")


@dataclass
class Paragraph:
    page: int
    text: str
    is_heading: bool = False


def normalize_text(s: str) -> str:
    s = (s or "").replace("\u00ad", "")  # soft hyphen
    s = _WS_RE.sub(" ", s).strip()
    return s


def split_paragraphs(page_text: str) -> List[str]:
    """
    Split page into paragraphs with conservative heuristics:
    - keep blank-line boundaries
    - also split on long sequences of spaces/newlines in OCR-like text
    """
    raw = (page_text or "").replace("\r\n", "\n").replace("\r", "\n")
    parts = [p.strip() for p in re.split(r"\n\s*\n+", raw) if p.strip()]
    return parts if parts else ([raw.strip()] if raw.strip() else [])


def is_heading(text: str) -> bool:
    t = normalize_text(text)
    if not t:
        return False
    if len(t) > 120:
        return False
    # Common academic headings
    common = {
        "abstract",
        "introduction",
        "related work",
        "background",
        "method",
        "methods",
        "approach",
        "experiments",
        "results",
        "discussion",
        "conclusion",
        "conclusions",
        "references",
        "bibliography",
        "acknowledgements",
        "acknowledgments",
        "appendix",
    }
    if t.lower() in common:
        return True
    # Numbered heading: 1 / 1. / 1.2 / 2.3.4
    if re.match(r"^\d+(\.\d+)*\.?\s+\S+", t):
        return True
    # ALL CAPS short-ish heading
    letters = [c for c in t if c.isalpha()]
    if letters and sum(1 for c in letters if c.isupper()) / max(1, len(letters)) > 0.85 and len(t) <= 80:
        return True
    return False


def iter_paragraphs(pages: List[str]) -> Iterable[Paragraph]:
    for i, page_text in enumerate(pages or [], start=1):
        for para in split_paragraphs(page_text):
            nt = normalize_text(para)
            if not nt:
                continue
            yield Paragraph(page=i, text=nt, is_heading=is_heading(nt))


def drop_references(paragraphs: Iterable[Paragraph], reference_keywords: List[str]) -> List[Paragraph]:
    out: List[Paragraph] = []
    for p in paragraphs:
        lower = p.text.lower()
        if any(k in lower for k in (reference_keywords or [])):
            break
        out.append(p)
    return out


def pack_chunks_by_paragraphs(
    paragraphs: List[Paragraph],
    *,
    chunk_size: int,
    chunk_overlap: int,
    max_chunks: int,
) -> List[Tuple[int, str]]:
    """
    Return list of (page, chunk_text) with paragraph-aware packing.
    Overlap is applied at character level (simple + stable).
    """
    chunks: List[Tuple[int, str]] = []
    buf = ""
    # we keep only one page number in output schema; choose "end page" for better locality.
    buf_end_page: Optional[int] = None

    def flush(final: bool = False) -> None:
        nonlocal buf, buf_end_page
        if not buf.strip():
            buf = ""
            buf_end_page = None
            return
        take = buf[:chunk_size]
        chunks.append((buf_end_page or 1, take))
        if final:
            buf = ""
            buf_end_page = None
            return
        buf = buf[chunk_size - chunk_overlap :] if chunk_overlap > 0 else buf[chunk_size:]
        if not buf.strip():
            buf = ""
            buf_end_page = None

    for p in paragraphs:
        if len(chunks) >= max_chunks:
            break
        if buf_end_page is None:
            buf_end_page = p.page
        else:
            buf_end_page = p.page
        sep = "\n\n" if buf else ""
        candidate = buf + sep + p.text
        if len(candidate) < chunk_size:
            buf = candidate
            continue
        # if heading, prefer chunk boundary before it (keep structure)
        if p.is_heading and buf.strip():
            flush(final=False)
            buf_end_page = p.page
            buf = p.text
        else:
            buf = candidate
        while len(buf) >= chunk_size and len(chunks) < max_chunks:
            flush(final=False)

    if len(chunks) < max_chunks:
        flush(final=True)
    return chunks


