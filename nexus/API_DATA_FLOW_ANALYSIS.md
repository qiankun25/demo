# Nexus API 数据传输机制分析

## 一、总体架构概览

Nexus 采用**事件驱动架构 (Event-Driven Architecture)** 与**Claim-Check 模式**相结合的方式，通过以下核心组件实现与上层应用服务的数据传输：

- **FastAPI REST API**：提供同步的 HTTP 接口
- **RabbitMQ**：实现异步消息传递（命令/事件模式）
- **MinIO**：持久化存储中间结果和最终数据（对象存储）

## 二、数据传输方式

### 2.1 消息传输：RabbitMQ

#### 命令流向（Nexus → 工具服务）
- **Exchange 类型**：Direct Exchange (`cmd_exchange`)
- **路由键格式**：`cmd.{service_name}.start` (例如: `cmd.discovery.start`, `cmd.parser.start`)
- **消息格式**：`MessagePackage` 包含：
  - `header`: `MsgHeader` (trace_id, task_type, sender, timestamp)
  - `payload`: `CommandPayload` (task_id, input_key, params)

#### 事件流向（工具服务 → Nexus）
- **Exchange 类型**：Topic Exchange (`evt_exchange`)
- **路由键格式**：`evt.{service_name}.finished` / `evt.{service_name}.failed`
- **绑定模式**：Nexus 监听 `evt.#` 模式，接收所有工具服务事件
- **消息格式**：`EventPayload` (status, output_key, input_key, error_msg)

### 2.2 数据存储：MinIO（Claim-Check 模式）

**核心思想**：消息中不传输大数据，只传递存储键（Storage Key）

- **输入数据**：工具服务通过 `input_key` 从 MinIO 读取输入
- **输出数据**：工具服务将结果写入 MinIO，返回 `output_key`
- **数据格式**：支持 JSON、Pickle、原始字节流
- **存储键命名规范**：
  - 任务输入：`data:job:{trace_id}:input`
  - 工作项数据：`data:work:{work_key}`
  - 中间结果：`data:{stage}:{input_key}` (例如: `data:parse:data:work:{work_key}`)
  - 清单文件：`data:manifest:{trace_id}`

## 三、从提交任务到获取数据的完整流程

### 阶段 1：任务提交 (POST /api/v1/jobs)

```
上层应用 → FastAPI Routes → JobService → WorkflowOrchestrator
```

1. **API 入口** (`app/api/routes.py`)
   ```python
   POST /api/v1/jobs
   {
     "task_type": "MORNING_REPORT",
     "parameters": {"limit": 5, "query": "LLM Agents"}
   }
   ```

2. **服务层处理** (`app/services/job_service.py`)
   - 调用 `orchestrator.submit_job()`
   - 返回 `JobSubmitResponse` (trace_id, status)

3. **编排器初始化** (`app/engine/orchestrator.py::submit_job()`)
   - 生成唯一 `trace_id` (UUID)
   - 创建 `JobContext` 并持久化到 MinIO (`task:{trace_id}:ctx`)
   - 将任务参数存入 MinIO (`data:job:{trace_id}:input`)
   - 根据工作流定义确定第一个阶段
   - **发布命令到 RabbitMQ** (`mq.publish_command()`)

### 阶段 2：命令分发与并行处理

#### 2.1 Discovery 阶段（单任务）

```
Orchestrator → RabbitMQ (cmd.discovery.start) → Discovery Service
```

- 工具服务从 RabbitMQ 接收命令
- 从 MinIO 读取输入数据 (`data:job:{trace_id}:input`)
- 执行搜索逻辑
- 将结果写入 MinIO，获得 `output_key`
- **发布完成事件** (`evt.discovery.finished`) 到 RabbitMQ

#### 2.2 Fan-out：并行处理多个工作项

```
Discovery Finished → DiscoveryFinishedHandler → 多个 Downloader 任务
```

**关键处理** (`app/engine/handlers.py::DiscoveryFinishedHandler`):

1. **接收事件**：从 RabbitMQ 接收 `evt.discovery.finished` 事件
2. **读取结果**：从 MinIO 读取 `payload.output_key` 处的数据
3. **过滤与分发**：
   ```python
   for i, work in enumerate(results):
       if work_has_pdf_candidate(work):
           work_key = generate_work_key(trace_id, i)  # 生成唯一工作键
           work_input_key = f"data:work:{work_key}"
           # 存储单个工作项数据到 MinIO
           await storage.put(work_input_key, {"work": work})
           # 发布命令，触发并行下载
           await mq.publish_command("cmd.downloader.start", ...)
   ```
