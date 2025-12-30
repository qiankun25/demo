# 微服务 API 测试指南

本文档介绍如何测试 `translator_service` 和 `retrieval_service` 的独立 API 接口。

## 1. Translator Service (多模态翻译)

该服务运行在 `8002` 端口，支持纯文本翻译以及带有图片的多模态翻译。

### 启动服务
```bash
cd tool_services/translator_service
python3 main.py
```

### 测试接口：`POST /translate`

#### A. 纯文本翻译
**请求体 (JSON):**
```json
{
  "text": "The rapid development of large language models has revolutionized natural language processing.",
  "target_lang": "zh"
}
```

**响应体示例 (JSON):**
```json
{
  "text_translated": "大语言模型的快速发展彻底改变了自然语言处理。",
  "images_translated": [],
  "meta": {
    "target_lang": "zh",
    "image_count": 0,
    "model": "deepseek-ai/DeepSeek-V3"
  }
}
```

#### B. 多模态翻译 (带图片)
**请求体 (JSON):**
```json
{
  "text": "Translate the following and describe the image.",
  "images": ["/path/to/your/image.png"],
  "target_lang": "zh"
}
```

**响应体示例 (JSON):**
```json
{
  "text_translated": "翻译以下内容并描述图片。",
  "images_translated": [
    {
      "input": "/path/to/your/image.png",
      "caption": "这张图片展示了一个正在运行的服务器集群。",
      "extracted_text": "Server Status: OK",
      "translated_text": "服务器状态：正常"
    }
  ],
  "meta": {
    "target_lang": "zh",
    "image_count": 1,
    "model": "deepseek-ai/DeepSeek-V3"
  }
}
```

---

## 2. Retrieval Service (检索编排)

该服务运行在 `8003` 端口。我们推荐使用 `search_simple` 接口进行快速测试，因为它直接扫描存储产物，不依赖复杂的索引链路。

### 启动服务
```bash
cd tool_services/retrieval_service
python3 main.py
```


### 其他可用接口
*   `GET /health`: 检查服务状态。
*   `GET /kb/overview`: 查看本地知识库概览（依赖 `indexing_service`）。
*   `GET /status/{doc_key}`: 查看特定文档的处理状态。

### 新增：语义检索接口（直连 MQ Indexer 落地的 Chroma + SQLite）

该接口用于“打通 MQ IndexerToolService 与 Retrieval HTTP 编排服务”：
- IndexerToolService 在索引时会把 **chunks 写入 SQLite(index.db)**、把 **向量写入 Chroma(persist dir)**。
- Retrieval Service 通过本接口 **直接读取同一份 index.db + chroma_data** 来完成语义检索：
  1) 先在 Chroma 中做向量检索命中 chunk
  2) 再用命中的 `chunk_id/doc_id` 去 SQLite 取 **完整论文元数据（docs）** 和 **完整 chunk 文本（chunks.text）**

> 注意：这是“本地文件直连”方式；若用 Docker 部署，需要将 `index.db` 与 `chroma_data/` 通过 volume 共享给 retrieval_service。

#### 启动前关键配置（默认无需设置）
- `RETRIEVAL_INDEX_DB_PATH`（或 `INDEX_DB_PATH`）：indexing 的 SQLite 路径  
  默认：`tool_services/indexing_service/index.db`
- `RETRIEVAL_CHROMA_PERSIST_DIR`（或 `INDEX_CHROMA_PERSIST_DIR`）：Chroma 持久化目录  
  默认：`tool_services/indexing_service/chroma_data`
- `RETRIEVAL_CHROMA_COLLECTION`（或 `INDEX_CHROMA_COLLECTION`）：collection 名称（需与 Indexer 一致）  
  默认：`paper_chunks`
- `RETRIEVAL_EMBED_DIM`（或 `INDEX_EMBED_DIM`）：embedding 维度（需与 Indexer 一致）  
  默认：`256`

#### 测试接口：`POST /semantic_search`

