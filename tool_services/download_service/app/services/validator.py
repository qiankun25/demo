"""URL validation service for checking URL reachability before downloads."""

import httpx
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class URLValidator:
    """Service for validating URL reachability before attempting downloads."""
    
    def __init__(self, timeout: int = 10):
        """Initialize URL validator.
        
        Args:
            timeout: Request timeout in seconds (default: 10)
        """
        self.timeout = timeout
        logger.info(f"URLValidator initialized with timeout: {timeout}s")
    
    async def is_reachable(self, url: str) -> Tuple[bool, str]:
        """Validate URL reachability using HEAD request with GET fallback.
        
        Attempts to validate the URL by first sending a HEAD request to minimize
        bandwidth usage. If the HEAD request fails, falls back to a GET request.
        
        Args:
            url: The URL to validate
        
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
                - is_valid: True if URL is reachable (2xx status), False otherwise
                - error_message: Empty string if valid, error description if invalid
        
        Examples:
            >>> validator = URLValidator()
            >>> is_valid, error = await validator.is_reachable("https://example.com/file.pdf")
            >>> if is_valid:
            ...     print("URL is reachable")
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Try HEAD request first
            try:
                logger.debug(f"Sending HEAD request to: {url}")
                response = await client.head(url, follow_redirects=True)
                
                if 200 <= response.status_code < 300:
                    logger.info(f"URL is reachable (HEAD): {url} - Status: {response.status_code}")
                    return (True, "")
                else:
                    error_msg = f"HTTP {response.status_code}"
                    logger.warning(f"URL returned non-2xx status (HEAD): {url} - {error_msg}")
                    return (False, error_msg)
                    
            except httpx.HTTPStatusError as e:
                # HEAD request failed with HTTP error, try GET fallback
                logger.debug(f"HEAD request failed for {url}, trying GET fallback: {e}")
                
            except httpx.RequestError as e:
                # Connection error on HEAD, try GET fallback
                logger.debug(f"HEAD request error for {url}, trying GET fallback: {e}")
            
            # Fallback to GET request
            try:
                logger.debug(f"Sending GET request to: {url}")
                response = await client.get(url, follow_redirects=True)
                
                if 200 <= response.status_code < 300:
                    logger.info(f"URL is reachable (GET): {url} - Status: {response.status_code}")
                    return (True, "")
                elif response.status_code == 404:
                    error_msg = "HTTP 404 - Not Found"
                    logger.warning(f"URL not found: {url}")
                    return (False, error_msg)
                elif 500 <= response.status_code < 600:
                    error_msg = f"HTTP {response.status_code} - Server Error"
                    logger.warning(f"Server error for URL: {url} - {error_msg}")
                    return (False, error_msg)
                else:
                    error_msg = f"HTTP {response.status_code}"
                    logger.warning(f"URL returned non-2xx status (GET): {url} - {error_msg}")
                    return (False, error_msg)
                    
            except httpx.TimeoutException as e:
                error_msg = f"Timeout after {self.timeout}s"
                logger.error(f"Timeout validating URL: {url} - {error_msg}")
                return (False, error_msg)
                
            except httpx.ConnectError as e:
                error_msg = f"Connection error: {str(e)}"
                logger.error(f"Connection error for URL: {url} - {error_msg}")
                return (False, error_msg)
                
            except httpx.RequestError as e:
                error_msg = f"Request error: {str(e)}"
                logger.error(f"Request error for URL: {url} - {error_msg}")
                return (False, error_msg)
                
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                logger.error(f"Unexpected error validating URL: {url} - {error_msg}")
                return (False, error_msg)
