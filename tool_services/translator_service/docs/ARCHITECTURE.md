# Translator Service Architecture

## Overview

The Translator Service is a production-ready microservice for academic translation, built with a hybrid Go + Python architecture.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│  Nexus SDK (Python) / RabbitMQ 消息队列                 │
│  └─> Python Adapter (BaseToolService 兼容层)            │
└─────────────────────────────────────────────────────────┘
                        │ HTTP/gRPC
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Go Translator Service (核心服务)                        │
│  ├─ REST API (Gin)                                      │
│  ├─ gRPC Service                                        │
│  ├─ Translation Engine (文本/图片/PDF)                  │
│  ├─ Glossary Service (术语库管理)                       │
│  ├─ Job Queue (异步任务)                                │
│  └─ Quality Assessment (质量评估)                        │
└─────────────────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
    PostgreSQL      Redis Cache    MinIO Storage
    (独立实例)      (缓存/队列)     (对象存储)
```

## Components

### Go Core Service

- **REST API**: Gin framework for HTTP endpoints
- **gRPC Service**: Internal service calls
- **Translation Engine**: Pluggable engines (SiliconFlow/DashScope)
- **OCR Client**: Baidu OCR integration
- **Glossary Service**: Terminology management
- **Quality Service**: Translation quality assessment
- **Job Service**: Async job processing
- **Cache Service**: Redis caching layer

### Python Adapter

- **BaseToolService**: Nexus SDK compatibility
- **HTTP Client**: Calls Go service
- **RabbitMQ Integration**: Message queue handling
- **MinIO Integration**: Claim Check storage

## Data Flow

### Text Translation

1. Request → REST API
2. Normalize & segment text
3. Protect regions (LaTeX, code, URLs)
4. Load glossary
5. Translate (engine)
6. Post-edit (with glossary)
7. Enforce glossary terms
8. Restore protected regions
9. Quality assessment
10. Cache result
11. Return response

### Image Translation

1. Request → REST API
2. Preprocess image
3. OCR + Layout detection
4. Classify blocks (text/equation/table)
5. Translate each block
6. Merge context
7. Quality assessment
8. Return structured result

### Async Job Processing

1. Create job → Database
2. Enqueue → Redis
3. Worker dequeues
4. Process translation
5. Update status
6. Store result → MinIO
7. Complete job

## Database Schema

- `tenants`: Multi-tenant support
- `api_keys`: Authentication
- `glossary_projects`: Glossary projects
- `glossary_terms`: Terminology entries
- `jobs`: Async jobs
- `translation_cache`: Result caching
- `feedback`: User feedback
- `audit_logs`: Audit trail

## API Endpoints

### REST API

- `POST /api/v1/translate/text` - Text translation
- `POST /api/v1/translate/image` - Image translation
- `POST /api/v1/translate/pdf` - PDF translation
- `POST /api/v1/jobs/translate` - Create async job
- `GET /api/v1/jobs/{job_id}` - Get job status
- `POST /api/v1/glossaries/{project_id}/terms` - Add term
- `GET /api/v1/glossaries/{project_id}/terms` - List terms

### gRPC

- `TranslateText` - Text translation
- `TranslateImage` - Image translation
- `GetJobStatus` - Job status

## Deployment

### Docker Compose

```bash
docker-compose up -d
```

Services:
- `translator-go`: Go API server
- `translator-worker`: Background workers
- `translator-python`: Python adapter
- `db_translator`: PostgreSQL
- `redis`: Redis cache/queue
- `minio`: Object storage

### Environment Variables

See `env.example` for required configuration.

## Monitoring

- Health checks: `/health`, `/health/live`, `/health/ready`
- Metrics: Prometheus (to be implemented)
- Logging: Structured JSON logs
- Tracing: OpenTelemetry (to be implemented)

## License

MIT
