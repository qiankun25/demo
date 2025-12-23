# Indexing Service

独立索引服务（与解析服务解耦）：
- 输入：`doc` + `chunks[]`（来自 `mico_pdf2json-main /api/convert`）
- 输出：入库结果；并提供检索接口

## 技术栈
- FastAPI
- SQLite（元数据/倒排；包含 FTS5 时启用关键词检索）
- Chroma（向量库，持久化 collection）
- 向量化：默认 **hashing embedding**（无需模型/网络，便于本地跑通；后续可替换为真实 embedding 模型）

## 启动
```bash
cd indexing_service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export INDEX_DB_PATH="index.db"
export INDEX_EMBED_DIM=256
export INDEX_CHROMA_PERSIST_DIR="chroma_data"
export INDEX_CHROMA_COLLECTION="paper_chunks"

uvicorn main:app --reload --host 0.0.0.0 --port 8020
```

## 接口

### POST `/index`
请求体（与解析服务输出字段一致）：
```json
{
  "doc": { "doc_id": "...", "pdf_sha256": "...", "canonical_id": "arxiv:1706.03762", "doc_type": "paper", "extra": {} },
  "chunks": [
    { "chunk_id": "...", "doc_id": "...", "text": "...", "span": { "paragraph": 1 }, "section_path": "3 Method" }
  ],
  "summary_keywords": { "summary": "...", "keywords": ["..."] }
}
```
说明：
- `doc_type`：`paper/dataset/code`；非 paper 允许不传 `pdf_sha256`，服务端会按 chunks 计算一个内容哈希用于幂等。

### POST `/search`
```json
{ "query": "transformer attention", "k": 10, "kinds": ["paper"], "filters": {}, "use_vector": true, "use_fts": true }
```

返回 `hits[]`（含 doc + chunk + score + explain）。

### GET `/kb/overview`
```bash
curl "http://localhost:8020/kb/overview?limit=20&offset=0"
```

返回：
- `docs_count`：论文数量
- `chunks_count`：chunk 数量
- `docs[]`：论文列表（含 `title` 等）


