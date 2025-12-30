from __future__ import annotations

import os
import subprocess
from typing import Optional, List

from .base import ExtractorResult


class ExternalCommandExtractor:
    """
    Extract text by calling an external binary (e.g. a Go-based extractor).
    Contract:
      - stdin: PDF bytes (required)
      - stdout: UTF-8 text (whole doc)
      - exit code 0 => success
    """

    name = "external_cmd"

    def __init__(self, cmd: Optional[str] = None):
        self._cmd = (cmd or os.getenv("PARSER_EXTERNAL_EXTRACTOR_CMD") or "").strip()

    def is_available(self) -> bool:
        return bool(self._cmd)

    def extract_pages(self, *, pdf_bytes: Optional[bytes] = None, path: Optional[str] = None) -> ExtractorResult:
        if not self._cmd:
            raise RuntimeError("external extractor cmd not configured")
        if pdf_bytes is None:
            # keep it strict so the contract is stable; caller can read file bytes first.
            raise RuntimeError("external extractor requires pdf_bytes")

        proc = subprocess.run(
            self._cmd.split(),
            input=pdf_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"external extractor failed rc={proc.returncode} stderr={proc.stderr[:200]!r}")
        text = proc.stdout.decode("utf-8", errors="replace").strip()
        pages: List[str] = [text] if text else []
        return ExtractorResult(pages=pages, extractor_name=self.name)


