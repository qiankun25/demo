# Translator Service

A production-ready microservice for academic translation, supporting text, image, and PDF translation with glossary management, quality assessment, and async job processing.

## Architecture

- **Go Core Service**: High-performance translation engine with REST API
- **Python Adapter**: Compatibility layer for Nexus SDK integration
- **PostgreSQL**: Database for jobs, glossaries, and metadata
- **Redis**: Caching and job queue
- **MinIO**: Object storage for images and results

## Features

- Text translation with LaTeX/citation preservation
- Image translation with OCR and structured output
- Glossary management (project/tenant-level)
- Quality assessment
- Async job processing
- Caching for performance

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Go 1.21+ (for local development)
- Python 3.11+ (for adapter)

### Environment Variables

Create a `.env` file:

```bash
SILICONFLOW_API_KEY=your_key
DASHSCOPE_API_KEY=your_key  # Optional
BAIDU_APP_ID=your_app_id    # Optional, for image OCR
BAIDU_SECRET_KEY=your_key   # Optional
```

### Run with Docker Compose

```bash
docker-compose up -d
```

### Run Migrations

```bash
docker-compose exec db_translator psql -U translator_user -d translator -f /path/to/migrations/001_init.sql
```

## API Documentation

### Paper Translation

**Endpoint:** `POST /translate-paper`

**Request:** `multipart/form-data`

**Form Fields:**
- `file` (required): PDF file (.pdf)
- `target_lang` (optional): Target language code (e.g., "zh", "en"), default "zh"

**Response:**
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

**Response Fields:**
- `text_translated`: Complete translated paper text extracted from PDF
- `meta.target_lang`: Target language used
- `meta.file_name`: Original uploaded filename (without path)
- `meta.model`: Translation model identifier used

**cURL Example:**
```bash
curl -X POST http://localhost:8002/translate-paper \
  -F "file=@paper.pdf" \
  -F "target_lang=zh"
```

### Text Translation

**Endpoint:** `POST /api/v1/translate/text`

**Request Body:**
```json
{
  "source_lang": "en",
  "target_lang": "zh",
  "content": "Please explain the role of contrastive learning in representation learning.",
  "content_type": "plain",
  "domain": "academic",
  "style": {
    "tone": "formal",
    "fidelity": "high",
    "preserve_citations": true,
    "preserve_latex": true
  },
  "glossary": {
    "project_id": "p_123",
    "terms": [
      {
        "source_text": "contrastive learning",
        "target_text": "对比学习",
        "case_sensitive": false,
        "priority": 1
      }
    ]
  },
  "options": {
    "return_alignment": true,
    "return_quality": true
  }
}
```

**Response:**
```json
{
  "translation": "请解释对比学习在表示学习中的作用。",
  "alignment": [
    {
      "src_span": [0, 6],
      "tgt_span": [0, 19]
    }
  ],
  "glossary_hits": [
    {
      "source": "contrastive learning",
      "target": "对比学习",
      "position": 15
    }
  ],
  "quality": {
    "score": 0.92,
    "issues": [],
    "glossary_hit_rate": 1.0,
    "number_consistency": true
  },
  "trace_id": "7f3c8a9b2d4e1f6a"
}
```

**cURL Example:**
```bash
curl -X POST http://localhost:8002/api/v1/translate/text \
  -H "Content-Type: application/json" \
  -d '{
    "source_lang": "en",
    "target_lang": "zh",
    "content": "Hello world",
    "content_type": "plain",
    "options": {
      "return_quality": true
    }
  }'
```

### Image Translation

**Endpoint:** `POST /api/v1/translate/image`

**Request:** `multipart/form-data`

**Form Fields:**
- `file` (required): Image file (PNG/JPG/WebP, max 2MB)
- `source_lang` (optional): Source language code, default "en"
- `target_lang` (optional): Target language code, default "zh"
- `mode` (optional): Output mode - `text_only`, `structured`, `overlay`, default "structured"
- `domain` (optional): Domain context - `academic`, `biomed`, `cs`, `physics`

**Response:**
```json
{
  "blocks": [
    {
      "type": "paragraph",
      "bbox": [120, 210, 980, 420],
      "source_text": "We propose a novel method for representation learning.",
      "translated_text": "我们提出了一种新的表示学习方法。"
    },
    {
      "type": "caption",
      "bbox": [130, 860, 970, 920],
      "source_text": "Figure 2: Model architecture.",
      "translated_text": "图2：模型架构。"
    },
    {
      "type": "equation",
      "bbox": [200, 500, 900, 600],
      "source_text": "$E = mc^2$",
      "translated_text": "$E = mc^2$"
    }
  ],
  "full_text_translation": "我们提出了一种新的表示学习方法。\n\n图2：模型架构。",
  "quality": {
    "score": 0.88,
    "issues": [],
    "glossary_hit_rate": 0.0,
    "number_consistency": true
  },
  "trace_id": "a1b2c3d4e5f6g7h8"
}
```

**cURL Example:**
```bash
curl -X POST http://localhost:8002/api/v1/translate/image \
  -F "file=@image.png" \
  -F "source_lang=en" \
  -F "target_lang=zh" \
  -F "mode=structured"
```

### PDF Translation

**Endpoint:** `POST /api/v1/translate/pdf`

**Status:** Not yet implemented

**Request:** `multipart/form-data`
- `file` (required): PDF file
- `source_lang` (optional): Source language, default "en"
- `target_lang` (optional): Target language, default "zh"

**Response:**
```json
{
  "error": "PDF translation not yet implemented"
}
```

### Create Async Job

**Endpoint:** `POST /api/v1/jobs/translate`

