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

### 测试接口：`POST /search_simple`


**请求体 (JSON):**
```json
{
  "query": "Machine Learning",
  "top_k": 5
}
```

**Curl 示例:**
```bash
curl -X POST http://localhost:8003/search_simple \
     -H "Content-Type: application/json" \
     -d '{"query": "Machine Learning", "top_k": 5}'
```

**响应体示例 (JSON):**
```json
{
  "query": "Machine Learning",
  "hits": [
    {
      "chunk_id": "doc_123:0",
      "doc_id": "doc_123",
      "text": "Machine learning is a subset of artificial intelligence...",
      "score": 0.8,
      "source": "local_simple"
    }
  ]
}
```

### 其他可用接口
*   `GET /health`: 检查服务状态。
*   `GET /kb/overview`: 查看本地知识库概览（依赖 `indexing_service`）。
*   `GET /status/{doc_key}`: 查看特定文档的处理状态。

---

## 注意事项
1. **API Key**: 服务已内置 SiliconFlow API Key，无需额外配置环境变量。
2. **依赖**: 请确保已安装 `requirements.txt` 中的依赖（`fastapi`, `uvicorn`, `httpx` 等）。
3. **跨域**: 服务已开启 CORS 允许所有来源，支持前端直接调用。

