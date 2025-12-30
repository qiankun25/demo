from __future__ import annotations

from io import BytesIO
from typing import Optional, List

from .base import ExtractorResult


class PdfPlumberExtractor:
    name = "pdfplumber"

    def is_available(self) -> bool:
        try:
            import pdfplumber  # noqa: F401

            return True
        except Exception:
            return False

    def extract_pages(self, *, pdf_bytes: Optional[bytes] = None, path: Optional[str] = None) -> ExtractorResult:
        try:
            import pdfplumber
        except Exception as e:
            raise RuntimeError("pdfplumber not installed") from e

        if pdf_bytes is None and not path:
            raise ValueError("Either pdf_bytes or path must be provided")

        pages: List[str] = []
        if pdf_bytes is not None:
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                for p in pdf.pages:
                    pages.append((p.extract_text() or ""))
        else:
            with pdfplumber.open(path) as pdf:  # type: ignore[arg-type]
                for p in pdf.pages:
                    pages.append((p.extract_text() or ""))
        return ExtractorResult(pages=pages, extractor_name=self.name)


