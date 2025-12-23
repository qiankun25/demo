### tool_services 微服务写入 MinIO 的内容总结

>
> - **Claim Check 存储（通过 `MockStorage`）**：消息里只传 `key`，实际 payload 以对象的形式写入 MinIO。
> - **文件对象存储（download_service 自己的 MinIO 客户端 `MinIOStorage`）**：把 PDF 二进制文件真正上传到 MinIO。

---

### 1) Claim Check（`MockStorage`）在 MinIO 中的落盘规则

- **对象位置**
  - **bucket**：`MINIO_BUCKET`（默认 `papers`）
  - **前缀**：`NEXUS_STORAGE_PREFIX`（默认 `claimcheck/`）
  - **对象名**：`{NEXUS_STORAGE_PREFIX}{storage_key}`
    - 例如 `storage_key = data:parse:task-123` → 对象名 `claimcheck/data:parse:task-123`

- **对象内容（value）编码**
  - 优先 **JSON**（绝大多数 dict/list/str/int）
  - JSON 不可序列化时回退到 **pickle**
  - `bytes` 则按 raw bytes 保存
  - 文件内部带 `NEXUS_CLAIMCHECK_V1` + `encoding:...` 的头用于解码

---

### 2) 各微服务（nexus_tool）写入 MinIO 的内容

以下服务都通过 `from nexus_sdk.common import MockStorage` 写入（也就是写入上面 “Claim Check” 这套 bucket/prefix）。

#### MORNING_REPORT（编排层最终产物，`nexus_service/core.py`）

- **写入 key**
  - `data:morning_report:{trace_id}`
- **写入内容（JSON）**
  - `trace_id`
  - `requested_limit`
  - `paper_count`
  - `papers[]`：每篇论文一个对象，包含：
    - `paper`：`title/authors/pdf_url/openalex_id/doi/publication_date/original_url`
    - `summary`：`llm_summary`
    - `index`：`collection/vector_count/persist_dir`
    - `keys`：该论文链路各阶段 key（work_key/download_key/parse_key/index_key）
  - `input`：`query/filters`

#### discovery_service（`tool_services/discovery_service/nexus_tool/tool_service.py`）

- **写入 key**
  - `data:discovery:{input_key}`
- **写入内容（JSON）**
  - `query`：检索词
  - `filters`：OpenAlex filter
  - `request_url`：实际请求 URL
  - `meta`：OpenAlex meta（如果有）
  - `results`：截断后的结果列表（最多 `limit` 条）

#### download_service（nexus_tool 版本，`tool_services/download_service/nexus_tool/tool_service.py`）

> 注意：这是“消息链路 demo 用的 downloader tool”。它 **不会把 PDF 文件本体上传到 MinIO**，只会在本机 `/tmp` 落文件，然后把路径写入 MinIO（Claim Check）。

- **写入 key**
  - `data:download:{input_key}`
- **写入内容（JSON）**
  - `file_path`：本机临时目录文件路径（例如 `/tmp/<uuid>_paper.pdf`）
  - `filename`：文件名
  - `size_bytes`：文件大小（字节）
  - `source_url`：来源 URL
  - `content_type`：`application/pdf`

#### paper_analyse（parser，`tool_services/paper_analyse/nexus_tool/tool_service.py`）

- **写入 key**
  - `data:parse:{input_key}`
- **写入内容（JSON）**
  - `doc_id`：由全文 hash 截断得到的 id
  - `title`：默认用 filename
  - `chunks`：分块数组，每个 chunk 包含：
    - `chunk_id`
    - `text`
    - `page`（当前实现为 `None`）
    - `hash`（chunk 的 sha256）
  - `fulltext_hash`：全文 sha256
  - `llm_summary`：SiliconFlow 总述（若未配 key 则为空字符串）
  - `meta`：`source_url / filename / size_bytes / content_type`

#### indexing_service（`tool_services/indexing_service/nexus_tool/tool_service.py`）

> 注意：这里的向量是“简化版 hash embedding”，**向量本身并不写入 MinIO**；MinIO 只保存索引结果的统计信息。

- **写入 key**
  - `data:index:{input_key}`
- **写入内容（JSON）**
  - `doc_id`
  - `chunk_count`
  - `vector_count`
  - `collection`：固定为 `"default"`

#### retrieval_service（`tool_services/retrieval_service/nexus_tool/tool_service.py`）

- **写入 key**
  - `data:retrieval:{input_key}`
- **写入内容（JSON）**
  - `query`
  - `local_hits`：本地命中（从 `data:parse:*` 的 chunks 做关键词重叠打分）
  - `external_hits`：OpenAlex 补全命中（可选）
  - `combined`：合并后 top_k
- **额外说明**
  - 本地检索会在 MinIO（Claim Check）里 **list** `data:parse:` 前缀的对象并逐个读取（受 `RETRIEVAL_LOCAL_SCAN_LIMIT` 限制，默认 50）。

#### translator_service（`tool_services/translator_service/nexus_tool/tool_service.py`）

- **写入 key**
  - `data:translate:{input_key}`
- **写入内容（JSON）**
  - `text_translated`：示例翻译（字符串前缀加 `[lang]`）
  - `images_translated`：图片翻译占位描述数组：`[{path, text}]`
  - `meta`：`target_lang / image_count`

---

### 3) 其他：`tool_services/impl/tools.py`（旧版 demo stub）

这一套是 `run_demo.py` 里用的简化实现，也走 `shared.common.MockStorage`（同样会写入 Claim Check 的 MinIO）：

- DownloaderService 写入：`data:download:{input_key}`
  - 内容示例：`{"file_path":"/minio/bucket/paper_001.pdf","size":"2MB"}`（占位值）
- ParserService 写入：`data:parse:{input_key}`
  - 内容示例：`{"content":"...","keywords":[...]}`
- IndexerService：当前实现 **不写入 MockStorage/MinIO**（直接返回 `"db_record_id_999"`）

---

### 4) download_service（FastAPI + Celery）对 MinIO 的“真实文件上传”

`tool_services/download_service/app/tasks/download_task.py` 里，Celery 任务会把 PDF 二进制内容上传到 MinIO：

- **上传对象名规则**
  - `object_name = "{task_id}/{filename}"`
- **对象内容**
  - 真实 PDF 文件 bytes（`content_type = application/pdf`）
- **配套元数据（不在 MinIO，而在数据库）**
  - `DocumentFile` 记录：`minio_bucket / minio_object / file_size / mime_type`
  - `DownloadTask` 记录：`file_id` 指向 `DocumentFile`

