import asyncio
import sys
import os

# Add project root
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# Add download service for 'app' import
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tool_services", "download_service"))

from tool_services.discovery_service.nexus_tool.tool_service import DiscoveryToolService
from tool_services.download_service.nexus_tool.tool_service import DownloaderToolService
from tool_services.paper_analyse.nexus_tool.tool_service import ParserToolService
from tool_services.indexing_service.nexus_tool.tool_service import IndexerToolService
from tool_services.overview_service.nexus_tool.tool_service import OverviewToolService

async def main():
    print("[Tools] Starting Tool Services...")
    
    discovery = DiscoveryToolService()
    downloader = DownloaderToolService()
    parser = ParserToolService()
    indexer = IndexerToolService()
    overview = OverviewToolService()
    
    services = [discovery, downloader, parser, indexer, overview]
    tasks = []
    
    for svc in services:
        tasks.append(asyncio.create_task(svc.start()))
        
    print("[Tools] All services started and listening on RabbitMQ.")
    
    try:
        # Keep running until cancelled
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        print("[Tools] Stopping services...")
    finally:
        print("[Tools] Services stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