**请求体 (JSON):**
```json
{
  "query": "Graph Neural Networks",
  "k": 5,
  "min_score": 0.0
}
```

**Curl 示例:**
```bash
curl -X POST http://localhost:8003/semantic_search \
     -H "Content-Type: application/json" \
     -d '{"query": "Graph Neural Networks", "k": 5, "min_score": 0.0}'
```

**响应体说明：**
- `hits[].paper`：更“业务友好”的论文信息（title/authors/year/canonical_id/pdf_sha256/pdf_object_key/extra 等），由 SQLite `docs` 解析得到
- `hits[].doc`：来自 SQLite `docs` 的完整论文元数据（按列返回）
- `hits[].chunk_text` / `hits[].chunk`：来自 SQLite `chunks` 的完整 chunk 文本与字段
- `hits[].vector_meta`：来自 Chroma 的元数据（索引时写入）

**响应体示例 (JSON):**
```json
{
  "query": "Graph Neural Networks",
  "k": 5,
  "hits": [
    {
      "score": 0.42,
      "chunk_id": "abc123:0",
      "doc_id": "abc123",
      "paper": {
        "doc_id": "abc123",
        "canonical_id": "https://openalex.org/W1234567890",
        "doc_type": "paper",
        "title": "Graph Neural Networks: A Review",
        "authors": ["Alice", "Bob"],
        "year": 2024,
        "venue": null,
        "source": "openalex",
        "license": null,
        "open_access": true,
        "pdf_object_key": "/tmp/xxxx_paper.pdf",
        "pdf_sha256": "9f2c...e8",
        "extra": {
          "pdf_url": "https://arxiv.org/pdf/1234.5678.pdf",
          "doi": "10.1234/xxxx",
          "publication_date": "2024-06-01",
          "openalex_id": "https://openalex.org/W1234567890"
        }
      },
      "chunk_text": "…这里是命中的 chunk 全文…",
      "chunk": {
        "chunk_id": "abc123:0",
        "doc_id": "abc123",
        "text": "…这里是命中的 chunk 全文…",
        "page": null,
        "paragraph": null,
        "section_path": "auto/section"
      },
      "doc": {
        "doc_id": "abc123",
        "canonical_id": "https://openalex.org/W1234567890",
        "doc_type": "paper",
        "title": "Graph Neural Networks: A Review",
        "authors_json": "[\"Alice\",\"Bob\"]",
        "year": 2024,
        "venue": null,
        "source": "openalex",
        "license": null,
        "open_access": 1,
        "pdf_object_key": "/tmp/xxxx_paper.pdf",
        "pdf_sha256": "9f2c...e8",
        "extra_json": "{\"pdf_url\":\"https://arxiv.org/pdf/1234.5678.pdf\"}",
        "created_at_unix": 1730000000
      },
      "vector_meta": {
        "doc_id": "abc123",
        "canonical_id": "https://openalex.org/W1234567890",
        "doc_type": "paper",
        "title": "Graph Neural Networks: A Review",
        "page": -1,
        "paragraph": -1,
        "section_path": "auto/section",
        "fulltext_hash": "9f2c...e8",
        "pdf_sha256": "9f2c...e8",
        "pdf_object_key": "/tmp/xxxx_paper.pdf"
      }
    }
  ],
  "meta": {
    "index_db_path": "tool_services/indexing_service/index.db",
    "chroma_persist_dir": "tool_services/indexing_service/chroma_data",
    "chroma_collection": "paper_chunks",
    "chroma_distance": "cosine",
    "embed_dim": 256
  }
}
```


---

## 注意事项
1. **API Key**: 服务已内置 SiliconFlow API Key，无需额外配置环境变量。
2. **依赖**: 请确保已安装 `requirements.txt` 中的依赖（`fastapi`, `uvicorn`, `httpx` 等）。
3. **跨域**: 服务已开启 CORS 允许所有来源，支持前端直接调用。

