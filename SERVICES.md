# 微服务接口一览

本文件汇总已适配 RabbitMQ 调度的工具服务：监听的 Routing Key、事件返回、期望输入/输出的 Storage Key 结构，便于编排与联调。MQ 协议和基础模型见 `shared/common.py` / `nexus_sdk/common.py`。

## 总览

- 指令交换机：`nexus.cmd.exchange` (direct)  
- 事件交换机：`nexus.evt.exchange` (topic)  
- 队列命名：`q.tool.<service>`  
- 路由表：见 `SERVICE_ROUTING`（`shared/common.py` / `nexus_sdk/common.py`）
- Claim Check：只在消息里传 key，业务数据写 Storage（当前为 MockStorage，可替换 Redis/MinIO）

## 服务清单

### Discovery Service (OpenAlex)
- `cmd.discovery.start` → `evt.discovery.finished|failed`
- 输入 key 内容：
  ```json
  {"query": "large language model", "filters": {"publication_year": "2023"}, "limit": 20, "sample": null, "seed": null}
  ```
- 输出 key：`data:discovery:{input_key}`  
  内容：`{query, filters, request_url, meta, results}`（results 已按 limit 截断）

### Download Service
- `cmd.downloader.start` → `evt.downloader.finished|failed`
- 输入 key 内容：
  ```json
  {"urls": ["https://.../paper.pdf"], "timeout": 30}
  ```
- 输出 key：`data:download:{input_key}`  
  内容：`{file_path, filename, size_bytes, source_url, content_type}`

### Parser Analyse Service
- `cmd.parser.start` → `evt.parser.finished|failed`
- 输入 key：上一步下载产物 `data:download:*`
- 输出 key：`data:parse:{input_key}`  
  内容示例：
  ```json
  {"doc_id": "sha256..", "title": "paper.pdf", "chunks": [{"chunk_id": "...", "text": "...", "page": 1, "section_path": "auto/section"}], "meta": {...}}
  ```

### Indexing Service
- `cmd.indexer.start` → `evt.indexer.finished|failed`
- 输入 key：`data:parse:*`
- 输出 key：`data:index:{input_key}`  
  内容：`{doc_id, chunk_count, vector_count, collection}`

### Retrieval Service
- `cmd.retrieval.start` → `evt.retrieval.finished|failed`
- 输入 key 内容：
  ```json
  {"query": "LLM safety", "top_k": 5, "min_local": 2, "use_external": true, "external_limit": 5}
  ```
- 输出 key：`data:retrieval:{input_key}`  
  内容：`{query, local_hits, external_hits, combined}` （本地先查 MockStorage 中的解析产物，命中不足再补 OpenAlex）

### Translator Service
- `cmd.translator.start` → `evt.translator.finished|failed`
- 输入 key 内容：
  ```json
  {"text": "原文", "images": ["/tmp/a.png"], "target_lang": "en"}
  ```
- 输出 key：`data:translate:{input_key}`  
  内容：`{text_translated, images_translated, meta}`

## 运行

- 启动全部服务（含 Nexus）：`python run_services.py`  
- Nexus 当前演示 DAG：downloader → parser → indexer（可根据业务扩展）

## 备注

- 外部发现与补全使用 OpenAlex 公网 API（无认证，1 rps 默认；生产建议添加 `mailto=` 参数）。  
- 当前解析/索引/翻译实现为轻量示例，便于消息流联调；可替换为实际业务逻辑（HTTP 调用、模型推理、MinIO 持久化等）。 
