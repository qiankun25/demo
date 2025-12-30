# Nexus 数据获取架构设计决策 (Data Retrieval Architecture Decision)

## 1. 背景与需求
- **场景**: 上层应用服务（Application Layer）需要根据前端的动态需求生成最终报告（如“学术早报”）。
- **角色定位**:
    - **Nexus**: 作为底层能力编排层（Orchestration Layer），负责调度工具并产生中间结果。
    - **上层应用**: 作为业务逻辑中心，负责数据的组装、展示逻辑和最终报告生成。
- **核心问题**: 上层应用如何从 Nexus 高效、灵活地获取任务执行结果？

## 2. 核心决策：混合模式 (Hybrid Pattern) - 统一报告 API + Artifacts API
采用 **"统一报告 API + 制品 API（保留用于高级场景）"** 的混合架构模式。

### 2.1 方案描述
1.  **任务执行**: Nexus 的 Workflow 在执行过程中，将各步骤的输出（Search Result, Translation, Summary 等）作为独立制品（Artifacts）存储在 MinIO 中。
2.  **清单生成**: 任务完成后，Nexus 生成一份 **制品清单 (Manifest)**，包含所有输出文件的元数据（Key/Path, Size, Type）。
3.  **统一报告 API**: 新增 `GET /api/v1/jobs/{trace_id}/report` 端点，返回标准化的聚合报告（适合 80% 的使用场景）。
4.  **制品 API（保留）**: 保留现有的 `GET /api/v1/jobs/{trace_id}/artifacts/{artifact_key}` 端点，用于高级场景（调试、特殊需求等）。

## 3. 架构模式分析

### 3.1 凭证检查模式 (Claim Check Pattern) - 变体
- **传统**: 消息体传 ID，去数据库取大负载。
- **本方案**: Nexus API 返回 MinIO 的 Object Key（凭证），上层应用通过 Nexus 代理获取实际数据。
- **价值**: 避免了在消息总线或 API 响应体中直接传输大数据块。

### 3.2 流透传 (Stream Passthrough)
- **机制**: Nexus API 从 MinIO 读取数据流，直接通过 HTTP Streaming Response 转发给上层应用。
- **价值**:
    - **零内存拷贝**: Nexus 不需要将整个文件加载到内存中解析。
    - **低延迟**: 首字节（TTFB）极快。
    - **隔离性**: 上层应用无需感知 MinIO 的存在（不需要 Access Key/Bucket Name），只与 HTTP API 交互。

### 3.3 读时模式 (Schema on Read)
- **机制**: 数据以原始/半结构化形式存储，读取时根据业务需求决定结构。
- **价值**: 极大提升了灵活性。上层应用修改报告展示逻辑（如增加一个字段），无需修改 Nexus 代码或重新运行任务。

## 4. 方案演进与对比

### 4.1 原方案（清单 + 流透传）的问题
原方案虽然实现了"高内聚低耦合"，但存在以下问题：
- **复杂度转移**：将数据格式转换的复杂度从 Nexus 转移到应用服务
- **认知负担**：应用服务需要了解多个工具服务的数据格式（discovery, parser, translator, indexer 等）
- **维护成本**：工具服务格式变更会直接影响应用服务代码

### 4.2 新方案（混合模式）的优势

| 维度 | 原方案: 清单 + 流透传 | 新方案: 统一报告 API + Artifacts API |
| :--- | :--- | :--- |
| **API 调用次数** | N+1 次（状态 + N个artifacts） | **1次**（统一报告）或 N+1次（高级场景） |
| **数据格式复杂度** | 高（需了解多个工具格式） | **低**（统一标准化格式） |
| **应用服务复杂度** | 高（需要数据转换和组装） | **低**（直接使用标准格式） |
| **灵活性** | 高（可按需获取） | **高**（统一API + 保留artifacts API） |
| **职责边界** | 模糊（应用服务做数据转换） | **清晰**（Nexus负责聚合，应用服务专注业务） |
| **向后兼容** | - | **完全兼容**（保留artifacts API） |

## 5. 解决方案与 API 设计

### 5.1 获取任务状态
`GET /api/v1/jobs/{trace_id}`

