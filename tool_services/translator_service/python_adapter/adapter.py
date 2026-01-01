"""
Python adapter for Translator Service
Provides BaseToolService compatibility layer that calls Go service
"""
import os
import sys
import json
import asyncio
from typing import Dict, Any, Tuple

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from nexus_sdk.base import BaseToolService
from nexus_sdk.common import MockStorage
from .client import TranslatorClient


class TranslatorAdapter(BaseToolService):
    """
    Translator Adapter: BaseToolService implementation that calls Go translator service
    """
    
    def __init__(self):
        super().__init__(service_name="translator", cmd_routing_key="cmd.translator.start")
        self.client = TranslatorClient()
    
    async def do_work(self, input_ref: dict, params: dict) -> Tuple[dict, dict]:
        """
        Process translation request from Nexus SDK
        """
        # 1. Get input from MockStorage
        input_key = params.get("input_key", "")
        if not input_key:
            raise ValueError("input_key is required")
        
        payload = await MockStorage.get(input_key)
        if not payload:
            raise ValueError(f"Input not found: {input_key}")
        
        # 2. Call Go service
        if payload.get("images"):
            # Image translation
            result = await self.client.translate_image(
                image_refs=payload.get("images", []),
                source_lang=payload.get("source_lang", "en"),
                target_lang=payload.get("target_lang", "zh"),
            )
        else:
            # Text translation
            result = await self.client.translate_text(
                text=payload.get("text", ""),
                source_lang=payload.get("source_lang", "en"),
                target_lang=payload.get("target_lang", "zh"),
            )
        
        # 3. Write to MockStorage (compatible format)
        output_key = f"data:translate:{input_key}"
        output_data = {
            "text_translated": result.get("translation", ""),
            "images_translated": result.get("blocks", []),
            "meta": {
                "target_lang": payload.get("target_lang", "zh"),
                "image_count": len(payload.get("images", [])),
                "model": "go-service",
            }
        }
        await MockStorage.save(output_key, output_data)
        
        # 4. Return result
        return (
            {
                "service": "translator",
                "type": "translation",
                "id": result.get("trace_id", ""),
                "version": "v1",
            },
            {
                "image_count": len(payload.get("images", [])),
                "target_lang": payload.get("target_lang", "zh"),
            },
        )


if __name__ == "__main__":
    service = TranslatorAdapter()
    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        pass

