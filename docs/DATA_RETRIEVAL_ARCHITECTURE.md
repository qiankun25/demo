# Nexus 数据获取架构设计决策（以当前仓库代码为准）

> 本文档说明“应用层如何从 Nexus 获取任务结果”的模式与接口，并**以当前仓库代码实现为准**。  
> 推荐对照以下文件阅读：
> - Nexus 路由：`nexus/app/api/routes.py`
> - Status / Artifacts：`nexus/app/services/status_service.py`
> - Report（标准化聚合）：`nexus/app/services/report_service.py`
> - 状态存储（Orchestration DB）：`nexus/app/infrastructure/state_db.py`、`nexus/app/infrastructure/orchestration_db.py`
> - 消息/合约（ref-only）：`nexus/app/models/messages.py`、`tool_services/libs/contracts/nexus_contracts/models.py`

---

## 1) 背景与需求
- **场景**：上层应用（Application Layer）提交任务（如 `MORNING_REPORT` / `SUMMARY_REPORT`），等待编排完成后需要获取结果。
- **核心诉求**：
  - **80% 场景**：一次调用拿到“统一、稳定”的结果结构（标准化报告）
  - **20% 场景**：可以按需拿到某个 stage 的“原始产物”（用于调试、验收、特殊展示）

---

## 2) 核心决策：Hybrid = Report API（主入口） + Artifacts API（调试入口）

### 2.1 ref-only + artifacts_refs：用“隐式 manifest”替代“物理 manifest 文件”
当前仓库的实现并没有生成一份独立的 Manifest 文件对象；而是把每个 stage 的产物输出以 **ResultRef** 的形式写入：
- `JobContext.artifacts_refs`（逻辑索引）
- Orchestration DB 的 `artifacts_index` 表（持久化索引）

因此：**`artifacts_refs` 就是“manifest-of-refs（隐式清单）”**。

### 2.2 Report API：统一结构（推荐）
- `GET /api/v1/jobs/{trace_id}/report`
  - **返回**：标准化报告（`report_models.py` 中的 Pydantic 模型）
  - **约束**：任务必须处于 `completed`；否则返回 400（`ReportService.build_report()`）
  - **支持任务类型**：当前实现仅支持 `MORNING_REPORT` / `SUMMARY_REPORT`

### 2.3 Artifacts API：原始制品（高级/调试）
- `GET /api/v1/jobs/{trace_id}/artifacts/{artifact_key}`
  - **返回**：`application/json`
  - **数据来源（非常重要）**：当前实现是 **Query API Proxy**  
    即：根据 `artifacts_refs[artifact_key]` 的 `service/type/id` 去调用对应微服务 Query API，再把 JSON 返回（见 `StatusService.get_artifact_stream()`）
  - **用途**：调试/验收/特殊需求场景；上层不必理解 MinIO path 或各服务 DB

---

## 3) API 设计（以实际实现为准）

### 3.1 获取任务状态：`GET /api/v1/jobs/{trace_id}`
见 `StatusService.get_job_status()`：
- `status`：来自 `JobContext.current_stage`
- `artifacts`：由 `artifacts_refs` 生成的 `{ artifact_key: download_url }` 映射
- `pending_count`：`total - completed - failed`（且不为负）

**示例（注意：artifacts 的 value 是 URL，不是存储 key）**：

```json
{
  "trace_id": "uuid",
  "task_type": "MORNING_REPORT",
  "status": "completed",
  "total_work_items": 5,
  "completed_count": 5,
  "failed_count": 0,
  "pending_count": 0,
  "artifacts": {
    "discovery": "/api/v1/jobs/uuid/artifacts/discovery",
    "search_results": "/api/v1/jobs/uuid/artifacts/search_results",
    "downloader:task:uuid:work:0": "/api/v1/jobs/uuid/artifacts/downloader:task:uuid:work:0",
    "parser:task:uuid:work:0": "/api/v1/jobs/uuid/artifacts/parser:task:uuid:work:0",
    "indexer:task:uuid:work:0": "/api/v1/jobs/uuid/artifacts/indexer:task:uuid:work:0"
  },
  "failures": []
}
```

> artifact_key 的集合会随任务类型、work_key 数量、以及是否存在别名归档而变化；应用层应以 API 返回为准。

### 3.2 获取标准化报告：`GET /api/v1/jobs/{trace_id}/report`

#### MORNING_REPORT（当前实现的真实语义）
见 `ReportService.build_morning_report()` + `_build_paper_ref_only()`：
- `papers[]` 来自 `completed_work_keys`
- paper 元数据主要来自 `JobContext.metadata["work_meta"][work_key]`（由 discovery handler 写入）
- `summary.llm_summary` 当前是 lightweight 实现：从 parser 的 `chunks[0].text` 截断到 800 字（不依赖 LLM）
- `index` 当前为占位（`IndexInfo()` 默认空）
- `keys` 字段保留但在 ref-only 场景通常为 `null`

