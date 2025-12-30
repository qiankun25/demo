from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .base import ExtractorResult, TextExtractor


@dataclass
class ExtractAttempt:
    name: str
    ok: bool
    error: Optional[str] = None


class FallbackExtractorChain:
    """
    Try extractors by priority; return first successful result.
    """

    def __init__(self, extractors: Sequence[TextExtractor]):
        self.extractors: List[TextExtractor] = list(extractors)

    def extract_pages(
        self, *, pdf_bytes: Optional[bytes] = None, path: Optional[str] = None
    ) -> Tuple[ExtractorResult, List[ExtractAttempt]]:
        attempts: List[ExtractAttempt] = []
        last_err: Optional[BaseException] = None

        for ex in self.extractors:
            name = getattr(ex, "name", ex.__class__.__name__)
            if not ex.is_available():
                attempts.append(ExtractAttempt(name=name, ok=False, error="not_available"))
                continue
            try:
                res = ex.extract_pages(pdf_bytes=pdf_bytes, path=path)
                if not isinstance(res.pages, list):
                    raise RuntimeError("extractor returned non-list pages")
                attempts.append(ExtractAttempt(name=name, ok=True))
                return res, attempts
            except Exception as e:
                last_err = e
                attempts.append(ExtractAttempt(name=name, ok=False, error=str(e)[:300]))
                continue

        raise RuntimeError(f"all extractors failed; last_err={last_err}; attempts={attempts}")


