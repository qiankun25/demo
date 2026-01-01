# retrieval_service

只说明两件事：
- 如何启动该微服务
- 如何调用 `/semantic_search`

### 启动

在仓库根目录执行：

```bash
cd tool_services/retrieval_service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 仅 /semantic_search 必需：指向 indexing_service
export RETRIEVAL_INDEXING_BASE_URL="http://localhost:8020"

# 可选：HTTP 超时（默认 30s）
export RETRIEVAL_HTTP_TIMEOUT="30"

uvicorn main:app --host 0.0.0.0 --port 8003 --reload
```

### 调用 `/semantic_search`

说明：
- `/semantic_search` **内部统一调用** `indexing_service /search` 获取向量命中，本服务不再直连 Chroma/index.db（更适合多实例部署的读一致性）。
- 返回结构保持不变：`{query, k, hits, meta}`，其中 `hits[*]` 包含 `score/chunk_id/doc_id/paper/chunk_text/chunk/doc/vector_meta` 等字段。

请求示例：

```bash
curl -X POST "http://localhost:8003/semantic_search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "GNN",
    "k": 5,
    "min_score": 0.0
  }'
```

