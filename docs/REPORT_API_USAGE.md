# 统一报告 API 使用指南

## 概述

Nexus 提供统一报告 API (`GET /api/v1/jobs/{trace_id}/report`)，自动聚合任务的所有 artifacts 并返回标准化格式的报告。

## 快速开始

### 1. 提交任务

```bash
POST /api/v1/jobs
Content-Type: application/json

{
  "task_type": "MORNING_REPORT",
  "parameters": {
    "limit": 5,
    "query": "large language model",
    "filters": {"publication_year": "2024"}
  }
}
```

响应：
```json
{
  "trace_id": "uuid",
  "status": "submitted",
  "message": "Job submitted successfully"
}
```

### 2. 轮询任务状态

```bash
GET /api/v1/jobs/{trace_id}
```

响应：
```json
{
  "trace_id": "uuid",
  "status": "completed",
  "completed_count": 5,
  "total_work_items": 5
}
```

### 3. 获取标准化报告

```bash
GET /api/v1/jobs/{trace_id}/report
```

## API 端点

### GET /api/v1/jobs/{trace_id}/report

获取已完成任务的标准化报告。

**路径参数：**
- `trace_id` (string, 必填): 任务追踪 ID

**响应：**

**MORNING_REPORT 响应示例：**
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
        "doi": "10.1234/example"
      },
      "summary": {
        "llm_summary": "This is a summary..."
      },
      "index": {
        "collection": "default",
        "vector_count": 10
      }
    }
  ],
  "failure_count": 0,
  "failures": [],
  "input": {
    "query": "large language model",
    "filters": {"publication_year": "2024"}
  }
}
```

**SUMMARY_REPORT 响应示例：**
```json
{
  "trace_id": "uuid",
  "task_type": "SUMMARY_REPORT",
  "overview_md": "# Summary\n\nThis is a summary...",
  "meta": {
    "model": "gpt-4",
    "paper_count": 3,
    "domain": "AI",
    "style": "academic"
  },
  "paper_count": 3
}
```

**错误响应：**

- `400 Bad Request`: 任务尚未完成
  ```json
  {"detail": "Job {trace_id} is not completed yet (current stage: processing)"}
  ```

- `404 Not Found`: 任务不存在
  ```json
  {"detail": "Job {trace_id} not found"}
  ```

## Python 示例

```python
import requests
import time

NEXUS_URL = "http://localhost:8000/api/v1"

# 1. 提交任务
response = requests.post(
    f"{NEXUS_URL}/jobs",
    json={
        "task_type": "MORNING_REPORT",
        "parameters": {
            "limit": 5,
            "query": "large language model"
        }
    }
)
trace_id = response.json()["trace_id"]

# 2. 等待任务完成
while True:
    status = requests.get(f"{NEXUS_URL}/jobs/{trace_id}").json()
    if status["status"] == "completed":
        break
    time.sleep(5)

# 3. 获取报告
report = requests.get(f"{NEXUS_URL}/jobs/{trace_id}/report").json()
print(f"Papers: {report['paper_count']}")
for paper in report["papers"]:
    print(f"- {paper['paper']['title']}")
```

## 优势

- **简单易用**：一次 API 调用获取完整报告
- **统一格式**：无需了解底层工具服务数据格式
- **向后兼容**：保留 `/artifacts/{artifact_key}` API 用于高级场景



