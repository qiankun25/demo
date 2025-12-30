from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol


@dataclass
class ExtractorResult:
    pages: List[str]
    extractor_name: str


class TextExtractor(Protocol):
    name: str

    def is_available(self) -> bool: ...

    def extract_pages(self, *, pdf_bytes: Optional[bytes] = None, path: Optional[str] = None) -> ExtractorResult: ...


