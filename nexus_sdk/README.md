# Nexus SDK 使用指南

`nexus-sdk` 是用于开发 Nexus 微服务架构工具服务的官方 SDK。

## 1. 安装

### 选项 A: 直接安装 Wheel 包
```bash
pip install dist/nexus_sdk-0.1.0-py3-none-any.whl
```

### 选项 B: 开发者模式安装 (推荐)
如果您正在开发 SDK 本身：
```bash
pip install -e .
```

## 2. 快速开始

创建一个新的 Python 文件（例如 `my_tool.py`），继承 `BaseToolService` 即可。

```python
import asyncio
from nexus_sdk import BaseToolService, MockStorage

class MyToolService(BaseToolService):
    async def do_work(self, input_key: str, params: dict) -> str:
        # 1. 获取输入
        data = await MockStorage.get(input_key)
        print(f"Processing data: {data}")
        
        # 2. 执行业务逻辑...
        await asyncio.sleep(1)
        
        # 3. 保存结果
        output_key = f"result:{input_key}"
        await MockStorage.save(output_key, {"result": "done"})
        
        # 4. 返回 Key
        return output_key

if __name__ == "__main__":
    # 启动服务，监听 'cmd.mytool.start'
    service = MyToolService(
        service_name="my_tool", 
        cmd_routing_key="cmd.mytool.start"
    )
    
    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        pass
```

## 3. 核心 API

### `BaseToolService(service_name, cmd_routing_key)`
*   `service_name`: 服务唯一标识（如 "downloader"）。
*   `cmd_routing_key`: 监听的 RabbitMQ 路由键（如 "cmd.downloader.start"）。

### `async do_work(input_key, params) -> str`
*   **必须实现**的方法。
*   `input_key`: 指向 Redis/MinIO 的输入数据 Key。
*   `params`: 任务参数字典。
*   **返回值**: 结果数据的 Key。

## 4. 依赖项
SDK 自动处理以下依赖：
*   `aio-pika`: 异步 RabbitMQ 客户端。
*   `pydantic`: 数据验证。
