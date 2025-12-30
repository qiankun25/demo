from __future__ import annotations

from io import BytesIO
from typing import Optional, List

from .base import ExtractorResult


class PyPDF2Extractor:
    name = "pypdf2"

    def is_available(self) -> bool:
        try:
            import PyPDF2  # noqa: F401

            return True
        except Exception:
            return False

    def extract_pages(self, *, pdf_bytes: Optional[bytes] = None, path: Optional[str] = None) -> ExtractorResult:
        try:
            from PyPDF2 import PdfReader
        except Exception as e:
            raise RuntimeError("PyPDF2 not installed") from e

        if pdf_bytes is None and not path:
            raise ValueError("Either pdf_bytes or path must be provided")

        reader = PdfReader(BytesIO(pdf_bytes)) if pdf_bytes is not None else PdfReader(path)  # type: ignore[arg-type]
        pages: List[str] = []
        for page in reader.pages:
            pages.append((page.extract_text() or ""))
        return ExtractorResult(pages=pages, extractor_name=self.name)