**示例（字段以 `nexus/app/models/report_models.py` 为准）**：

```json
{
  "trace_id": "uuid",
  "task_type": "MORNING_REPORT",
  "requested_limit": 5,
  "paper_count": 1,
  "papers": [
    {
      "paper": {
        "title": "Paper Title",
        "authors": ["Author 1"],
        "pdf_url": "https://example.com/paper.pdf",
        "openalex_id": "W123",
        "doi": "10.1234/example",
        "publication_date": "2024-01-01",
        "original_url": "https://example.com/paper.pdf"
      },
      "summary": {
        "llm_summary": "..."
      },
      "index": {
        "collection": null,
        "vector_count": null,
        "persist_dir": null
      },
      "keys": {
        "work_key": "task:uuid:work:0",
        "download_key": null,
        "parse_key": null,
        "index_key": null
      }
    }
  ],
  "failure_count": 0,
  "failures": [],
  "keys": {
    "init_key": null,
    "discovery_key": null
  },
  "input": {
    "query": "large language model",
    "filters": {
      "publication_year": "2024"
    }
  }
}
```

#### SUMMARY_REPORT（当前实现的真实语义）
见 `ReportService.build_summary_report()`：
- `overview_md`：通过 `artifacts_refs["overview"]` 指向的 `overview_service` Query API 拉取
- `paper_count`：优先从 overview meta 读取

```json
{
  "trace_id": "uuid",
  "task_type": "SUMMARY_REPORT",
  "overview_md": "## Background\n...",
  "meta": {"paper_count": 3},
  "paper_count": 3
}
```

### 3.3 获取原始制品：`GET /api/v1/jobs/{trace_id}/artifacts/{artifact_key}`
见 `StatusService.get_artifact_stream()`，当前支持的 ref → Query API 映射如下（按 `service/type` 判断）：
- `discovery/search_result` → `GET {discovery_base_url}/v1/results/{id}`
- `parser/parsed_doc` → `GET {parser_base_url}/v1/parsed/{id}`
- `download/file` → `GET {download_base_url}/v1/files/{id}/signed_url`
- `overview/overview_report` → `GET {overview_base_url}/v1/reports/{id}`

> 这意味着 `/artifacts/*` 的 JSON 结构 **由各微服务 API 决定**；Nexus 只做“ref → API → JSON”的代理。

---

## 4) 模式解释（为什么这样设计）

### 4.1 Claim-check（ref-only 变体）
- MQ 只承载控制面（trace/work_key/params/ref），不承载大对象
- 大对象（PDF、parsed chunks、overview 报告等）由 owning service 自治存储（MinIO/DB/Chroma）

### 4.2 Schema-on-read（读时组装）
- Report API 负责向业务层提供稳定模型
- 工具服务的内部结构可演进，上层应用不需要同步理解所有“原始格式”

### 4.3 为什么 artifacts 不是 “MinIO stream passthrough”
在当前仓库里：
- Nexus `/artifacts/*` 走的是 Query API Proxy（见 `StatusService.get_artifact_stream()`）
- 对 `download/file` 这类二进制对象，最佳实践是由 download_service 提供 signed URL；Nexus 返回 JSON（上层再拉 signed URL）

---

## 5) 常见坑（结合真实代码）

### 5.1 不要把 artifacts 的 URL 当成 artifact_key
正确方式：
- 从 `GET /jobs/{trace_id}` 返回的 `artifacts` 字典里取 key（例如 `search_results`）
- 直接请求 value（URL），或把 key 填到 `/artifacts/{artifact_key}`

错误方式（会 404）：
- 把 `download_url` 整段 URL encode 后塞进 `{artifact_key}`

### 5.2 SUMMARY_REPORT “卡在 processing” 的自愈
当前代码中 `StatusService.get_job_status()` 存在 best-effort reconcile：
- 如果发现 SUMMARY_REPORT 已经满足 “completed+failed >= total”，但 stage 仍为 `processing`
- 会触发一次 `orchestrator._check_completion(trace_id)` 尝试补发 `cmd.overview.start` 或直接完成

---

## 6) 应用层使用建议
- **默认只用 report**：`GET /api/v1/jobs/{trace_id}/report`
- **需要排查/高级需求再用 artifacts**：`GET /api/v1/jobs/{trace_id}/artifacts/{artifact_key}`
- **需要二进制 PDF**：先通过 artifacts 拿到 signed_url（download_service 返回），再直接拉 signed_url
