# API 文档（汇总）

本文档汇总以下服务的 HTTP API：
- Nexus Orchestration Service（来自 [routes.py](file:///d:/05_python/demo/nexus/app/api/routes.py)）
- Translator Service（来自 [API_TEST_GUIDE.md](file:///d:/05_python/demo/API_TEST_GUIDE.md) 与实现 [main.py](file:///d:/05_python/demo/tool_services/translator_service/main.py)）
- Retrieval Service（来自 [API_TEST_GUIDE.md](file:///d:/05_python/demo/API_TEST_GUIDE.md) 与实现 [main.py](file:///d:/05_python/demo/tool_services/retrieval_service/main.py)）

---

## 1. Nexus Orchestration Service

### 1.1 基本信息
- 默认监听：`http://localhost:8000`
- API 前缀：`/api/v1`（见 [config.py](file:///d:/05_python/demo/nexus/app/core/config.py#L111-L123)）
- OpenAPI：
  - `GET /api/v1/openapi.json`
  - `GET /api/v1/docs`
  - `GET /api/v1/redoc`

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

字段说明（见 [api_models.py](file:///d:/05_python/demo/nexus/app/models/api_models.py#L7-L11)）：
- `task_type`：任务类型（字符串）
- `parameters`：任务参数（任意键值对，默认 `{}`）

#### JobSubmitResponse

```json
{
  "trace_id": "string",
  "status": "submitted",
  "message": "Job submitted successfully"
}
```

字段说明（见 [api_models.py](file:///d:/05_python/demo/nexus/app/models/api_models.py#L13-L18)）：
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

字段说明（见 [api_models.py](file:///d:/05_python/demo/nexus/app/models/api_models.py#L28-L38)）：
- `status`：当前状态（由编排器填充，见 [status_service.py](file:///d:/05_python/demo/nexus/app/services/status_service.py#L20-L33)）
- `artifacts`：制品 key 到下载 URL 的映射（URL 形如 `/api/v1/jobs/{trace_id}/artifacts/{artifact_key}`）
- `failures`：失败明细列表（字典数组）

---

### 1.3 API 列表

#### 文档约定
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
提交一个任务到编排器执行（见 [routes.py](file:///d:/05_python/demo/nexus/app/api/routes.py#L21-L41) 与 [job_service.py](file:///d:/05_python/demo/nexus/app/services/job_service.py#L8-L18)）。

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
返回任务状态、进度统计、制品下载 URL（见 [routes.py](file:///d:/05_python/demo/nexus/app/api/routes.py#L43-L57) 与 [status_service.py](file:///d:/05_python/demo/nexus/app/services/status_service.py#L9-L33)）。

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
    "manifest": "/api/v1/jobs/2f4a6df3-4f6e-4e05-8a54-3c01caa6a9b2/artifacts/manifest"
  },
  "failures": []
}
```

说明：
- `artifacts` 的结构是 `{artifact_key: download_url}`。
- `download_url` 是可直接请求的地址；不要把它 URL-encode 后再塞进 `{artifact_key}`。

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

**MORNING_REPORT 响应格式**（见 [report_models.py](file:///d:/05_python/demo/nexus/app/models/report_models.py)）：

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

#### 4) 获取任务制品（流式下载/透传）
**Method & Path**  
`GET /api/v1/jobs/{trace_id}/artifacts/{artifact_key}`

**描述**  
从存储读取对象流并透传返回（见 [routes.py](file:///d:/05_python/demo/nexus/app/api/routes.py#L59-L85) 与 [status_service.py](file:///d:/05_python/demo/nexus/app/services/status_service.py#L35-L50)）。  
**注意**：此 API 返回原始工具服务数据格式，适合调试和特殊需求场景。常规使用建议使用 `GET /api/v1/jobs/{trace_id}/report` 获取标准化报告。

**描述**  
从存储读取对象流并透传返回（见 [routes.py](file:///d:/05_python/demo/nexus/app/api/routes.py#L59-L85) 与 [status_service.py](file:///d:/05_python/demo/nexus/app/services/status_service.py#L35-L50)）。

**路径参数**
- `trace_id`（string，必填）：任务追踪 ID
- `artifact_key`（string，必填）：制品 key（来自 `GET /api/v1/jobs/{trace_id}` 的 `artifacts` 映射键）

**响应**
- `200 OK`（stream）  
  - `Content-Type` 由存储对象元信息决定（见 [storage.py](file:///d:/05_python/demo/nexus/app/infrastructure/storage.py#L80-L118)）
  - Body 为制品原始字节流（可能是 JSON / 二进制 / 其他）

示例（制品为 JSON 时的响应体示例）：

```json
{
  "example": "artifact payload"
}
```

- `404 Not Found`（application/json）

```json
{
  "detail": "Artifact manifest not found in job 2f4a6df3-4f6e-4e05-8a54-3c01caa6a9b2"
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
curl -L http://localhost:8000/api/v1/jobs/2f4a6df3-4f6e-4e05-8a54-3c01caa6a9b2/artifacts/manifest -o manifest.json
```

---

#### 5) 健康检查
**Method & Path**  
`GET /api/v1/health`

**描述**  
检查消息队列与存储是否健康（见 [routes.py](file:///d:/05_python/demo/nexus/app/api/routes.py#L88-L104)）。

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
检查是否可以接入流量（当前仅检查 MQ）（见 [routes.py](file:///d:/05_python/demo/nexus/app/api/routes.py#L106-L116)）。

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

## 2. Translator Service（多模态翻译）

### 2.1 基本信息
- 默认监听：`http://localhost:8002`

### 2.2 API

#### 1) 健康检查
**Method & Path**  
`GET /health`

**响应**
- `200 OK`（application/json）

```json
{"status":"ok"}
```

#### 2) 翻译（文本 / 多模态）
**Method & Path**  
`POST /translate`

**请求头**  
- `Content-Type: application/json`

**请求体（application/json）**（见 [translator main.py](file:///d:/05_python/demo/tool_services/translator_service/main.py#L22-L26)）

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

## 3. Indexing Service（索引 / 语义检索）

### 3.1 基本信息
- 默认监听：`http://localhost:8020`

### 3.2 API

#### 1) 语义检索 / 混合检索
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