4. **更新状态**：将 `work_keys` 列表保存到 `JobContext`

**扇出效果**：一个 Discovery 任务 → N 个并行 Downloader 任务

#### 2.3 后续阶段流转（链式处理）

```
Downloader Finished → Parser Start
Parser Finished → Indexer Start (for MORNING_REPORT)
                  → Overview Start (for SUMMARY_REPORT, after all parsers complete)
```

每个 Handler 负责：
- 接收上一阶段完成事件
- 更新 `completed_work_keys`（原子操作）
- 检查是否所有工作项完成
- 触发下一阶段或完成聚合

### 阶段 3：结果聚合（Fan-in）

#### 3.1 MORNING_REPORT 聚合流程

**完成条件检查** (`app/engine/handlers.py::IndexerFinishedHandler`):

```python
# 原子更新已完成工作项
completed = set(context.completed_work_keys)
completed.add(work_key)
updated_ctx = await state.atomic_update_context(..., {"completed_work_keys": list(completed)})

# 检查是否全部完成
all_keys = set(updated_ctx.work_keys)
failures = set(f.work_key for f in updated_ctx.failures)
completed = set(updated_ctx.completed_work_keys)

is_complete = (completed | failures) >= all_keys

if is_complete:
    # 生成 Manifest（清单文件）
    manifest = []
    for wk in completed:
        manifest.append({
            "work_key": wk,
            "download_key": f"data:download:data:work:{wk}",
            "parse_key": f"data:parse:data:download:data:work:{wk}",
            "index_key": f"data:index:data:parse:data:download:data:work:{wk}"
        })
    
    manifest_key = f"data:manifest:{trace_id}"
    await storage.put(manifest_key, manifest)
    
    # 更新状态为 completed
    await state.atomic_update_context(trace_id, {
        "current_stage": "completed",
        "artifacts": {"detailed_manifest": manifest_key}
    })
```

**关键点**：
- **不合并数据**：只生成包含所有存储键的清单（Manifest）
- **原子操作**：使用 `atomic_update_context` 确保状态一致性
- **支持部分失败**：即使部分工作项失败，也会为成功的项生成清单

#### 3.2 SUMMARY_REPORT 聚合流程

**两阶段聚合** (`app/engine/handlers.py::ParserFinishedHandler`):

1. **Parser 完成阶段**：
   ```python
   # 更新已完成工作项
   completed.add(work_key)
   
   # 检查是否所有 parser 完成
   if (completed | failures) >= all_keys:
       # 聚合所有 parser 结果
       summaries = []
       for wk in completed:
           parse_key = f"data:parse:data:work:{wk}"
           parse_data = await storage.get(parse_key)
           summaries.append({
               "paper": {...},
               "llm_summary": parse_data.get("llm_summary", "")
           })
       
       # 触发 Overview 服务进行最终聚合
       await mq.publish_command("cmd.overview.start", input_key=overview_in_key)
   ```

2. **Overview 完成阶段** (`OverviewFinishedHandler`):
   - 接收 Overview 服务的最终结果
   - 更新状态为 `completed`
   - Overview 的输出存储在 MinIO 中，键记录在 `artifacts` 中

### 阶段 4：数据获取（GET API）

#### 4.1 查询任务状态 (GET /api/v1/jobs/{trace_id})

**流程** (`app/services/status_service.py::get_job_status()`):

```
API Request → StatusService → Orchestrator.get_job_status() → StateManager.get_context()
→ JobContext → JobStatusResponse
```

**响应格式**:
```json
{
  "trace_id": "xxx",
  "task_type": "MORNING_REPORT",
  "status": "completed",
  "total_work_items": 5,
  "completed_count": 4,
  "failed_count": 1,
  "pending_count": 0,
  "artifacts": {
    "detailed_manifest": "/api/v1/jobs/{trace_id}/artifacts/detailed_manifest",
    "search_results": "/api/v1/jobs/{trace_id}/artifacts/search_results"
  },
  "failures": [...]
}
```

**关键字段**：
- `artifacts`: 映射逻辑键（如 "detailed_manifest"）到下载 URL
- `status`: 当前阶段状态（init, discovery, processing, completed）

#### 4.2 获取具体数据 (GET /api/v1/jobs/{trace_id}/artifacts/{artifact_key})

**流式传输机制** (`app/api/routes.py::get_job_artifact()`):

