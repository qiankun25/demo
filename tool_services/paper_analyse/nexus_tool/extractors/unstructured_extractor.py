from __future__ import annotations

from typing import Optional, List

from .base import ExtractorResult


class UnstructuredExtractor:
    """
    Optional extractor using `unstructured`.
    Not installed by default (keep image/pdf deps out of base container).
    """

    name = "unstructured"

    def is_available(self) -> bool:
        try:
            import unstructured  # noqa: F401

            return True
        except Exception:
            return False

    def extract_pages(self, *, pdf_bytes: Optional[bytes] = None, path: Optional[str] = None) -> ExtractorResult:
        if pdf_bytes is not None:
            # unstructured partition_pdf prefers file path; keep simple here.
            raise RuntimeError("unstructured extractor currently requires `path` (not pdf_bytes)")
        if not path:
            raise ValueError("path required")
        try:
            from unstructured.partition.pdf import partition_pdf
        except Exception as e:
            raise RuntimeError("unstructured not installed") from e

        elements = partition_pdf(filename=path)  # type: ignore[arg-type]
        text = "\n".join([getattr(el, "text", "") or "" for el in elements]).strip()
        pages: List[str] = [text] if text else []
        return ExtractorResult(pages=pages, extractor_name=self.name)


