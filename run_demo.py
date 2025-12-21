import asyncio
import sys
import os

# 添加项目根目录
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from nexus_service.core import NexusService
from tool_services.impl.tools import DownloaderService, ParserService, IndexerService

async def main():
    print("--- 🚀 Starting Event-Driven Microservices Demo ---")
    
    # 1. 实例化服务
    nexus = NexusService()
    
    downloader = DownloaderService("downloader", "cmd.downloader.start")
    parser = ParserService("parser", "cmd.parser.start")
    indexer = IndexerService("indexer", "cmd.indexer.start")
    
    try:
        # 2. 在后台启动服务
        # 我们使用 asyncio.create_task 并发运行它们
        t_nexus = asyncio.create_task(nexus.start())
        t_dl = asyncio.create_task(downloader.start())
        t_parser = asyncio.create_task(parser.start())
        t_idx = asyncio.create_task(indexer.start())
        
        # 给它们一点时间连接
        await asyncio.sleep(2)
        
        # 3. 提交任务
        print("\n--- 📥 Submitting Job ---")
        job_data = {"urls": ["http://arxiv.org/abs/2301.0001", "http://arxiv.org/abs/2301.0002"]}
        await nexus.submit_job("MORNING_REPORT", job_data)
        
        # 4. 等待处理 (模拟)
        # 在真实应用中，我们可能会等待特定信号或永远运行。
        # 这里我们等待足够的时间让链路完成 (1s + 2s + 0.5s + 开销 ~ 5s)
        print("\n--- ⏳ Waiting for Workflow Completion ---")
        await asyncio.sleep(10)
        
    except Exception as e:
        print(f"\n[!!!] Error during execution: {e}")
        print("Check if RabbitMQ is running locally on port 5672.")
    
    finally:
        print("\n--- 🛑 Stopping Demo ---")
        # 优雅关闭：取消所有后台任务
        tasks = [t_nexus, t_dl, t_parser, t_idx]
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