```
API Request → StatusService.get_artifact_stream() → StorageBackend.get_stream()
→ MinIO → StreamingResponse → HTTP Stream → 上层应用
```

**实现细节** (`app/infrastructure/storage.py::MinIOStorage.get_stream()`):

```python
async def get_stream(self, key: str) -> tuple[generator, str]:
    # 1. 从 MinIO 获取对象响应（同步操作在线程池执行）
    response = await asyncio.to_thread(self.client.get_object, bucket, obj_name)
    
    # 2. 返回异步生成器，直接流式传输
    async def _stream_generator():
        try:
            for chunk in response.stream(32 * 1024):  # 32KB 块
                yield chunk
        finally:
            response.close()
    
    return _stream_generator(), content_type
```

**优势**：
- **零内存拷贝**：数据从 MinIO 直接流式传输到客户端
- **按需获取**：上层应用只需获取需要的 artifact，无需下载全部数据
- **安全性**：验证 artifact 属于指定任务（防止未授权访问）

#### 4.3 上层应用的完整使用流程

```python
# 1. 提交任务
response = requests.post("http://nexus:8000/api/v1/jobs", json={
    "task_type": "MORNING_REPORT",
    "parameters": {"limit": 5, "query": "LLM"}
})
trace_id = response.json()["trace_id"]

# 2. 轮询状态（或使用 WebSocket）
while True:
    status_resp = requests.get(f"http://nexus:8000/api/v1/jobs/{trace_id}")
    status = status_resp.json()
    
    if status["status"] == "completed":
        break
    time.sleep(2)

# 3. 获取清单
manifest_url = status["artifacts"]["detailed_manifest"]
manifest_resp = requests.get(f"http://nexus:8000{manifest_url}")
manifest = manifest_resp.json()  # [{"work_key": "...", "parse_key": "...", ...}]

# 4. 按需获取具体数据
for item in manifest:
    parse_key = item["parse_key"]
    # 通过 artifact_key 获取（需要知道映射关系，或直接使用 storage_key）
    # 实际实现中，可能需要额外的 API 来根据 storage_key 获取
    data_resp = requests.get(f"http://nexus:8000/api/v1/jobs/{trace_id}/artifacts/{parse_key}")
    paper_data = data_resp.json()
    # 处理数据...
```

## 四、多个工具服务工作结果的返回机制

### 4.1 Fan-out/Fan-in 模式

**Fan-out（扇出）**：
- **触发点**：`DiscoveryFinishedHandler` 处理 Discovery 完成事件
- **机制**：将单个结果列表拆分为多个工作项，为每个工作项生成 `work_key`
- **并行度**：多个工具服务实例可以同时处理不同的 `work_key`

**Fan-in（扇入）**：
- **触发点**：每个阶段的 Handler 检查完成条件
- **机制**：使用 `completed_work_keys` 集合跟踪完成状态
- **聚合逻辑**：
  - `IndexerFinishedHandler`: 所有 indexer 完成后生成 Manifest
  - `ParserFinishedHandler`: 所有 parser 完成后触发 Overview
  - `OverviewFinishedHandler`: Overview 完成后标记任务完成

### 4.2 状态管理（State Management）

**持久化存储** (`app/infrastructure/storage.py::StateManager`):

- **存储位置**：MinIO (`task:{trace_id}:ctx`)
- **数据结构**：`JobContext` (Pydantic 模型)
  ```python
  class JobContext:
      trace_id: str
      task_type: str
      work_keys: List[str]              # 所有工作项键
      completed_work_keys: List[str]    # 已完成的工作项
      failures: List[FailureRecord]     # 失败记录
      artifacts: Dict[str, str]         # 逻辑键 -> 存储键映射
      current_stage: str                # 当前阶段
  ```

**原子更新** (`atomic_update_context`):

```python
async def atomic_update_context(self, trace_id: str, update_func: Callable):
    lock = await self._get_lock(trace_id)  # 每个 trace_id 一个锁
    async with lock:
        # 1. 读取最新状态
        current = await self.storage.get(ctx_key)
        
        # 2. 应用更新函数
        updates = update_func(current)
        
        # 3. 写入新状态
        await self.storage.put(ctx_key, updated_ctx.model_dump())
```

**关键点**：
- **并发安全**：使用 `asyncio.Lock` 确保同一任务的并发更新不会丢失
- **幂等性**：多次调用相同的事件处理是安全的（基于集合的完成检查）

### 4.3 结果聚合的两种模式

