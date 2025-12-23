import asyncio
import sys
import os

# 将项目根目录添加到路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from tool_services.sdk.base import BaseToolService
from shared.common import MockStorage

# --- 1. 下载服务 ---
class DownloaderService(BaseToolService):
    async def do_work(self, input_key: str, params: dict) -> str:
        # 1. 获取输入
        input_data = await MockStorage.get(input_key)
        print(f"   >>> [Logic] Downloading URLs: {input_data.get('urls')}...")
        
        # 模拟工作
        await asyncio.sleep(1)
        
        # 2. 保存结果
        result = {"file_path": "/minio/bucket/paper_001.pdf", "size": "2MB"}
        output_key = f"data:download:{input_key}"
        await MockStorage.save(output_key, result)
        
        return output_key

# --- 2. 解析服务 ---
class ParserService(BaseToolService):
    async def do_work(self, input_key: str, params: dict) -> str:
        prev_result = await MockStorage.get(input_key)
        print(f"   >>> [Logic] Parsing PDF at: {prev_result['file_path']}...")
        
        await asyncio.sleep(2)
        
        result = {"content": "Abstract: Deep Learning is...", "keywords": ["AI", "ML"]}
        output_key = f"data:parse:{input_key}"
        await MockStorage.save(output_key, result)
        
        return output_key

# --- 3. 索引服务 ---
class IndexerService(BaseToolService):
    async def do_work(self, input_key: str, params: dict) -> str:
        data = await MockStorage.get(input_key)
        print(f"   >>> [Logic] Indexing content into VectorDB...")
        await asyncio.sleep(0.5)
        return "db_record_id_999"
