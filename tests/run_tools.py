import asyncio
import sys
import os

# Add project root
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# Add download service for 'app' import
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tool_services", "download_service"))

from tool_services.discovery_service.nexus_tool.tool_service import DiscoveryToolService
from tool_services.download_service.nexus_tool.tool_service import DownloaderToolService
from tool_services.indexing_service.nexus_tool.tool_service import IndexerToolService
from tool_services.overview_service.nexus_tool.tool_service import OverviewToolService

async def main():
    print("[Tools] Starting Tool Services...")
    
    discovery = DiscoveryToolService()
    downloader = DownloaderToolService()
    indexer = IndexerToolService()
    overview = OverviewToolService()
    
    # NOTE: paper_analyse ParserToolService is deprecated in ref-only mode.
    # Run `tool_services/parser_service` (API + MQ worker) separately to handle cmd.parser.start.
    services = [discovery, downloader, indexer, overview]
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
