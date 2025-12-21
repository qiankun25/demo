# 微服务架构集成规范与开发指南

本文档旨在规范 **Nexus (编排中枢)** 与 **Tool Services (工具服务)** 之间的通信协议、数据存储标准及开发流程，确保多人协作时的接口一致性与系统稳定性。

---

## 1. 核心设计理念

### 1.1 传信不传物 (Claim Check Pattern)
*   **MQ (RabbitMQ)**：仅传输轻量级的控制指令和“数据引用 Key”，严禁传输文件二进制流或大段 JSON 文本。
*   **Storage (Redis/MinIO)**：负责存储实际的业务数据（如 PDF 文件、解析后的 Markdown、向量数据等）。

### 1.2 职责分离
*   **Nexus**：只管“流程”，不碰“业务数据”。它负责把 A 的输出 Key 传给 B。
*   **Tools**：只管“执行”，无状态设计。从 Storage 读 Key，处理完写 Storage，返回新 Key。

---

## 2. 通信协议规范

所有服务必须遵循 `shared/common.py` 中定义的 Pydantic 模型。

### 2.1 消息头 (MsgHeader)
所有指令和事件必须包含此头部，用于全链路追踪。

| 字段 | 类型 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `trace_id` | `UUID` | 全局唯一任务 ID，贯穿整个 DAG 流程 | `550e8400-e29b-41d4-a716-446655440000` |
| `task_type` | `String` | 业务场景标识，决定 Nexus 走哪个流程 | `MORNING_REPORT` |
| `sender` | `String` | 发送方服务名 | `nexus`, `downloader`, `parser` |
| `timestamp` | `Float` | 发送时间戳 (Unix Time) | `1703145600.0` |

### 2.2 指令包 (Command Payload)
**方向**：Nexus -> Tool Service
**交换机**：`nexus.cmd.exchange` (Direct)

```json
{
  "task_id": "UUID",       // 当前步骤的唯一ID
  "input_key": "String",   // 数据输入源的 Key (指向 Storage)
  "params": {              // 动态参数 (可选)
    "retry_count": 0,
    "priority": "high"
  }
}
```

### 2.3 事件包 (Event Payload)
**方向**：Tool Service -> Nexus
**交换机**：`nexus.evt.exchange` (Topic)

**成功响应**：
```json
{
  "status": "SUCCESS",
  "output_key": "String",  // 结果数据的 Key (指向 Storage)
  "error_msg": null
}
```

**失败响应**：
```json
{
  "status": "FAIL",
  "output_key": null,
  "error_msg": "TimeoutError: Failed to connect source"
}
```

---

## 3. 数据存储与 Key 命名规范

为了防止 Key 冲突并方便 Debug，所有存入 Shared Storage 的数据必须遵循以下命名格式。

### 3.1 Key 格式
格式：`{数据类型}:{来源服务}:{TraceID}:{后缀}`

| 阶段 | 生成者 | Key 示例 | 存储内容示例 (JSON) |
| :--- | :--- | :--- | :--- |
| **任务初始化** | API/Nexus | `task:{trace_id}:init` | `{"urls": ["http://arxiv.org/..."], "email": "user@example.com"}` |
| **下载完成** | Downloader | `data:download:{trace_id}` | `{"file_path": "/minio/papers/001.pdf", "size_bytes": 102400}` |
| **解析完成** | Parser | `data:parse:{trace_id}` | `{"content_md": "# Title...", "images": ["/minio/img/1.png"]}` |
| **索引完成** | Indexer | `data:index:{trace_id}` | `{"vector_id": "8899", "collection": "papers"}` |

### 3.2 存储内容建议
*   **小数据 (<10KB)**：直接存 JSON 字符串。
*   **大数据/文件**：
    1.  将文件上传至 MinIO/S3。
    2.  Storage 中仅存储文件路径元数据（如 `{"bucket": "A", "path": "/b/c.pdf"}`）。

---

## 4. 开发指南 (How-To)

### 4.1 开发一个新的工具服务 (如 "Translator")

1.  **新建文件**：在 `tool_services/impl/` 下创建 `translator.py`。
2.  **继承基类**：继承 `BaseToolService`。
3.  **实现逻辑**：
    ```python
    class TranslatorService(BaseToolService):
        async def do_work(self, input_key: str, params: dict) -> str:
            # 1. 读: 从 Storage 获取上一步(Parser)的结果
            source_data = await MockStorage.get(input_key)
            
            # 2. 算: 执行翻译逻辑
            translated_text = translate(source_data['content_md'])
            
            # 3. 写: 存入 Storage
            output_key = f"data:trans:{params['trace_id']}" # 建议从 header 获取 trace_id 但此处演示简化
            # 注: 实际开发中 input_key 通常包含 trace_id，可复用
            
            await MockStorage.save(output_key, {"text": translated_text})
            
            # 4. 返: 返回 Key
            return output_key
    ```
4.  **注册运行**：在 `run_demo.py` 或启动脚本中实例化并启动它。

### 4.2 修改编排流程 (Nexus)

1.  打开 `nexus_service/core.py`。
2.  定位到 `_on_event` 方法。
3.  在 `DAG 逻辑` 区域添加新的 `elif` 分支：
    ```python
    elif routing_key == "evt.translator.finished":
        # 翻译完了，发送给通知服务
        await self._send_command(trace_id, "cmd.notifier.send", pkg.payload['output_key'])
    ```

---

## 5. 错误处理与重试

*   **业务异常**：在 `do_work` 中直接抛出 Python Exception。SDK 会自动捕获并发送 `FAIL` 事件。
*   **服务崩溃**：如果服务进程直接挂掉（OOM），RabbitMQ 会因未收到 ACK 而将消息重新投递（需配置死信队列 DLQ 处理毒丸消息）。
*   **超时控制**：Nexus 侧未实现超时重发，建议在生产环境引入 Redis 定时器检查长时间未完成的任务。
