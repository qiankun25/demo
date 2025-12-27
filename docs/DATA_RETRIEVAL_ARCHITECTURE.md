# Nexus 数据获取架构设计决策 (Data Retrieval Architecture Decision)

## 1. 背景与需求
- **场景**: 上层应用服务（Application Layer）需要根据前端的动态需求生成最终报告（如“学术早报”）。
- **角色定位**:
    - **Nexus**: 作为底层能力编排层（Orchestration Layer），负责调度工具并产生中间结果。
    - **上层应用**: 作为业务逻辑中心，负责数据的组装、展示逻辑和最终报告生成。
- **核心问题**: 上层应用如何从 Nexus 高效、灵活地获取任务执行结果？

## 2. 核心决策：清单 + 制品模式 (Manifest + Artifacts Pattern)
放弃“预聚合报告”方案，采用 **“制品清单 (Manifest) + 按需流式获取 (On-demand Streaming)”** 的架构模式。

### 2.1 方案描述
1.  **任务执行**: Nexus 的 Workflow 在执行过程中，将各步骤的输出（Search Result, Translation, Summary 等）作为独立制品（Artifacts）存储在 MinIO 中。
2.  **清单获取**: 任务完成后，Nexus 不合并文件，而是生成一份 **制品清单 (Manifest)**，包含所有输出文件的元数据（Key/Path, Size, Type）。
3.  **按需组装**: 上层应用根据清单，按需调用 API 获取特定的 JSON 片段（如只获取翻译结果），在内存中完成业务组装。

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

## 4. 方案对比与代价平衡

| 维度 | 方案 A: 预聚合 (Rejected) | 方案 B: 清单 + 流透传 (Selected) |
| :--- | :--- | :--- |
| **耦合度** | 高。Nexus 需知晓上层业务展示逻辑。 | **低**。Nexus 只负责生产数据，不负责展示。 |
| **灵活性** | 差。报告结构变更需修改 Workflow 代码。 | **优**。报告结构由上层应用动态组装。 |
| **性能 (IO)** | 优 (1次请求)。 | 良 (N次请求)。需通过并发调用优化。 |
| **性能 (内存)**| 差。Nexus 需加载所有数据进行聚合。 | **优**。Nexus 仅做流转发，内存占用恒定且极低。 |
| **职责边界** | 模糊。Nexus 承担了部分 View 层职责。 | **清晰**。Nexus = 编排 + 存储网关；上层应用 = 业务逻辑。 |

## 5. 解决方案与 API 设计

### 5.1 获取任务清单
`GET /api/v1/jobs/{trace_id}`
```json
{
  "trace_id": "uuid",
  "status": "completed",
  "artifacts": {
    "literature_search": "/api/v1/jobs/{trace_id}/artifacts/search_output",
    "paper_analysis": "/api/v1/jobs/{trace_id}/artifacts/analysis_output"
  }
}
```

### 5.2 获取特定制品 (流式)
`GET /api/v1/jobs/{trace_id}/artifacts/{artifact_key}`
- **Response**: `application/json` (Streamed)
- **Behavior**: Nexus reads stream from MinIO -> Writes stream to HTTP Response.

## 6. 总结
该设计通过牺牲少量的网络交互次数（N+1次请求），换取了系统架构的**高内聚低耦合**。它正确地将“业务展现逻辑”归还给了上层应用，同时保证了 Nexus 作为基础设施层的稳定性和高性能。
