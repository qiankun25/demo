import asyncio
import sys
import os

# 保证项目根目录在路径中
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from nexus_service.core import NexusService
from tool_services.discovery_service.nexus_tool.tool_service import DiscoveryToolService
from tool_services.download_service.nexus_tool.tool_service import DownloaderToolService
from tool_services.indexing_service.nexus_tool.tool_service import IndexerToolService
from tool_services.retrieval_service.nexus_tool.tool_service import RetrievalToolService
from tool_services.translator_service.nexus_tool.tool_service import TranslatorToolService


async def main():
    print("--- 🚀 Starting All Services (Nexus + Tools) ---")

    nexus = NexusService()
    discovery = DiscoveryToolService()
    downloader = DownloaderToolService()
    indexer = IndexerToolService()
    retrieval = RetrievalToolService()
    translator = TranslatorToolService()

    tasks = [
        asyncio.create_task(nexus.start()),
        asyncio.create_task(discovery.start()),
        asyncio.create_task(downloader.start()),
        asyncio.create_task(indexer.start()),
        asyncio.create_task(retrieval.start()),
        asyncio.create_task(translator.start()),
    ]

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print("\n--- 🛑 Stopping Services ---")
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        print("--- Services Stopped Gracefully ---")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