语义说明（结合实现 [routes.py](file:///d:/05_python/demo/nexus/app/api/routes.py) 与 [status_service.py](file:///d:/05_python/demo/nexus/app/services/status_service.py)）：
- `artifacts` 是一个"制品索引（manifest of links）"，结构为：`{ artifact_key: download_url }`
  - `artifact_key`：制品的逻辑名称/别名（用来标识"这是哪个制品"）
  - `download_url`：可直接请求的下载地址（即 `GET /api/v1/jobs/{trace_id}/artifacts/{artifact_key}`）
- `artifacts` 的 value 不是 MinIO 的 object key，也不是再次拼接的路径参数；它本身就是可用的 URL（通常是相对路径）。

```json
{
  "trace_id": "uuid",
  "status": "completed",
  "artifacts": {
    "search_results": "/api/v1/jobs/{trace_id}/artifacts/search_results",
    "detailed_manifest": "/api/v1/jobs/{trace_id}/artifacts/detailed_manifest"
  }
}
```

### 5.2 获取标准化报告（推荐 - 80% 场景）
`GET /api/v1/jobs/{trace_id}/report`
- **Response**: `application/json` - 标准化的聚合报告
- **Behavior**: Nexus 自动聚合所有相关 artifacts，转换为统一的业务层数据模型

**优势**：
- **简单易用**：一次 API 调用即可获取完整报告
- **统一格式**：应用服务只需理解一种标准格式，无需了解底层工具服务的数据结构
- **职责清晰**：数据格式转换和聚合逻辑集中在 Nexus，应用服务专注于业务逻辑

**响应格式示例（MORNING_REPORT）**：
```json
{
  "trace_id": "uuid",
  "task_type": "MORNING_REPORT",
  "requested_limit": 5,
  "paper_count": 3,
  "papers": [
    {
      "paper": {
        "title": "Paper Title",
        "authors": ["Author 1", "Author 2"],
        "pdf_url": "http://example.com/paper.pdf",
        "openalex_id": "W123",
        "doi": "10.1234/example",
        "publication_date": "2024-01-01",
        "original_url": "http://example.com/paper.pdf"
      },
      "summary": {
        "llm_summary": "This is a summary of the paper..."
      },
      "index": {
        "collection": "default",
        "vector_count": 10,
        "persist_dir": "/path/to/vectors"
      },
      "keys": {
        "work_key": "task:uuid:work:0",
        "download_key": "data:download:data:work:task:uuid:work:0",
        "parse_key": "data:parse:data:download:data:work:task:uuid:work:0",
        "index_key": "data:index:data:parse:data:download:data:work:task:uuid:work:0"
      }
    }
  ],
  "failure_count": 0,
  "failures": [],
  "keys": {
    "init_key": "job:uuid:init",
    "discovery_key": "data:discovery:job:uuid:input"
  },
  "input": {
    "query": "large language model",
    "filters": {"publication_year": "2024"}
  }
}
```

### 5.3 获取特定制品 (流式) - 高级场景
`GET /api/v1/jobs/{trace_id}/artifacts/{artifact_key}`
- **Response**: `application/json` (Streamed)
- **Behavior**: Nexus reads stream from MinIO -> Writes stream to HTTP Response.
- **用途**：调试、特殊需求、需要访问原始工具服务数据格式的场景

关键点：
- `{artifact_key}` 来自 `GET /api/v1/jobs/{trace_id}` 返回的 `artifacts` 对象的"键名"，例如上面的 `search_results`、`detailed_manifest`。
- 调用时二选一即可：
  1) 直接请求 `artifacts` 给你的 `download_url`
  2) 把 `artifact_key` 填到该接口路径参数里

补充：关于"内部 key（存储 key）"
- Nexus 内部确实存在 MinIO 的 object key（例如 `data:manifest:{trace_id}`、`data:parse:...`），它们是存储层的定位符。
- 正常情况下，上层应用不需要关心这些 key，只需要使用 `download_url`。
- 若你从 `detailed_manifest` 中拿到了某个 `data:*` key，并且它属于当前任务，上述接口也支持直接把该 `data:*` key 作为 `{artifact_key}` 传入进行拉取。

反例（你遇到的 404 根因）：
- 不要把 `download_url`（例如 `/api/v1/jobs/.../artifacts/search_results`）整体 URL-encode 后再塞进 `{artifact_key}`。
- 这会导致实际请求变成：`/artifacts/%2Fapi%2Fv1%2Fjobs%2F...%2Fartifacts%2Fsearch_results`，此时 `{artifact_key}` 的值已经是"整段路径字符串"，当然无法命中实际制品。

## 6. 总结

### 6.1 设计原则
该混合模式设计遵循以下原则：
1. **80/20 原则**：为 80% 的常见场景提供简单统一的 API，为 20% 的高级场景保留灵活的 artifacts API
2. **职责清晰**：Nexus 作为编排层，负责数据格式的统一与标准化，向应用层提供简洁统一的接口
3. **向后兼容**：保留现有的 artifacts API，确保现有客户端不受影响
4. **降低复杂度**：应用服务只需理解统一的业务模型，无需了解底层工具服务的实现细节

### 6.2 使用建议
- **常规使用场景**（推荐）：使用 `GET /api/v1/jobs/{trace_id}/report` 获取标准化报告
- **高级场景**（调试、特殊需求）：使用 `GET /api/v1/jobs/{trace_id}/artifacts/{artifact_key}` 访问原始数据
- **迁移路径**：现有使用 artifacts API 的代码可以继续工作，新代码建议使用统一报告 API

### 6.3 实现要点
- ReportService 负责从多个 artifacts 聚合数据并转换为标准化格式
- 支持 MORNING_REPORT 和 SUMMARY_REPORT 两种任务类型
- 自动处理 manifest 或从 work_keys 重建数据
- 完善的错误处理和日志记录
