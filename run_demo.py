import asyncio
import sys
import os

# 添加项目根目录
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from nexus_service.core import NexusService
from tool_services.discovery_service.nexus_tool.tool_service import DiscoveryToolService
from tool_services.download_service.nexus_tool.tool_service import DownloaderToolService
from tool_services.paper_analyse.nexus_tool.tool_service import ParserToolService
from tool_services.indexing_service.nexus_tool.tool_service import IndexerToolService
from tool_services.overview_service.nexus_tool.tool_service import OverviewToolService
from shared.common import MockStorage

async def main():
    print("--- 🚀 Starting Event-Driven Microservices Demo ---")
    
    # 1. 实例化服务
    nexus = NexusService()
    
    discovery = DiscoveryToolService()
    downloader = DownloaderToolService()
    parser = ParserToolService()
    indexer = IndexerToolService()
    overview = OverviewToolService()
    
    try:
        # 2. 在后台启动服务
        # 我们使用 asyncio.create_task 并发运行它们
        t_nexus = asyncio.create_task(nexus.start())
        t_discovery = asyncio.create_task(discovery.start())
        t_dl = asyncio.create_task(downloader.start())
        t_parser = asyncio.create_task(parser.start())
        t_idx = asyncio.create_task(indexer.start())
        t_overview = asyncio.create_task(overview.start())
        
        # 给它们一点时间连接
        await asyncio.sleep(2)
        
        # 3. 提交任务
        print("\n--- 📥 Submitting Job ---")
        task_type = os.getenv("DEMO_TASK_TYPE", "MORNING_REPORT").strip().upper()
        if task_type == "SUMMARY_REPORT":
            # SummaryReport 输入：先把 pdf_url 列表存入 MinIO，再把 key 传给 orchestrator
            seed_key = "seed:summary_report:demo"
            await MockStorage.save(
                seed_key,
                {
                    "domain": "Graph Neural Networks",
                    "style": "academic",
                    "papers": [
                        {"pdf_url": "https://arxiv.org/pdf/2010.03409", "title": "Graph Neural Networks: A Review of Methods and Applications"},
                        {"pdf_url": "https://arxiv.org/pdf/1810.00826.pdf", "title": "Graph Attention Networks"},
                    ],
                },
            )
            await nexus.submit_job("SUMMARY_REPORT", {"summary_report_key": seed_key})
        else:
            # MORNING_REPORT 输入：query + filters（filters 设宽松些，避免 0 结果）
            job_data = {
                "query": "GNN",
                "filters": {
                    "last_n_days": 365,
                    "is_oa": "true",
                },
                "limit": 5,
            }
            await nexus.submit_job("MORNING_REPORT", job_data)
        
        # 4. 等待处理 (模拟)
        # 在真实应用中，我们可能会等待特定信号或永远运行。
        # 这里我们等待足够的时间让链路完成（多篇论文解析 + 领域综述）
        print("\n--- ⏳ Waiting for Workflow Completion ---")
        await asyncio.sleep(300)
        
    except Exception as e:
        print(f"\n[!!!] Error during execution: {e}")
        print("Check if RabbitMQ is running locally on port 5672.")
    
    finally:
        print("\n--- 🛑 Stopping Demo ---")
        # 优雅关闭：取消所有后台任务
        tasks = [t_nexus, t_discovery, t_dl, t_parser, t_idx, t_overview]
        for task in tasks:
            task.cancel()
        
        # 等待任务取消完成，并忽略期间的 CancelledError
        await asyncio.gather(*tasks, return_exceptions=True)
        print("--- Services Stopped Gracefully ---")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