#### 模式 1：清单模式（Manifest Pattern）- MORNING_REPORT

**特点**：不聚合数据，只生成索引清单

```python
manifest = [
    {
        "work_key": "task:xxx:work:0",
        "download_key": "data:download:data:work:task:xxx:work:0",
        "parse_key": "data:parse:data:download:data:work:task:xxx:work:0",
        "index_key": "data:index:data:parse:data:download:data:work:task:xxx:work:0"
    },
    # ... 更多工作项
]
```

**优势**：
- 灵活性：上层应用可以按需选择获取哪些数据
- 可扩展性：清单本身很小，不受数据量影响
- 解耦：Nexus 不关心数据的业务含义，只负责编排

#### 模式 2：聚合模式（Aggregation Pattern）- SUMMARY_REPORT

**特点**：在 Nexus 层进行数据聚合，然后调用聚合服务

```python
# Parser 完成后聚合
summaries = []
for wk in completed_work_keys:
    parse_data = await storage.get(f"data:parse:data:work:{wk}")
    summaries.append({
        "paper": {...},
        "llm_summary": parse_data.get("llm_summary")
    })

# 触发 Overview 服务
await mq.publish_command("cmd.overview.start", input_key=overview_in_key)
```

**优势**：
- 业务逻辑集中：复杂的聚合逻辑由专门的 Overview 服务处理
- 减少网络传输：上层应用只需获取最终结果，无需多次请求

### 4.4 错误处理与部分失败

**失败记录** (`app/engine/handlers.py::FailureHandler`):

```python
class FailureHandler:
    async def handle(self, message: MessagePackage, context: JobContext):
        failure = FailureRecord(
            work_key=work_key,
            stage=message.header.task_type,
            routing_key=message.header.sender,
            input_key=payload.input_key,
            error_msg=payload.error_msg
        )
        
        # 原子更新失败列表
        await state.atomic_update_context(trace_id, lambda ctx: {
            "failures": ctx.failures + [failure]
        })
        
        # 检查是否所有工作项都已处理（成功或失败）
        if (completed | failed_keys) >= all_keys:
            # 即使有失败，也触发完成逻辑（只包含成功的项）
            ...
```

**关键点**：
- **部分失败容忍**：单个工作项失败不影响其他工作项
- **失败信息保留**：`JobStatusResponse.failures` 包含所有失败详情
- **完成条件**：`(completed | failures) >= all_keys` 确保所有工作项都有结果

## 五、数据流图

### 5.1 MORNING_REPORT 完整流程

```
[上层应用]
    | POST /api/v1/jobs
    v
[Nexus API] → JobService → Orchestrator
    |                              |
    |                              | publish_command("cmd.discovery.start")
    |                              v
    |                    [RabbitMQ cmd_exchange]
    |                              |
    |                              v
    |                    [Discovery Service]
    |                              |
    |                    [MinIO: data:job:{trace_id}:input] ← 读取
    |                              |
    |                              | 写入结果
    |                              v
    |                    [MinIO: data:discovery:{trace_id}]
    |                              |
    |                              | publish_event("evt.discovery.finished")
    |                              v
    |                    [RabbitMQ evt_exchange]
    |                              |
    |                    DiscoveryFinishedHandler ← 处理
    |                              |
    |                    Fan-out: 生成 N 个 work_key
    |                              |
    |                    [MinIO: data:work:{work_key}] × N
    |                              |
    |                    publish_command("cmd.downloader.start") × N
    |                              |
    |                    [RabbitMQ cmd_exchange] × N
    |                              |
    +──────────────────────────────┼──────────────────────────────┐
    |                              |                              |
    v                              v                              v
[Downloader 1]              [Downloader 2]              [Downloader N]
    |                              |                              |
    | publish_event("evt.downloader.finished") × N
    v
[RabbitMQ evt_exchange]
    |
    v
DownloaderFinishedHandler → publish_command("cmd.parser.start") × N
    |
    v
[Parser Service] × N → publish_event("evt.parser.finished") × N
    |
    v
ParserFinishedHandler → publish_command("cmd.indexer.start") × N
    |
    v
[Indexer Service] × N → publish_event("evt.indexer.finished") × N
    |
    v
IndexerFinishedHandler
    |
    | 检查: (completed | failures) >= all_keys
    |
    | 生成 Manifest
    v
[MinIO: data:manifest:{trace_id}]
    |
    | 更新状态: current_stage = "completed"
    v
[MinIO: task:{trace_id}:ctx]

[上层应用]
    | GET /api/v1/jobs/{trace_id}
    v
[StatusService] → 返回 JobStatusResponse (包含 artifacts 映射)
    |
    | GET /api/v1/jobs/{trace_id}/artifacts/detailed_manifest
    v
[StatusService.get_artifact_stream()] → MinIO.get_stream()
    |
    v
[StreamingResponse] → 上层应用接收 Manifest JSON
    |
    | 根据 Manifest 中的键，按需获取具体数据
    v
[GET /api/v1/jobs/{trace_id}/artifacts/{storage_key}]
    |
    v
[StreamingResponse] → 上层应用接收实际数据
```

