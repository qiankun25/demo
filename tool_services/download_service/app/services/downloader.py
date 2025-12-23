"""PDF downloader service for fetching files from remote URLs."""

import httpx
from typing import Tuple
from urllib.parse import urlparse
import re


class PDFDownloader:
    """Service for downloading PDF files from remote URLs."""

    def __init__(self, timeout: int = 30):
        """
        Initialize the PDF downloader.

        Args:
            timeout: Request timeout in seconds (default: 30)
        """
        self.timeout = timeout

    async def download(self, url: str) -> Tuple[bytes, str]:
        """
        Download a PDF file from the given URL.

        This method:
        - Streams the file content in chunks to handle large files efficiently
        - Extracts filename from Content-Disposition header or URL path
        - Validates that Content-Type contains "pdf" or "application/pdf"

        Args:
            url: The URL to download the PDF from

        Returns:
            Tuple of (file_content: bytes, filename: str)

        Raises:
            ValueError: If the content type is not PDF
            httpx.HTTPError: If the download fails
        """
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()

                # Validate Content-Type
                content_type = response.headers.get("content-type", "").lower()
                if "pdf" not in content_type and "application/pdf" not in content_type:
                    raise ValueError(
                        f"Invalid content type: {content_type}. Expected PDF content."
                    )

                # Extract filename from Content-Disposition header or URL
                filename = self._extract_filename(response.headers, url)

                # Stream file content in chunks
                file_content = b""
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    file_content += chunk

                return file_content, filename

    def _extract_filename(self, headers: httpx.Headers, url: str) -> str:
        """
        Extract filename from Content-Disposition header or URL path.

        Args:
            headers: Response headers
            url: The request URL

        Returns:
            Extracted filename
        """
        # Try to extract from Content-Disposition header
        content_disposition = headers.get("content-disposition", "")
        if content_disposition:
            # Look for filename= or filename*= patterns
            filename_match = re.search(
                r'filename\*?=(["\']?)(.+?)\1(?:;|$)',
                content_disposition,
                re.IGNORECASE
            )
            if filename_match:
                filename = filename_match.group(2)
                # Remove any UTF-8'' prefix from RFC 5987 encoding
                filename = re.sub(r"^UTF-8''", "", filename, flags=re.IGNORECASE)
                return filename

        # Fallback to extracting from URL path
        parsed_url = urlparse(url)
        path = parsed_url.path
        filename = path.split("/")[-1]

        # If no filename in path or it doesn't end with .pdf, generate a default
        if not filename or not filename.lower().endswith(".pdf"):
            filename = "document.pdf"

        return filename
