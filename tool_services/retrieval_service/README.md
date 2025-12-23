# retrieval_service（统一检索编排层 + 事件驱动入库）

实现你提出的：
- **3**：把“发现服务”拆成检索编排层（本服务）+ 数据源连接器（`mic_find_url/external_clients.py`）
- **5**：本地优先，外部补充；外部命中异步入库
- **4（接入版）**：事件驱动状态机（SQLite 持久化）

## 对外接口

### POST `/search`
先查本地（`indexing_service`），再依据“**高相似度本地命中数量**”决定是否外部补充（`mic_find_url`），并对外部候选（paper/dataset/code）自动 enqueue 入库事件。

外部补充触发条件：
- 仅当本地命中里 **`score >= RETRIEVAL_MIN_LOCAL_SCORE`** 的条目数量不足（小于 `max(RETRIEVAL_MIN_LOCAL_HITS, k)`）时，才会去外部补充。

返回规则：
- `local_hits` 只返回满足 `score >= RETRIEVAL_MIN_LOCAL_SCORE` 的本地命中（低于阈值的不返回）。

请求：
```json
{
  "query": "attention is all you need",
  "k": 10,
  "kinds": ["paper"], 
  "filters": {},
  "sources": ["arxiv"]
}
```

响应：
- `local_hits`：来自本地索引
- `external_hits`：来自外部检索
- `merged_hits`：融合结果（当前策略：本地优先 + 简单去重）
- `ingest_enqueued`：本次新入库事件数量

### GET `/status/{doc_key}`
查看某个文档的状态机状态：
`DISCOVERED -> DOWNLOADED -> PARSED -> INDEXED`（失败为 `FAILED`）。

### GET `/kb/overview`
获取当前本地知识库概览（论文数量、chunk 数、论文 title 列表等）。内部调用 `indexing_service /kb/overview`。

## 事件/状态机
事件类型示例：
- `PaperDiscovered`
- `DatasetDiscovered`
- `CodeDiscovered`
- `PdfDownloaded`
- `PdfParsed`
- `Indexed`

## 启动
```bash
cd retrieval_service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export RETRIEVAL_DISCOVERY_BASE_URL="http://localhost:8000"
export RETRIEVAL_DOWNLOAD_BASE_URL="http://localhost:8001"
export RETRIEVAL_PARSER_BASE_URL="http://localhost:3000"
export RETRIEVAL_INDEXING_BASE_URL="http://localhost:8020"
export RETRIEVAL_KAGGLE_USERNAME=""
export RETRIEVAL_KAGGLE_KEY=""
export RETRIEVAL_GITHUB_TOKEN=""
export RETRIEVAL_MIN_LOCAL_SCORE="0.01"

uvicorn main:app --reload --host 0.0.0.0 --port 8030
```

## 快速测试
```bash
curl -X POST http://localhost:8030/search \
  -H "Content-Type: application/json" \
  -d '{"query":"attention is all you need","k":5,"sources":["arxiv"]}'

curl "http://localhost:8030/kb/overview?limit=20&offset=0"
```