**Request Body:**
```json
{
  "type": "text",
  "input_ref": "{\"source_lang\":\"en\",\"target_lang\":\"zh\",\"content\":\"Long text to translate...\"}",
  "tenant_id": "tenant_123"
}
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**cURL Example:**
```bash
curl -X POST http://localhost:8002/api/v1/jobs/translate \
  -H "Content-Type: application/json" \
  -d '{
    "type": "text",
    "input_ref": "{\"source_lang\":\"en\",\"target_lang\":\"zh\",\"content\":\"Hello\"}"
  }'
```

### Get Job Status

**Endpoint:** `GET /api/v1/jobs/{job_id}`

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "tenant_123",
  "type": "text",
  "status": "completed",
  "progress": 100,
  "input_ref": "{\"source_lang\":\"en\",\"target_lang\":\"zh\",\"content\":\"Hello\"}",
  "output_ref": "translator/results/550e8400-e29b-41d4-a716-446655440000.json",
  "error_msg": null,
  "trace_id": "trace_123",
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:05Z",
  "completed_at": "2025-01-15T10:30:05Z"
}
```

**Job Status Values:**
- `pending`: Job is queued
- `processing`: Job is being processed
- `completed`: Job completed successfully
- `failed`: Job failed
- `cancelled`: Job was cancelled

**cURL Example:**
```bash
curl http://localhost:8002/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000
```

### Cancel Job

**Endpoint:** `DELETE /api/v1/jobs/{job_id}`

**Response:**
```json
{
  "message": "job cancelled"
}
```

**cURL Example:**
```bash
curl -X DELETE http://localhost:8002/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000
```

### Add Glossary Term

**Endpoint:** `POST /api/v1/glossaries/{project_id}/terms`

**Request Body:**
```json
{
  "source_text": "contrastive learning",
  "target_text": "对比学习",
  "pos": "noun",
  "domain": "machine_learning",
  "case_sensitive": false,
  "regex_pattern": null,
  "priority": 1
}
```

**Response:**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "project_id": "p_123",
  "source_text": "contrastive learning",
  "target_text": "对比学习",
  "pos": "noun",
  "domain": "machine_learning",
  "case_sensitive": false,
  "regex_pattern": null,
  "priority": 1,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

**cURL Example:**
```bash
curl -X POST http://localhost:8002/api/v1/glossaries/p_123/terms \
  -H "Content-Type: application/json" \
  -d '{
    "source_text": "neural network",
    "target_text": "神经网络",
    "case_sensitive": false
  }'
```

### Get Glossary Terms

**Endpoint:** `GET /api/v1/glossaries/{project_id}/terms?query={query}`

**Query Parameters:**
- `query` (optional): Search query for source or target text

**Response:**
```json
{
  "terms": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "project_id": "p_123",
      "source_text": "contrastive learning",
      "target_text": "对比学习",
      "pos": "noun",
      "domain": "machine_learning",
      "case_sensitive": false,
      "regex_pattern": null,
      "priority": 1,
      "created_at": "2025-01-15T10:30:00Z",
      "updated_at": "2025-01-15T10:30:00Z"
    },
    {
      "id": "770e8400-e29b-41d4-a716-446655440002",
      "project_id": "p_123",
      "source_text": "neural network",
      "target_text": "神经网络",
      "case_sensitive": false,
      "priority": 0,
      "created_at": "2025-01-15T10:31:00Z",
      "updated_at": "2025-01-15T10:31:00Z"
    }
  ]
}
```

**cURL Example:**
```bash
# Get all terms
curl http://localhost:8002/api/v1/glossaries/p_123/terms

# Search terms
curl "http://localhost:8002/api/v1/glossaries/p_123/terms?query=neural"
```

### Update Glossary Term

**Endpoint:** `PUT /api/v1/glossaries/{project_id}/terms/{term_id}`

**Request Body:**
```json
{
  "target_text": "对比学习（更新）",
  "priority": 2
}
```

**Response:**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "project_id": "p_123",
  "source_text": "contrastive learning",
  "target_text": "对比学习（更新）",
  "priority": 2,
  "updated_at": "2025-01-15T10:35:00Z"
}
```

**cURL Example:**
```bash
curl -X PUT http://localhost:8002/api/v1/glossaries/p_123/terms/660e8400-e29b-41d4-a716-446655440001 \
  -H "Content-Type: application/json" \
  -d '{
    "target_text": "对比学习（更新）"
  }'
```

### Delete Glossary Term

**Endpoint:** `DELETE /api/v1/glossaries/{project_id}/terms/{term_id}`

**Response:**
```json
{
  "message": "term deleted"
}
```

**cURL Example:**
```bash
curl -X DELETE http://localhost:8002/api/v1/glossaries/p_123/terms/660e8400-e29b-41d4-a716-446655440001
```

### Health Check

**Endpoint:** `GET /health/ready`

**Response (Ready):**
```json
{
  "status": "ready",
  "components": {
    "database": "available",
    "redis": "available"
  }
}
```

**Response (Not Ready):**
```json
{
  "status": "not ready",
  "components": {
    "database": "unavailable",
    "redis": "available"
  }
}
```

**cURL Example:**
```bash
curl http://localhost:8002/health/ready
```

### Error Responses

All endpoints may return error responses in the following format:

**400 Bad Request:**
```json
{
  "error": "invalid request: source_lang is required"
}
```

**404 Not Found:**
```json
{
  "error": "job not found"
}
```

**500 Internal Server Error:**
```json
{
  "error": "translation failed: API error: 401 - Unauthorized"
}
```

## Development

### Go Service

```bash
cd go
go mod download
go run cmd/api/main.go
```

### Python Adapter

```bash
export GO_SERVICE_URL=http://localhost:8002
python -m python_adapter.adapter
```

## Testing

```bash
cd go
go test ./...
```

## License

MIT

