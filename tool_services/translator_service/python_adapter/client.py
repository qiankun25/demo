"""
HTTP client for Go translator service
"""
import httpx
import os
from typing import List, Dict, Any


class TranslatorClient:
    """
    HTTP client for Go translator service
    """
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("GO_SERVICE_URL", "http://localhost:8002")
        self.client = httpx.AsyncClient(timeout=90.0)
    
    async def translate_text(
        self,
        text: str,
        source_lang: str = "en",
        target_lang: str = "zh",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Translate text via Go service
        """
        url = f"{self.base_url}/api/v1/translate/text"
        payload = {
            "source_lang": source_lang,
            "target_lang": target_lang,
            "content": text,
            "content_type": kwargs.get("content_type", "plain"),
            "domain": kwargs.get("domain", "academic"),
            "style": kwargs.get("style", {}),
            "options": {
                "return_alignment": kwargs.get("return_alignment", False),
                "return_quality": kwargs.get("return_quality", True),
            }
        }
        
        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    
    async def translate_image(
        self,
        image_refs: List[str],
        source_lang: str = "en",
        target_lang: str = "zh",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Translate image via Go service
        Note: This is a simplified version. Full implementation would:
        1. Load images from paths/URLs
        2. Upload to Go service
        3. Get structured results
        """
        # For now, return a placeholder
        # Full implementation would handle file uploads
        return {
            "blocks": [],
            "full_text_translation": "",
            "trace_id": "",
        }
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

