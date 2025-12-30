from __future__ import annotations

import shutil
from typing import Optional, List

from .base import ExtractorResult


class TesseractOCRExtractor:
    """
    Optional OCR fallback (requires system packages: poppler + tesseract).
    - python deps: pdf2image, pillow, pytesseract
    - binaries: pdftoppm (poppler-utils), tesseract
    """

    name = "ocr_tesseract"

    def is_available(self) -> bool:
        if not shutil.which("tesseract"):
            return False
        if not shutil.which("pdftoppm"):
            return False
        try:
            import pytesseract  # noqa: F401
            import pdf2image  # noqa: F401

            return True
        except Exception:
            return False

    def extract_pages(self, *, pdf_bytes: Optional[bytes] = None, path: Optional[str] = None) -> ExtractorResult:
        if pdf_bytes is None and not path:
            raise ValueError("Either pdf_bytes or path must be provided")
        try:
            import pytesseract
            from pdf2image import convert_from_bytes, convert_from_path
        except Exception as e:
            raise RuntimeError("OCR deps not installed (pytesseract/pdf2image)") from e

        images = convert_from_bytes(pdf_bytes) if pdf_bytes is not None else convert_from_path(path)  # type: ignore[arg-type]
        pages: List[str] = []
        for img in images:
            pages.append((pytesseract.image_to_string(img) or ""))
        return ExtractorResult(pages=pages, extractor_name=self.name)


