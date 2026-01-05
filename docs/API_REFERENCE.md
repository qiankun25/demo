# API 文档（汇总）

本文档汇总以下服务的 HTTP API：
- Application Service（实现：`application_service/main.py`）- 用户服务与应用层 API
- Nexus Orchestration Service（实现：`nexus/app/api/routes.py`）
- Retrieval Service（实现：`tool_services/retrieval_service/main.py`）
- Translator Service（实现：`tool_services/translator_service/main.py`）
- Indexing Service（实现：`tool_services/indexing_service/app/main.py`）
- Strict Microservices Query APIs（用于编排/聚合的只读查询 API，见各服务 `*/app/main.py` 与 `download_service` 的 `routes/`）

---

## 目录（Table of Contents）

- [API 文档（汇总）](#api-文档汇总)
  - [目录（Table of Contents）](#目录table-of-contents)
  - [0. 阅读指南（推荐用法 + 术语 + 端到端示例）](#0-阅读指南推荐用法--术语--端到端示例)
    - [0.1 服务地址与版本前缀](#01-服务地址与版本前缀)
    - [0.2 通用约定（Content-Type / 错误格式 / ID 编码）](#02-通用约定content-type--错误格式--id-编码)
    - [0.3 关键术语（trace\_id / task\_type / work\_key / artifact\_key / ref-only）](#03-关键术语trace_id--task_type--work_key--artifact_key--ref-only)
    - [0.4 推荐调用路径（80% Report + 20% Artifacts）](#04-推荐调用路径80-report--20-artifacts)
    - [0.5 端到端示例（MORNING\_REPORT / SUMMARY\_REPORT）](#05-端到端示例morning_report--summary_report)
      - [MORNING\_REPORT：提交 → 轮询 → 获取报告](#morning_report提交--轮询--获取报告)
      - [SUMMARY\_REPORT：提交 → 轮询 → 获取报告](#summary_report提交--轮询--获取报告)
    - [0.6 常见坑与排查建议](#06-常见坑与排查建议)
  - [1. Nexus Orchestration Service](#1-nexus-orchestration-service)
    - [1.1 基本信息](#11-基本信息)
    - [1.2 数据模型（Schema）](#12-数据模型schema)
      - [JobSubmitRequest](#jobsubmitrequest)
      - [JobSubmitResponse](#jobsubmitresponse)
      - [JobStatusResponse](#jobstatusresponse)
    - [1.3 API 列表](#13-api-列表)
      - [0) 文档约定](#0-文档约定)
      - [1) 提交任务](#1-提交任务)
      - [2) 查询任务状态（含制品清单）](#2-查询任务状态含制品清单)
      - [3) 获取标准化报告（推荐）](#3-获取标准化报告推荐)
      - [4) 获取任务制品（原始 JSON / Query API 代理）](#4-获取任务制品原始-json--query-api-代理)
      - [5) 健康检查](#5-健康检查)
      - [6) 就绪检查](#6-就绪检查)
  - [2. Retrieval Service（统一检索编排层）](#2-retrieval-service统一检索编排层)
    - [2.1 基本信息](#21-基本信息)
    - [2.2 API](#22-api)
      - [1) 健康检查](#1-健康检查)
      - [2) 统一检索（本地优先 + 外部补足）](#2-统一检索本地优先--外部补足)
      - [3) 语义检索（透传 indexing\_service）](#3-语义检索透传-indexing_service)
      - [4) 知识库概览（透传 indexing\_service）](#4-知识库概览透传-indexing_service)
      - [5) 查看某个文档的编排状态（本服务 SQLite）](#5-查看某个文档的编排状态本服务-sqlite)
  - [3. Translator Service（多模态翻译）](#3-translator-service多模态翻译)
    - [3.1 基本信息](#31-基本信息)
    - [3.2 API](#32-api)
      - [1) 健康检查](#1-健康检查-1)
      - [2) 翻译（文本 / 多模态）](#2-翻译文本--多模态)
      - [3) 论文翻译](#3-论文翻译)
      - [4) Prompt 管理（系统 Prompt）](#4-prompt-管理系统-prompt)
      - [5) 术语表管理（Postgres + 用户定义术语）](#5-术语表管理postgres--用户定义术语)
        - [GET /glossary](#get-glossary)
        - [GET /glossary/{term}](#get-glossaryterm)
        - [POST /glossary](#post-glossary)
        - [PUT /glossary/{term}](#put-glossaryterm)
  - [4. Indexing Service（索引 / 语义检索）](#4-indexing-service索引--语义检索)
    - [4.1 基本信息](#41-基本信息)
    - [4.2 API](#42-api)
      - [0) 健康检查](#0-健康检查)
      - [1) 写入索引（入库 + 向量写入）](#1-写入索引入库--向量写入)
      - [2) 知识库概览](#2-知识库概览)
      - [3) 语义检索 / 混合检索](#3-语义检索--混合检索)
  - [5. Strict Microservices Query APIs（编排/聚合用只读查询）](#5-strict-microservices-query-apis编排聚合用只读查询)
    - [5.1 Discovery Service Query API](#51-discovery-service-query-api)
    - [5.2 Discovery Service Min Fields（给 Nexus fan-out 用）](#52-discovery-service-min-fields给-nexus-fan-out-用)
    - [5.3 Download Service APIs（download + files）](#53-download-service-apisdownload--files)
      - [5.3.1 创建下载任务](#531-创建下载任务)
      - [5.3.2 查询下载任务状态](#532-查询下载任务状态)
      - [5.3.3 获取文件 Signed URL（Query API）](#533-获取文件-signed-urlquery-api)
    - [5.4 Parser Service Parsed Query API](#54-parser-service-parsed-query-api)
    - [5.5 Overview Service Report Query API](#55-overview-service-report-query-api)
      - [5.5.1 Prompt 管理（系统 Prompt）](#551-prompt-管理系统-prompt)
    - [5.6 Indexing Service Query APIs（给 Retrieval/Nexus 使用）](#56-indexing-service-query-apis给-retrievalnexus-使用)
  - [6. Application Service（用户服务与应用层）](#6-application-service用户服务与应用层)
    - [6.1 基本信息](#61-基本信息)
    - [6.2 认证 API](#62-认证-api)
      - [1) 用户注册](#1-用户注册)
      - [2) 用户登录](#2-用户登录)
    - [6.3 订阅管理 API](#63-订阅管理-api)
      - [1) 创建订阅](#1-创建订阅)
      - [2) 获取所有订阅](#2-获取所有订阅)
      - [3) 获取指定订阅](#3-获取指定订阅)
      - [4) 更新订阅](#4-更新订阅)
      - [5) 删除订阅](#5-删除订阅)
    - [6.4 学术日报 API](#64-学术日报-api)
      - [1) 提交学术日报任务](#1-提交学术日报任务)
      - [2) 获取学术日报结果](#2-获取学术日报结果)
    - [6.5 文献综述 API](#65-文献综述-api)
      - [创建文献综述](#创建文献综述)
    - [6.6 文献检索 API](#66-文献检索-api)
      - [文献检索](#文献检索)
    - [6.7 文献翻译 API](#67-文献翻译-api)
      - [翻译论文文件](#翻译论文文件)
      - [健康检查](#健康检查)
      - [根路径](#根路径)

---

<a id="guide"></a>
## 0. 阅读指南（推荐用法 + 术语 + 端到端示例）

本文件目标是作为“最终可交付”的 API Documentation：既能查单个 endpoint 的参数/响应，也能指导应用层以正确方式获取任务结果。

<a id="guide-0-1"></a>
### 0.1 服务地址与版本前缀

本仓库在本地默认端口（以本文件现有描述为准）：

| 服务 | Base URL | API 前缀 / 版本 |
|---|---|---|
| Application Service | `http://localhost:8005` | `/api` |
| Nexus Orchestration Service | `http://localhost:8000` | `/api/v1` |
| Retrieval Service | `http://localhost:8003` | 无（根路径） |
| Translator Service | `http://localhost:8002` | 无（根路径） |
| Indexing Service | `http://localhost:8020` | 无（根路径） |
| Strict Microservices Query APIs | 由各微服务部署决定 | 多为 `/v1/...`（见第 5 章） |

> 注：Nexus 的 OpenAPI 文档入口见 [1.1 基本信息](#nexus-1-1)。

<a id="guide-0-2"></a>
### 0.2 通用约定（Content-Type / 错误格式 / ID 编码）

- **Content-Type**：所有 JSON 请求体使用 `Content-Type: application/json`。
- **通用错误响应**：本文中多数服务基于 FastAPI，常见错误体为：

```json
{
  "detail": "string"
}
```

- **URL/Path 编码**：
  - `trace_id` 通常为 UUID 字符串，可直接放入路径。
  - `artifact_key` 可能包含 `:` 等字符（例如 `parser:task:<trace_id>:work:0`）。在作为 path 参数时，客户端应进行 URL path segment 编码（例如 JS `encodeURIComponent` / Python `quote`），以避免路由解析问题。

<a id="guide-0-3"></a>
### 0.3 关键术语（trace_id / task_type / work_key / artifact_key / ref-only）

- **trace_id**：任务追踪 ID（Nexus `POST /api/v1/jobs` 返回），用于后续查询状态/报告/制品。
- **task_type**：任务类型（如 `MORNING_REPORT`、`SUMMARY_REPORT`）。
- **work_key**：fan-out 子任务的 key，canonical 形式通常为 `task:{trace_id}:work:{index}`（见仓库架构说明）。
- **artifact_key**：制品索引 key（来自 `GET /api/v1/jobs/{trace_id}` 的 `artifacts` 字段的 key），不同任务/阶段集合不同。
- **ref-only（当前仓库默认实现）**：跨服务不传大对象；Nexus `/artifacts/*` 通过 `artifacts_refs` 把 ref 映射到各微服务的只读 Query API 并代理返回 JSON（而不是从 MinIO 直接透传字节流）。

<a id="guide-0-4"></a>
### 0.4 推荐调用路径（80% Report + 20% Artifacts）

面向应用层的推荐使用方式（以当前仓库实现为准）：

- **80% 常规场景（推荐）**：用标准化报告
  - `GET /api/v1/jobs/{trace_id}/report`
  - 优点：一次调用拿到统一稳定结构，无需理解底层工具服务的原始 JSON 形状。
- **20% 调试/高级场景**：按需取“原始制品”
  - `GET /api/v1/jobs/{trace_id}/artifacts/{artifact_key}`
  - 注意：该接口返回的是“Query API Proxy 的 JSON”，结构由对应微服务 Query API 决定（见第 5 章）。
- **需要二进制文件（如 PDF）**：
  - 通常先通过 artifacts 取到 download_service 返回的 signed URL（JSON），再由客户端直接拉取该 signed URL 获取字节流。

<a id="guide-0-5"></a>
### 0.5 端到端示例（MORNING_REPORT / SUMMARY_REPORT）

#### MORNING_REPORT：提交 → 轮询 → 获取报告

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "MORNING_REPORT",
    "parameters": {
      "limit": 5,
      "query": "large language model",
      "filters": { "publication_year": "2024" }
    }
  }'
```

轮询状态：

```bash
curl http://localhost:8000/api/v1/jobs/{trace_id}
```

完成后获取标准化报告：

```bash
curl http://localhost:8000/api/v1/jobs/{trace_id}/report
```

#### SUMMARY_REPORT：提交 → 轮询 → 获取报告

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "SUMMARY_REPORT",
    "parameters": {
      "papers": [
        { "pdf_url": "https://example.com/paper.pdf", "title": "Paper Title" }
      ]
    }
  }'
```

```bash
curl http://localhost:8000/api/v1/jobs/{trace_id}/report
```

<a id="guide-0-6"></a>
### 0.6 常见坑与排查建议

- **不要把 artifacts 的 URL 当成 artifact_key**
  - `GET /api/v1/jobs/{trace_id}` 返回的 `artifacts` 是 `{artifact_key: download_url}` 映射。
  - 正确做法：直接请求 `download_url`；或把 `artifact_key` 填入 `GET /api/v1/jobs/{trace_id}/artifacts/{artifact_key}`。
  - 错误做法：把 `download_url` 整段 URL-encode 后再塞回 `{artifact_key}`（会 404）。
- **Report API 只对 completed 生效**
  - `GET /api/v1/jobs/{trace_id}/report` 在任务未完成时会返回 `400`（提示当前 stage/processing）。
  - 应先轮询 `GET /api/v1/jobs/{trace_id}`，确认 `status` 已完成后再取报告。
- **artifact_key 建议做路径编码**
  - 当 artifact key 含 `:` 等字符时，客户端调用 `/artifacts/{artifact_key}` 时建议对 path segment 做编码，避免网关/客户端对路径的解析差异。

---

<a id="nexus"></a>
## 1. Nexus Orchestration Service

<a id="nexus-1-1"></a>
### 1.1 基本信息
- 默认监听：`http://localhost:8000`
- API 前缀：`/api/v1`（见 [`nexus/app/core/config.py`](../nexus/app/core/config.py)）
- OpenAPI：
  - `GET /api/v1/openapi.json`
  - `GET /api/v1/docs`
  - `GET /api/v1/redoc`

<a id="nexus-1-2"></a>
### 1.2 数据模型（Schema）

#### JobSubmitRequest
用于提交任务。

```json
{
  "task_type": "string",
  "parameters": {
    "anyKey": "anyValue"
  }
}
```

字段说明（见 [`nexus/app/models/api_models.py`](../nexus/app/models/api_models.py)）：
- `task_type`：任务类型（字符串）
- `parameters`：任务参数（任意键值对，默认 `{}`）

**当前支持的高层任务（重点）**：
- `MORNING_REPORT`
  - 常用参数（透传给 discovery 工具服务并影响扇出数量）：
    - `limit`（int）：期望返回论文数；Nexus 会保存为 `requested_limit`（默认 5）
    - `query`（string）：检索 query
    - `filters`（object）：过滤条件（示例：`publication_year`/`journal`/`author` 等；由 discovery_service 解释）
- `SUMMARY_REPORT`
  - 必填参数：
    - `papers`（list[object]）：论文列表（ref-only 模式下必须直接传）
      - 每个 paper 至少包含 `pdf_url`（string，必填）
      - 可选：`title/authors/canonical_id/doi/publication_date`

#### JobSubmitResponse

```json
{
  "trace_id": "string",
  "status": "submitted",
  "message": "Job submitted successfully"
}
```

字段说明（见 [`nexus/app/models/api_models.py`](../nexus/app/models/api_models.py)）：
- `trace_id`：任务追踪 ID（用于后续查询）
- `status`：固定返回 `"submitted"`
- `message`：固定返回 `"Job submitted successfully"`

#### JobStatusResponse

```json
{
  "trace_id": "string",
  "task_type": "string",
  "status": "string",
  "total_work_items": 0,
  "completed_count": 0,
  "failed_count": 0,
  "pending_count": 0,
  "artifacts": {
    "artifact_key": "/api/v1/jobs/{trace_id}/artifacts/{artifact_key}"
  },
  "failures": [
    {
      "any": "any"
    }
  ]
}
```

字段说明（见 [`nexus/app/models/api_models.py`](../nexus/app/models/api_models.py)）：
- `status`：当前状态（由编排器填充，见 [`nexus/app/services/status_service.py`](../nexus/app/services/status_service.py)）
- `artifacts`：制品 key 到下载 URL 的映射（URL 形如 `/api/v1/jobs/{trace_id}/artifacts/{artifact_key}`）
- `failures`：失败明细列表（字典数组）

---

<a id="nexus-1-3"></a>
### 1.3 API 列表

#### 0) 文档约定
- Base URL：`http://localhost:8000`
- 通用请求头：
  - `Content-Type: application/json`（有请求体时必填）
- 通用错误响应（FastAPI 默认 `HTTPException`）：

```json
{
  "detail": "string"
}
```

#### 1) 提交任务

**Method & Path**  
`POST /api/v1/jobs`

**描述**  
提交一个任务到编排器执行（见 [`nexus/app/api/routes.py`](../nexus/app/api/routes.py) 与 [`nexus/app/services/job_service.py`](../nexus/app/services/job_service.py)）。

**请求头**  
- `Content-Type: application/json`

**请求体（application/json）**  
Schema：`JobSubmitRequest`

```json
{
  "task_type": "example_task",
  "parameters": {
    "foo": "bar"
  }
}
```

**响应**
- `202 Accepted`（application/json）  
  Schema：`JobSubmitResponse`

```json
{
  "trace_id": "2f4a6df3-4f6e-4e05-8a54-3c01caa6a9b2",
  "status": "submitted",
  "message": "Job submitted successfully"
}
```

- `400 Bad Request`（application/json）  

```json
{
  "detail": "string"
}
```

- `500 Internal Server Error`（application/json）

```json
{
  "detail": "string"
}
```

**请求示例（curl）**

```bash
curl -X POST http://localhost:8000/api/v1/jobs ^
  -H "Content-Type: application/json" ^
  -d "{\"task_type\":\"example_task\",\"parameters\":{\"foo\":\"bar\"}}"
```

---

#### 2) 查询任务状态（含制品清单）
**Method & Path**  
`GET /api/v1/jobs/{trace_id}`

**描述**  
返回任务状态、进度统计、制品下载 URL（见 [`nexus/app/api/routes.py`](../nexus/app/api/routes.py) 与 [`nexus/app/services/status_service.py`](../nexus/app/services/status_service.py)）。

**路径参数**
- `trace_id`（string，必填）：任务追踪 ID

**响应**
- `200 OK`（application/json）  
  Schema：`JobStatusResponse`

```json
{
  "trace_id": "2f4a6df3-4f6e-4e05-8a54-3c01caa6a9b2",
  "task_type": "example_task",
  "status": "running",
  "total_work_items": 3,
  "completed_count": 1,
  "failed_count": 0,
  "pending_count": 2,
  "artifacts": {
    "search_results": "/api/v1/jobs/2f4a6df3-4f6e-4e05-8a54-3c01caa6a9b2/artifacts/search_results",
    "parser:task:2f4a6df3-4f6e-4e05-8a54-3c01caa6a9b2:work:0": "/api/v1/jobs/2f4a6df3-4f6e-4e05-8a54-3c01caa6a9b2/artifacts/parser:task:2f4a6df3-4f6e-4e05-8a54-3c01caa6a9b2:work:0"
  },
  "failures": []
}
```

说明：
- `artifacts` 的结构是 `{artifact_key: download_url}`。
- `download_url` 是可直接请求的地址；不要把它 URL-encode 后再塞进 `{artifact_key}`。
- `artifact_key` 是由 Nexus 收到 `evt.*` 后将 `result_ref` 归档到 `JobContext.artifacts_refs` 生成的；不同任务/不同阶段 key 集合不同，以上仅为示例。

- `404 Not Found`（application/json）

```json
{
  "detail": "Job 2f4a6df3-4f6e-4e05-8a54-3c01caa6a9b2 not found"
}
```

**请求示例（curl）**

```bash
curl http://localhost:8000/api/v1/jobs/2f4a6df3-4f6e-4e05-8a54-3c01caa6a9b2
```

---

#### 3) 获取标准化报告（推荐）
**Method & Path**  
`GET /api/v1/jobs/{trace_id}/report`

**描述**  
获取已完成任务的标准化聚合报告。该 API 自动聚合所有相关 artifacts，并转换为统一的业务层数据模型，适合大多数使用场景（80%）。

**路径参数**
- `trace_id`（string，必填）：任务追踪 ID

**响应**
- `200 OK`（application/json）

响应格式取决于任务类型：

**MORNING_REPORT 响应格式**（见 [`nexus/app/models/report_models.py`](../nexus/app/models/report_models.py)）：

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
    "filters": {"publication_year": "2024"}
  }
}
```

**SUMMARY_REPORT 响应格式**：

```json
{
  "trace_id": "uuid",
  "task_type": "SUMMARY_REPORT",
  "overview_md": "# Summary\n\nThis is a summary.",
  "meta": {
    "model": "gpt-4",
    "paper_count": 3,
    "domain": "AI",
    "style": "academic"
  },
  "paper_count": 3
}
```

- `400 Bad Request`（application/json）

```json
{
  "detail": "Job {trace_id} is not completed yet (current stage: processing)"
}
```

- `404 Not Found`（application/json）

```json
{
  "detail": "Job {trace_id} not found"
}
```

- `500 Internal Server Error`（application/json）

```json
{
  "detail": "Failed to generate report: {error_message}"
}
```

**使用建议**
- **常规场景**（推荐）：使用此 API 获取标准化报告，简单高效
- **高级场景**（调试、特殊需求）：如需访问原始工具服务数据格式，使用 `GET /api/v1/jobs/{trace_id}/artifacts/{artifact_key}`

**请求示例（curl）**

```bash
curl http://localhost:8000/api/v1/jobs/2f4a6df3-4f6e-4e05-8a54-3c01caa6a9b2/report
```

---

#### 4) 获取任务制品（原始 JSON / Query API 代理）
**Method & Path**  
`GET /api/v1/jobs/{trace_id}/artifacts/{artifact_key}`

**描述**  
获取任务某个制品的“原始 JSON”（调试/高级场景）。  
**当前实现（非常重要）**：Nexus 会根据 `artifact_key` 对应的 `result_ref` 去调用下游微服务 Query API，再把 JSON 直接返回（`application/json`），而不是从 MinIO 读取字节流透传。

**路径参数**
- `trace_id`（string，必填）：任务追踪 ID
- `artifact_key`（string，必填）：制品 key（来自 `GET /api/v1/jobs/{trace_id}` 的 `artifacts` 映射键）

**响应**
- `200 OK`（application/json）
  - Body 为对应微服务 Query API 的 JSON 响应（形状由微服务定义）

示例（制品为 JSON 时的响应体示例）：

```json
{
  "example": "artifact payload"
}
```

- `404 Not Found`（application/json）

```json
{
  "detail": "Artifact search_results not found in job 2f4a6df3-4f6e-4e05-8a54-3c01caa6a9b2"
}
```

- `500 Internal Server Error`（application/json）

```json
{
  "detail": "Failed to retrieve artifact: string"
}
```

**请求示例（curl：下载到文件）**

```bash
curl -L http://localhost:8000/api/v1/jobs/2f4a6df3-4f6e-4e05-8a54-3c01caa6a9b2/artifacts/search_results -o search_results.json
```

---

#### 5) 健康检查
**Method & Path**  
`GET /api/v1/health`

**描述**  
检查消息队列与存储是否健康（见 [`nexus/app/api/routes.py`](../nexus/app/api/routes.py)）。

**响应**
- `200 OK`（application/json）

```json
{
  "status": "healthy",
  "details": {
    "mq": "healthy",
    "storage": "healthy"
  }
}
```

说明：代码中计算了 `status_code` 变量，但未实际设置到 HTTP 响应；因此当前实现通常返回 `200`，建议以 `status/details` 字段判断健康状态。

---

#### 6) 就绪检查
**Method & Path**  
`GET /api/v1/ready`

**描述**  
检查是否可以接入流量（当前仅检查 MQ）（见 [`nexus/app/api/routes.py`](../nexus/app/api/routes.py)）。

**响应**
- `200 OK`（application/json）

```json
{
  "status": "ready"
}
```

- `503 Service Unavailable`（application/json）

```json
{
  "detail": "Service not ready"
}
```

---

<a id="retrieval"></a>
## 2. Retrieval Service（统一检索编排层）

<a id="retrieval-2-1"></a>
### 2.1 基本信息
- 默认监听：`http://localhost:8003`

<a id="retrieval-2-2"></a>
### 2.2 API

#### 1) 健康检查
- `GET /health`：聚合健康（返回 `service/timestamp/components` 等字段）
- `GET /health/live`：liveness
- `GET /health/ready`：readiness（至少检查本地 SQLite + 下游 indexing_service）

#### 2) 统一检索（本地优先 + 外部补足）
**Method & Path**  
`POST /search`

**请求体（application/json）**（实现：`tool_services/retrieval_service/main.py::SearchRequest`）

```json
{
  "query": "GNN",
  "k": 5,
  "kinds": ["paper"],
  "filters": {},
  "sources": ["openalex"]
}
```

**响应（application/json）**（实现：`SearchResponse`）

```json
{
  "query": "GNN",
  "local_hits": [],
  "external_hits": [],
  "merged_hits": [],
  "ingest_enqueued": 0
}
```

说明：
- `local_hits` 通过调用 indexing_service `/search` 得到（并按 `min_local_score` 阈值过滤）
- `external_hits` 通过外部发现（mic_find_url/discovery connector）得到（可选异步入库）

#### 3) 语义检索（透传 indexing_service）
**Method & Path**  
`POST /semantic_search`

**请求体（application/json）**（实现：`SemanticSearchRequest`）

```json
{
  "query": "graph neural network",
  "k": 10,
  "min_score": 0.0
}
```

**响应（application/json）**（实现：`SemanticSearchResponse`；字段较多，示意）：

```json
{
  "query": "graph neural network",
  "k": 10,
  "hits": [
    {
      "score": 0.12,
      "chunk_id": "c1",
      "doc_id": "d1",
      "paper": {},
      "chunk_text": "..."
    }
  ],
  "meta": {}
}
```

#### 4) 知识库概览（透传 indexing_service）
**Method & Path**  
`GET /kb/overview?limit=20&offset=0`

**响应**：与 indexing_service `/kb/overview` 相同（见下方 Indexing Service 与 Strict Query APIs 部分）。

#### 5) 查看某个文档的编排状态（本服务 SQLite）
**Method & Path**  
`GET /status/{doc_key}`

**响应（示意）**：

```json
{
  "doc_key": "cid:W123",
  "status": "INDEXED",
  "canonical_id": "W123",
  "pdf_sha256": "....",
  "last_error": null
}
```

---

<a id="translator"></a>
## 3. Translator Service（多模态翻译）

<a id="translator-3-1"></a>
### 3.1 基本信息
- 默认监听：`http://localhost:8002`

<a id="translator-3-2"></a>
### 3.2 API

#### 1) 健康检查
**Method & Path**  
`GET /health`

**响应**
- `200 OK`（application/json）

```json
{
  "service": "translator_service",
  "status": "ready",
  "components": {
    "siliconflow_api_key": "configured",
    "baidu_ocr_creds": "configured"
  },
  "timestamp": 1730000000.0
}
```

补充：
- `GET /health/live`：`{"status":"alive"}`
- `GET /health/ready`：返回 `{"status":"ready"|"not ready","components":{...}}`（不做网络探测，仅检查关键配置是否存在）

#### 2) 翻译（文本 / 多模态）
**Method & Path**  
`POST /translate`

**请求头**  
- `Content-Type: application/json`

**请求体（application/json）**（见 [`tool_services/translator_service/main.py`](../tool_services/translator_service/main.py)）

```json
{
  "text": "string",
  "images": ["/path/to/image.png", "https://example.com/a.png"],
  "target_lang": "zh"
}
```

**响应**
- `200 OK`（application/json）  
  Schema：`TranslateResponse`

```json
{
  "text_translated": "string",
  "images_translated": [
    {
      "input": "/path/to/your/image.png",
      "caption": "string",
      "extracted_text": "string",
      "translated_text": "string"
    }
  ],
  "meta": {
    "target_lang": "zh",
    "image_count": 1,
    "model": "deepseek-ai/DeepSeek-V3"
  }
}
```

 - `500 Internal Server Error`（application/json）

```json
{
  "detail": "string"
}
```

**缓存行为**
- 成功的 `POST /translate` 会将请求（`text`、`images`、`target_lang`）的结果写入 Redis 缓存；默认 TTL 6 小时，可通过 `TRANSLATOR_CACHE_TTL_SECONDS` 调整。
- 只要请求 payload 完全一致且缓存未过期（`TRANSLATOR_REDIS_URL` 配置存在），后续请求直接返回缓存，避免重复调用下游模型。

**请求示例（curl：纯文本）**

```bash
curl -X POST http://localhost:8002/translate ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"The rapid development of large language models has revolutionized natural language processing.\",\"target_lang\":\"zh\"}"
```

**请求示例（curl：多模态）**

```bash
curl -X POST http://localhost:8002/translate ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"Translate the following and describe the image.\",\"images\":[\"/path/to/your/image.png\"],\"target_lang\":\"zh\"}"
```

---

#### 3) 论文翻译
**Method & Path**  
`POST /translate-paper`

**请求头**  
- `Content-Type: multipart/form-data`

**请求体（multipart/form-data）**  
上传一个论文文件，可选指定目标语言。字段如下：

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `file` | file | 是 | 论文文件（.pdf） |
| `target_lang` | string | 否 | 目标语言代码（如 "zh"、"en"），默认为 "zh" |

**响应 - 200 OK（application/json）**  
Schema：`TranslatePaperResponse`

```json
{
  "text_translated": "提取并翻译后的完整论文文本...",
  "meta": {
    "target_lang": "zh",
    "file_name": "paper.pdf",
    "model": "deepseek-ai/DeepSeek-V3"
  }
}
```

**响应字段说明：**
- `text_translated`: 提取并翻译后的完整论文文本。
- `meta.target_lang`: 实际使用的目标语言。
- `meta.file_name`: 原始上传的文件名（不含路径）。
- `meta.model`: 所用翻译模型标识。

**错误响应：**
- `400 Bad Request`: 文件格式错误或缺少文件
  ```json
  {
    "error": "only PDF files are supported"
  }
  ```
- `500 Internal Server Error`: 翻译失败
  ```json
  {
    "error": "PDF parsing failed: ..."
  }
  ```

**请求示例（curl）：**
```bash
curl -X POST http://localhost:8002/translate-paper \
  -F "file=@paper.pdf" \
  -F "target_lang=zh"
```

**请求示例（Python requests）：**
```python
import requests

url = "http://localhost:8002/translate-paper"
files = {"file": open("paper.pdf", "rb")}
data = {"target_lang": "zh"}

response = requests.post(url, files=files, data=data)
result = response.json()
print(result["text_translated"])
```

---

#### 4) Prompt 管理（系统 Prompt）
**Method & Path**
`GET /prompts`  
`GET /prompts/{prompt_key}`  
`PUT /prompts/{prompt_key}`

**描述**  
系统 Prompt 配置文件位于 `tool_services/translator_service/prompts.json`。每个 Prompt 包含 `template`（支持 Python 形式的 `{placeholder}`）和 `description`，运行时会被加载。通过上述接口可以读取当前 Prompt 以及在不重启服务的情况下更新 template/description，更新会直接写回 JSON 文件，下一次模型调用立即生效。

**GET /prompts**

```json
{
  "prompts": [
    {
      "key": "multimodal_translation",
      "template": "You are a professional multilingual translator...",
      "description": "Used when translating text+image payloads via SiliconFlow multimodal chat."
    }
  ]
}
```

**GET /prompts/{prompt_key}**
返回指定 Prompt：

```json
{
  "key": "image_caption",
  "template": "You are a helpful assistant. Describe the image in {target_lang}. Return a short caption only.",
  "description": "Used by the translator fallback path that only captions images."
}
```

**PUT /prompts/{prompt_key}**
请求体（application/json）：

```json
{
  "template": "You are an elite translator. Translate into {target_lang}. Deliver JSON only.",
  "description": "调试时临时替换 Prompt。"
}
```

响应体：同 `GET /prompts/{prompt_key}`，并且 `tool_services/translator_service/prompts.json` 会被更新。

---

#### 5) 术语表管理（Postgres + 用户定义术语）
**描述**  
- `translator_glossary` 表保存学术术语（`term` 主键，包含 `definition`、`domain`、`created_at`、`updated_at`），启动时自动建表。
- 通过下列 API 用户可以写入/更新术语，后续翻译可直接复用特定术语输出。
**环境变量**
- `TRANSLATOR_DB_URL`：Postgres DSN，示例 `postgresql+asyncpg://translator_user:translator_pass@db_translator:5432/translator`。

##### GET /glossary
**Method & Path**  
`GET /glossary`

**描述**  
列出所有术语，支持 query 参数 `domain` 过滤。

**响应（200 OK）**
```json
{
  "terms": [
    {
      "term": "LLM",
      "definition": "Large language model，首字母大写以保留专有名词输出",
      "domain": "research",
      "created_at": "2025-01-04T10:00:00Z",
      "updated_at": "2025-01-04T10:00:00Z"
    }
  ]
}
```

##### GET /glossary/{term}
**Method & Path**  
`GET /glossary/{term}`

**描述**  
按精确 `term` 查询（大小写需与存储一致，支持 URL encode）。

**响应（200 OK）**  
Schema：`GlossaryTermResponse`（含 `created_at`/`updated_at`）。

##### POST /glossary
**Method & Path**  
`POST /glossary`

**请求头**  
- `Content-Type: application/json`

**请求体**
```json
{
  "term": "RAG",
  "definition": "Retrieval-Augmented Generation（前缀保持大写）",
  "domain": "research"
}
```

**响应（201 Created）**
Schema：`GlossaryTermResponse`。

**错误**
- `409 Conflict`：术语已存在。
- `400 Bad Request`：`term` 或 `definition` 为空。

##### PUT /glossary/{term}
**Method & Path**  
`PUT /glossary/{term}`

**描述**  
可更新 `definition` 和/或 `domain`，至少提供一项。

**请求体**
```json
{
  "definition": "Retrieval-Augmented Generation（确保大写）"
}
```

**响应（200 OK）**
返回更新后的 `GlossaryTermResponse`。

**错误**
- `404 Not Found`：术语不存在。
- `400 Bad Request`：未提供可更新字段。

---

<a id="indexing"></a>
## 4. Indexing Service（索引 / 语义检索）

<a id="indexing-4-1"></a>
### 4.1 基本信息
- 默认监听：`http://localhost:8020`

<a id="indexing-4-2"></a>
### 4.2 API

#### 0) 健康检查
- `GET /health`：聚合健康（返回 `service/timestamp/components` 等字段）
- `GET /health/live`：liveness（`{"status":"alive"}`）
- `GET /health/ready`：readiness（检查 DB + Chroma collection）

#### 1) 写入索引（入库 + 向量写入）
**Method & Path**  
`POST /index`

**请求体（application/json）**（实现：`tool_services/indexing_service/app/schemas/api_models.py::IndexRequest`）

```json
{
  "doc": {
    "doc_id": "d1",
    "canonical_id": "W123",
    "doc_type": "paper",
    "title": "Paper Title",
    "authors": ["A", "B"],
    "year": 2024,
    "source": "openalex",
    "pdf_sha256": "..."
  },
  "chunks": [
    {"chunk_id": "c1", "doc_id": "d1", "text": "chunk text"}
  ],
  "summary_keywords": {
    "summary": "optional summary",
    "summary_source": "generated_summary",
    "keywords": ["llm", "retrieval"]
  },
  "upsert": true
}
```

**响应（application/json）**（实现：`IndexResponse`）

```json
{
  "doc_id": "d1",
  "chunks_indexed": 1,
  "embed_dim": 256
}
```

#### 2) 知识库概览
**Method & Path**  
`GET /kb/overview?limit=20&offset=0`

**响应（application/json）**（实现：`KnowledgeBaseOverviewResponse`）

```json
{
  "docs_count": 1,
  "chunks_count": 1,
  "docs": [
    {
      "doc_id": "d1",
      "canonical_id": "W123",
      "doc_type": "paper",
      "title": "Paper Title",
      "year": 2024,
      "source": "openalex",
      "pdf_sha256": "...",
      "created_at_unix": 1730000000
    }
  ]
}
```

#### 3) 语义检索 / 混合检索
**Method & Path**  
`POST /search`

**描述**  
对本地已入库内容进行检索：
- `use_vector=true`：启用向量检索（语义检索，底层使用 Chroma）
- `use_fts=true`：启用全文关键词检索（若后端可用）并与向量检索结果融合
- 返回命中列表，每条包含 `doc`（文档元信息）、`chunk`（命中片段）、`score`（融合分）以及 `explain`（解释字段）

**请求头**  
- `Content-Type: application/json`

**请求体（application/json）**  

```json
{
  "query": "GNN",
  "k": 5,
  "kinds": ["paper"],
  "filters": {},
  "use_vector": true,
  "use_fts": false
}
```

字段说明：
- `query`（string，必填）：检索文本
- `k`（int，默认 10，范围 1~50）：返回 top-k 数量
- `kinds`（string[]，可选）：按资源种类过滤，可选值：`paper` / `dataset` / `code`；为空则不过滤
- `filters`（object，默认 `{}`）：过滤条件（当前实现至少支持 `canonical_id` 精确过滤）
- `use_vector`（bool，默认 true）：是否启用向量检索（语义检索）
- `use_fts`（bool，默认 true）：是否启用关键词检索并融合

**响应**
- `200 OK`（application/json）

响应体格式：

```json
{
  "query": "GNN",
  "hits": [
    {
      "doc": {
        "doc_id": "string",
        "canonical_id": "string",
        "doc_type": "paper",
        "title": "string"
      },
      "chunk": {
        "chunk_id": "string",
        "doc_id": "string",
        "text": "string",
        "page": 1,
        "paragraph": -1,
        "section_path": "string"
      },
      "score": 0.0,
      "explain": {
        "rrf": 0.0,
        "vector": 0.0,
        "fts": 0.0
      }
    }
  ]
}
```

说明：
- `hits` 可能为空数组 `[]`（表示没有命中，或库中尚无数据）
- `score` 为最终融合分（通常是 RRF 融合分）
- `explain.vector` 为向量相似度（越大越好；通常约等于 `1 - distance`）
- `explain.fts` 为关键词检索分（可能为 `null` 或缺失，取决于后端与开关）

**错误响应**
- `400 Bad Request`（application/json）

```json
{
  "detail": "string"
}
```

- `500/502`（application/json）

```json
{
  "detail": "string"
}
```

**请求示例（curl）**

```bash
curl -X POST "http://localhost:8020/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "GNN",
    "k": 5,
    "kinds": ["paper"],
    "filters": {},
    "use_vector": true,
    "use_fts": false
  }'
```

---

<a id="strict-query-apis"></a>
## 5. Strict Microservices Query APIs（编排/聚合用只读查询）

这些接口用于“claim-check ref + Query API”模式下的跨服务读取（编排/报告聚合使用）。

<a id="strict-5-1"></a>
### 5.1 Discovery Service Query API

- `GET /v1/results/{result_id}`
返回：

```json
{ "result_id": "sr_xxx", "data": { "results": [/* ... */] } }
```

<a id="strict-5-2"></a>
### 5.2 Discovery Service Min Fields（给 Nexus fan-out 用）

- `GET /v1/results/{result_id}/min_fields?limit=50`

返回（示意）：

```json
{
  "result_id": "sr_xxx",
  "items": [
    {
      "title": "Paper Title",
      "authors": ["A", "B"],
      "pdf_url": "https://...",
      "canonical_id": "W123",
      "doi": "10.1234/...",
      "publication_date": "2024-01-01"
    }
  ]
}
```

<a id="strict-5-3"></a>
### 5.3 Download Service APIs（download + files）

download_service 同时提供：
- **下载任务 API**（供上层或其它服务在“非 MQ 模式”下使用）：
  - `POST /download`：创建下载任务（异步，Celery）
  - `GET /download/{task_id}`：查询任务状态（成功时返回 `file_url`，或通过 `file_id` 进一步走 signed URL）
- **文件查询 API（ref-only / claim-check）**：
  - `GET /files/{file_id}/signed_url?expires=3600`：返回 presigned URL（file_id 必须是 UUID）

#### 5.3.1 创建下载任务
`POST /download`

请求：

```json
{ "url": "https://example.com/paper.pdf" }
```

响应：

```json
{ "task_id": "uuid", "status": "PENDING" }
```

#### 5.3.2 查询下载任务状态
`GET /download/{task_id}`

响应（示意）：

```json
{
  "task_id": "uuid",
  "status": "SUCCESS",
  "file_url": "https://...presigned...",
  "error_message": null,
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:01Z"
}
```

#### 5.3.3 获取文件 Signed URL（Query API）
`GET /files/{file_id}/signed_url?expires=3600`

返回：

```json
{ "file_id": "uuid", "url": "https://...presigned...", "expires_seconds": 3600 }
```

<a id="strict-5-4"></a>
### 5.4 Parser Service Parsed Query API

- `GET /v1/parsed/{doc_id}`
返回：

```json
{ "doc_id": "xxx", "data": { "doc_id": "xxx", "chunks": [/* ... */] } }
```

<a id="strict-5-5"></a>
### 5.5 Overview Service Report Query API

- `GET /v1/reports/{trace_id}`

返回（示意）：

```json
{
  "trace_id": "uuid",
  "data": {
    "overview_md": "## Background\n...",
    "meta": {"paper_count": 3, "domain": "AI", "style": "academic"}
  }
}
```

#### 5.5.1 Prompt 管理（系统 Prompt）
**Method & Path**
`GET /prompts`  
`GET /prompts/{prompt_key}`  
`PUT /prompts/{prompt_key}`

**描述**  
System prompt 存在 `tool_services/overview_service/prompts.json`，主要控制 `nexus_tool` worker 发送给 SiliconFlow 的第一条消息。调用上述接口可以在不重启 worker 的情况下读取或替换 prompt 模板（支持 Python 的 `{}` 占位符）及说明文字，更新会立即写回该 JSON 并影响下一次模型调用。

**GET /prompts**

```json
{
  "prompts": [
    {
      "key": "overview_markdown",
      "template": "You follow instructions precisely and output markdown only.",
      "description": "Used when generating domain survey reports."
    }
  ]
}
```

**GET /prompts/{prompt_key}**
返回指定 prompt，例如：

```json
{
  "key": "overview_markdown",
  "template": "You follow instructions precisely and output markdown only.",
  "description": "Used when generating domain survey reports."
}
```

**PUT /prompts/{prompt_key}**
请求体：

```json
{
  "template": "You are a meticulous researcher. Follow instructions and return Markdown only.",
  "description": "临时调整 Prompt 以强化格式约束。"
}
```

响应与 `GET /prompts/{prompt_key}` 相同，且 `tool_services/overview_service/prompts.json` 会在本地更新。

<a id="strict-5-6"></a>
### 5.6 Indexing Service Query APIs（给 Retrieval/Nexus 使用）

- `POST /search`
  - 请求体：见 `tool_services/indexing_service/app/schemas/api_models.py::SearchRequest`
  - 响应体：`{ "query": "...", "hits": [ { "doc": {...}, "chunk": {...}, "score": 0.0, "explain": {...} } ] }`

- `GET /kb/overview?limit=20&offset=0`
  - 响应体：`{ "docs_count": 0, "chunks_count": 0, "docs": [ { "doc_id": "...", "canonical_id": "...", "title": "...", "created_at_unix": 0 } ] }`

---

<a id="application-service"></a>
## 6. Application Service（用户服务与应用层）

Application Service 是面向用户的应用层服务，提供用户认证、订阅管理以及各类学术功能（学术日报、文献综述、文献检索、文献翻译）的 API 接口。

<a id="application-service-6-1"></a>
### 6.1 基本信息

- **默认监听**：`http://localhost:8005`
- **API 前缀**：`/api`
- **实现位置**：`application_service/main.py`
- **技术栈**：FastAPI + SQLAlchemy + PostgreSQL
- **OpenAPI 文档**：
  - `GET /docs`（Swagger UI）
  - `GET /openapi.json`（OpenAPI JSON）

**通用请求头**：
- `Content-Type: application/json`（有请求体时必填）
- `X-User-ID`（部分接口需要，用于标识当前用户）

**通用错误响应**（FastAPI 默认 `HTTPException`）：
```json
{
  "detail": "string"
}
```

<a id="application-service-6-2"></a>
### 6.2 认证 API

#### 1) 用户注册

**Method & Path**  
`POST /api/auth/register`

**描述**  
创建新用户账户。

**请求头**  
- `Content-Type: application/json`

**请求体（application/json）**

```json
{
  "username": "string",
  "email": "user@example.com",
  "password": "string"
}
```

字段说明：
- `username`（string，必填）：用户名，长度 3-50 个字符
- `email`（EmailStr，必填）：邮箱地址，必须唯一
- `password`（string，必填）：密码，长度至少 6 位，最多 1000 个字符

**响应**
- `201 Created`（application/json）

```json
{
  "id": 1,
  "username": "string",
  "email": "user@example.com"
}
```

- `400 Bad Request`（application/json）

```json
{
  "detail": "该用户名已被使用"
}
```

或

```json
{
  "detail": "该邮箱已被注册"
}
```

**请求示例（curl）**

```bash
curl -X POST http://localhost:8005/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123"
  }'
```

---

#### 2) 用户登录

**Method & Path**  
`POST /api/auth/login`

**描述**  
用户登录验证。

**请求头**  
- `Content-Type: application/json`

**请求体（application/json）**

```json
{
  "email": "user@example.com",
  "password": "string",
  "remember_me": false
}
```

字段说明：
- `email`（EmailStr，必填）：注册时使用的邮箱
- `password`（string，必填）：用户密码
- `remember_me`（bool，可选）：是否记住登录状态，默认 `false`

**响应**
- `200 OK`（application/json）

```json
{
  "id": 1,
  "username": "string",
  "email": "user@example.com"
}
```

- `401 Unauthorized`（application/json）

```json
{
  "detail": "邮箱或密码错误"
}
```

**请求示例（curl）**

```bash
curl -X POST http://localhost:8005/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123",
    "remember_me": true
  }'
```

---

<a id="application-service-6-3"></a>
### 6.3 订阅管理 API

订阅管理 API 用于管理用户的学术订阅（期刊、学者、关键词）。所有接口都需要在请求头中提供 `X-User-ID`。

#### 1) 创建订阅

**Method & Path**  
`POST /api/subscriptions`

**描述**  
为用户创建新的订阅。

**请求头**  
- `Content-Type: application/json`
- `X-User-ID`（必填）：用户 ID

**请求体（application/json）**

```json
{
  "subscription_type": "journal",
  "subscription_value": "Nature"
}
```

字段说明：
- `subscription_type`（enum，必填）：订阅类型，可选值：
  - `"journal"`：期刊订阅
  - `"scholar"`：学者订阅
  - `"keyword"`：关键词订阅
- `subscription_value`（string，必填）：订阅值，长度 1-100 个字符，不能为空

**响应**
- `201 Created`（application/json）

```json
{
  "id": 1,
  "user_id": 1,
  "subscription_type": "journal",
  "subscription_value": "Nature"
}
```

- `400 Bad Request`（application/json）

```json
{
  "detail": "该订阅已存在"
}
```

或

```json
{
  "detail": "订阅值不能为空"
}
```

- `401 Unauthorized`（application/json）

```json
{
  "detail": "未提供用户ID，请在请求头中添加 X-User-ID"
}
```

**请求示例（curl）**

```bash
curl -X POST http://localhost:8005/api/subscriptions \
  -H "Content-Type: application/json" \
  -H "X-User-ID: 1" \
  -d '{
    "subscription_type": "journal",
    "subscription_value": "Nature"
  }'
```

---

#### 2) 获取所有订阅

**Method & Path**  
`GET /api/subscriptions`

**描述**  
获取当前用户的所有订阅。

**请求头**  
- `X-User-ID`（必填）：用户 ID

**响应**
- `200 OK`（application/json）

```json
[
  {
    "id": 1,
    "user_id": 1,
    "subscription_type": "journal",
    "subscription_value": "Nature"
  },
  {
    "id": 2,
    "user_id": 1,
    "subscription_type": "keyword",
    "subscription_value": "machine learning"
  }
]
```

**请求示例（curl）**

```bash
curl http://localhost:8005/api/subscriptions \
  -H "X-User-ID: 1"
```

---

#### 3) 获取指定订阅

**Method & Path**  
`GET /api/subscriptions/{subscription_id}`

**描述**  
获取指定订阅的详细信息。

**路径参数**
- `subscription_id`（int，必填）：订阅 ID

**请求头**  
- `X-User-ID`（必填）：用户 ID

**响应**
- `200 OK`（application/json）

```json
{
  "id": 1,
  "user_id": 1,
  "subscription_type": "journal",
  "subscription_value": "Nature"
}
```

- `404 Not Found`（application/json）

```json
{
  "detail": "订阅不存在"
}
```

---

#### 4) 更新订阅

**Method & Path**  
`PUT /api/subscriptions/{subscription_id}`

**描述**  
更新指定订阅的信息。

**路径参数**
- `subscription_id`（int，必填）：订阅 ID

**请求头**  
- `Content-Type: application/json`
- `X-User-ID`（必填）：用户 ID

**请求体（application/json）**

```json
{
  "subscription_type": "keyword",
  "subscription_value": "deep learning"
}
```

**响应**
- `200 OK`（application/json）

```json
{
  "id": 1,
  "user_id": 1,
  "subscription_type": "keyword",
  "subscription_value": "deep learning"
}
```

- `404 Not Found`（application/json）

```json
{
  "detail": "订阅不存在"
}
```

---

#### 5) 删除订阅

**Method & Path**  
`DELETE /api/subscriptions/{subscription_id}`

**描述**  
删除指定订阅。

**路径参数**
- `subscription_id`（int，必填）：订阅 ID

**请求头**  
- `X-User-ID`（必填）：用户 ID

**响应**
- `204 No Content`（无响应体）

- `404 Not Found`（application/json）

```json
{
  "detail": "订阅不存在"
}
```

---

<a id="application-service-6-4"></a>
### 6.4 学术日报 API

学术日报 API 用于生成每日学术论文摘要报告，基于 Nexus Orchestration Service 的 `MORNING_REPORT` 任务类型。

#### 1) 提交学术日报任务

**Method & Path**  
`POST /api/morning-report`

**描述**  
提交学术日报生成任务，返回 `trace_id` 供后续查询使用。

**请求头**  
- `Content-Type: application/json`

**请求体（application/json）**

```json
{
  "query": "Large Language Models",
  "limit": 5,
  "filters": {
    "publication_year": "2024",
    "last_n_days": 30
  }
}
```

字段说明：
- `query`（string，必填）：检索关键词，默认 `"Large Language Models"`
- `limit`（int，可选）：期望返回的论文数量，默认 `5`
- `filters`（object，可选）：过滤条件，默认 `{"last_n_days": 30}`

**响应**
- `200 OK`（application/json）

```json
{
  "trace_id": "2f4a6df3-4f6e-4e05-8a54-3c01caa6a9b2",
  "status": "submitted",
  "message": "Job submitted successfully"
}
```

**请求示例（curl）**

```bash
curl -X POST http://localhost:8005/api/morning-report \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Large Language Models",
    "limit": 5,
    "filters": {
      "publication_year": "2024"
    }
  }'
```

---

#### 2) 获取学术日报结果

**Method & Path**  
`GET /api/morning-report/{trace_id}`

**描述**  
通过 `trace_id` 获取学术日报的生成结果。该接口会调用 Nexus Orchestration Service 的标准化报告 API，并将结果转换为前端期望的格式。

**路径参数**
- `trace_id`（string，必填）：任务追踪 ID

**响应**
- `200 OK`（application/json）

```json
{
  "trace_id": "2f4a6df3-4f6e-4e05-8a54-3c01caa6a9b2",
  "search_results": {
    "results": [
      {
        "title": "Paper Title",
        "authors": ["Author 1", "Author 2"],
        "pdf_url": "http://example.com/paper.pdf",
        "openalex_id": "W123",
        "doi": "10.1234/example",
        "publication_date": "2024-01-01",
        "llm_summary": "This is a summary of the paper..."
      }
    ]
  }
}
```

- `400 Bad Request`（application/json）

```json
{
  "detail": "任务尚未完成，请稍后再试"
}
```

- `404 Not Found`（application/json）

```json
{
  "detail": "任务 2f4a6df3-4f6e-4e05-8a54-3c01caa6a9b2 未找到"
}
```

**请求示例（curl）**

```bash
curl http://localhost:8005/api/morning-report/2f4a6df3-4f6e-4e05-8a54-3c01caa6a9b2
```

---

<a id="application-service-6-5"></a>
### 6.5 文献综述 API

文献综述 API 用于生成多篇论文的综合综述报告，基于 Nexus Orchestration Service 的 `SUMMARY_REPORT` 任务类型。

#### 创建文献综述

**Method & Path**  
`POST /api/literature-review`

**描述**  
提交文献综述生成任务。该接口会：
1. 提交 `SUMMARY_REPORT` 任务到 Nexus Orchestration Service
2. 等待任务完成（最长等待 10 分钟）
3. 获取标准化报告并返回

**请求头**  
- `Content-Type: application/json`

**请求体（application/json）**

```json
{
  "papers": [
    {
      "pdf_url": "https://example.com/paper1.pdf",
      "title": "Paper Title 1",
      "authors": ["Author 1", "Author 2"]
    },
    {
      "pdf_url": "https://example.com/paper2.pdf",
      "title": "Paper Title 2",
      "authors": ["Author 3"]
    }
  ],
  "domain": "machine_learning",
  "style": "academic"
}
```

字段说明：
- `papers`（array[object]，必填）：论文列表
  - `pdf_url`（string，必填）：论文 PDF 的 URL
  - `title`（string，可选）：论文标题，默认为空字符串
  - `authors`（array[string]，可选）：作者列表，默认为空数组
- `domain`（string，可选）：领域，如 `"machine_learning"`、`"medical"` 等
- `style`（string，可选）：风格，如 `"academic"`、`"concise"` 等

**响应**
- `200 OK`（application/json）

```json
{
  "trace_id": "2f4a6df3-4f6e-4e05-8a54-3c01caa6a9b2",
  "final_report": {
    "trace_id": "uuid",
    "task_type": "SUMMARY_REPORT",
    "overview_md": "# Summary\n\nThis is a summary.",
    "meta": {
      "model": "gpt-4",
      "paper_count": 2,
      "domain": "machine_learning",
      "style": "academic"
    },
    "paper_count": 2
  }
}
```

- `408 Request Timeout`（application/json）

```json
{
  "detail": "任务超时（超过 600 秒）"
}
```

- `500 Internal Server Error`（application/json）

```json
{
  "detail": "提交任务失败: ..."
}
```

**请求示例（curl）**

```bash
curl -X POST http://localhost:8005/api/literature-review \
  -H "Content-Type: application/json" \
  -d '{
    "papers": [
      {
        "pdf_url": "https://example.com/paper1.pdf",
        "title": "Paper Title 1",
        "authors": ["Author 1"]
      }
    ],
    "domain": "machine_learning",
    "style": "academic"
  }'
```

---

<a id="application-service-6-6"></a>
### 6.6 文献检索 API

文献检索 API 用于在本地知识库中进行语义检索和混合检索，调用 Indexing Service 的 `/search` API。

#### 文献检索

**Method & Path**  
`POST /api/literature-search`

**描述**  
执行文献检索，支持向量检索（语义检索）和关键词检索的混合模式。

**请求头**  
- `Content-Type: application/json`

**请求体（application/json）**

```json
{
  "query": "graph neural network",
  "k": 10,
  "kinds": ["paper"],
  "filters": {},
  "use_vector": true,
  "use_fts": true
}
```

字段说明：
- `query`（string，必填）：检索文本，长度至少 1 个字符
- `k`（int，可选）：返回 top-k 数量，默认 `10`，范围 1-50
- `kinds`（array[string]，可选）：按资源种类过滤，可选值：`"paper"` / `"dataset"` / `"code"`，为空则不过滤
- `filters`（object，可选）：过滤条件，默认 `{}`
- `use_vector`（bool，可选）：是否启用向量检索（语义检索），默认 `true`
- `use_fts`（bool，可选）：是否启用关键词检索并融合，默认 `true`

**响应**
- `200 OK`（application/json）

```json
{
  "query": "graph neural network",
  "hits": [
    {
      "doc": {
        "doc_id": "d1",
        "canonical_id": "W123",
        "doc_type": "paper",
        "title": "Paper Title"
      },
      "chunk": {
        "chunk_id": "c1",
        "doc_id": "d1",
        "text": "chunk text...",
        "page": 1,
        "paragraph": -1,
        "section_path": "Introduction"
      },
      "score": 0.85,
      "explain": {
        "rrf": 0.85,
        "vector": 0.90,
        "fts": 0.80
      }
    }
  ],
  "results": [
    {
      "doc_id": "d1",
      "canonical_id": "W123",
      "title": "Paper Title",
      "doc_type": "paper",
      "chunk_text": "chunk text...",
      "chunk_id": "c1",
      "page": 1,
      "paragraph": -1,
      "section_path": "Introduction",
      "score": 0.85,
      "explain": {
        "rrf": 0.85,
        "vector": 0.90,
        "fts": 0.80
      },
      "authors": [],
      "abstract": "chunk text...",
      "publication_date": null,
      "publication_year": null,
      "doi": null,
      "url": null
    }
  ],
  "total": 1
}
```

- `400 Bad Request`（application/json）

```json
{
  "detail": "请求参数错误"
}
```

- `502 Bad Gateway`（application/json）

```json
{
  "detail": "Indexing Service 错误: ..."
}
```

**请求示例（curl）**

```bash
curl -X POST http://localhost:8005/api/literature-search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "graph neural network",
    "k": 10,
    "kinds": ["paper"],
    "use_vector": true,
    "use_fts": true
  }'
```

---

<a id="application-service-6-7"></a>
### 6.7 文献翻译 API

文献翻译 API 用于翻译 PDF 论文文件，调用 Translator Service 的翻译接口。

#### 翻译论文文件

**Method & Path**  
`POST /api/translate-paper`

**描述**  
上传 PDF 论文文件并获取翻译结果。

**请求头**  
- `Content-Type: multipart/form-data`

**请求体（multipart/form-data）**

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `file` | file | 是 | 论文文件（.pdf） |
| `target_lang` | string | 否 | 目标语言代码（如 "zh"、"en"），默认为 "zh" |

**响应**
- `200 OK`（application/json）

```json
{
  "text_translated": "提取并翻译后的完整论文文本...",
  "meta": {
    "target_lang": "zh",
    "file_name": "paper.pdf",
    "model": "deepseek-ai/DeepSeek-V3"
  }
}
```

- `400 Bad Request`（application/json）

```json
{
  "error": "only PDF files are supported"
}
```

- `500 Internal Server Error`（application/json）

```json
{
  "error": "PDF parsing failed: ..."
}
```

- `504 Gateway Timeout`（application/json）

```json
{
  "error": "翻译服务超时，请稍后重试"
}
```

**请求示例（curl）**

```bash
curl -X POST http://localhost:8005/api/translate-paper \
  -F "file=@paper.pdf" \
  -F "target_lang=zh"
```

**请求示例（Python requests）**

```python
import requests

url = "http://localhost:8005/api/translate-paper"
files = {"file": open("paper.pdf", "rb")}
data = {"target_lang": "zh"}

response = requests.post(url, files=files, data=data)
result = response.json()
print(result["text_translated"])
```

---

#### 健康检查

**Method & Path**  
`GET /health`

**描述**  
检查服务健康状态。

**响应**
- `200 OK`（application/json）

```json
{
  "status": "healthy"
}
```

---

#### 根路径

**Method & Path**  
`GET /`

**描述**  
服务根路径，返回欢迎信息。

**响应**
- `200 OK`（application/json）

```json
{
  "message": "Welcome to ResearchGO API",
  "version": "1.0.0",
  "docs": "/docs"
}
```