### 5.2 关键组件交互图

```
┌─────────────────┐
│   上层应用服务    │
└────────┬────────┘
         │ HTTP REST API
         │
    ┌────▼─────────────────────────────────┐
    │      Nexus Service (FastAPI)         │
    │  ┌────────────────────────────────┐  │
    │  │  API Routes                    │  │
    │  │  - POST /jobs                  │  │
    │  │  - GET /jobs/{trace_id}        │  │
    │  │  - GET /jobs/{trace_id}/       │  │
    │  │         artifacts/{key}        │  │
    │  └───────────┬────────────────────┘  │
    │              │                        │
    │  ┌───────────▼────────────────────┐  │
    │  │  Services                      │  │
    │  │  - JobService                  │  │
    │  │  - StatusService               │  │
    │  └───────────┬────────────────────┘  │
    │              │                        │
    │  ┌───────────▼────────────────────┐  │
    │  │  WorkflowOrchestrator          │  │
    │  │  - submit_job()                │  │
    │  │  - handle_event()              │  │
    │  └───────┬──────────────┬─────────┘  │
    │          │              │             │
    │  ┌───────▼──────┐  ┌───▼──────────┐ │
    │  │   Handlers   │  │ StateManager │ │
    │  │  - Discovery │  │  - save/     │ │
    │  │  - Downloader│  │    update    │ │
    │  │  - Parser    │  │    context   │ │
    │  │  - Indexer   │  └──────────────┘ │
    │  └──────────────┘                   │
    └───────────┬──────────────────────────┘
                │
    ┌───────────┼───────────────┐
    │           │               │
    ▼           ▼               ▼
┌─────────┐ ┌─────────┐  ┌──────────┐
│RabbitMQ │ │  MinIO  │  │Prometheus│
│         │ │         │  │ Metrics  │
│ cmd/evt │ │ Storage │  │          │
│exchange │ │ Backend │  │          │
└────┬────┘ └────┬────┘  └──────────┘
     │           │
     │           │
     ▼           ▼
┌─────────────────────────────────┐
│      工具服务 (Tool Services)    │
│  - Discovery Service            │
│  - Downloader Service           │
│  - Parser Service               │
│  - Indexer Service              │
│  - Overview Service             │
└─────────────────────────────────┘
```

## 六、总结

### 6.1 核心设计模式

1. **Claim-Check Pattern（凭证检查模式）**
   - 消息中只传递存储键，不传递实际数据
   - 减少消息队列负载，支持大数据传输

2. **Event-Driven Architecture（事件驱动架构）**
   - 工具服务通过异步事件通知 Nexus
   - Nexus 通过事件处理器驱动工作流执行

3. **Fan-out/Fan-in Pattern（扇出/扇入模式）**
   - 支持并行处理多个工作项
   - 通过状态管理实现结果聚合

4. **Manifest + Artifacts Pattern（清单+制品模式）**
   - 生成轻量级的清单文件
   - 按需获取具体数据，减少不必要的传输

5. **Stream Passthrough（流透传）**
   - 数据从 MinIO 直接流式传输到客户端
   - 零内存拷贝，支持大文件传输

### 6.2 数据传输特点

- **异步性**：任务提交后立即返回，通过轮询获取结果
- **可扩展性**：支持多个工具服务实例并行处理
- **容错性**：支持部分失败，失败信息完整记录
- **灵活性**：上层应用可以按需获取部分数据
- **解耦性**：Nexus 不关心业务逻辑，只负责编排和数据传递

### 6.3 完整数据流总结

```
任务提交 → 命令发布 → 工具服务执行 → 事件通知 → 状态更新 → 结果聚合 
→ 清单生成 → 状态查询 → 按需获取 → 数据流传输 → 上层应用处理
```

每个阶段都通过 RabbitMQ（消息）和 MinIO（数据）进行解耦，实现了高度可扩展和容错的分布式系统架构。

