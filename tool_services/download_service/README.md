# Literature Download Service

An asynchronous PDF download and upload service built with FastAPI and Celery for the Dify platform's research agent ecosystem. This service enables reliable downloading of academic literature from various sources (arXiv, Semantic Scholar, Springer, etc.) with automatic retry mechanisms, direct file upload capability, MinIO storage, and PostgreSQL-based task tracking.

## Features

- **Asynchronous Processing**: Non-blocking task queue using Celery and Redis for downloads
- **Direct File Upload**: Batch upload multiple PDF files with presigned URL generation
- **Automatic Retries**: Exponential backoff retry logic for transient failures (up to 3 attempts)
- **Object Storage**: PDF files stored in MinIO (S3-compatible)
- **Task Tracking**: PostgreSQL database for task status and metadata
- **Presigned URLs**: Secure, time-limited file access (configurable expiration)
- **Partial Success Handling**: Individual file failures don't affect batch uploads
- **URL Validation**: Pre-download URL reachability checks
- **Containerized**: Full Docker Compose deployment

## Architecture

```
Client → FastAPI → Redis Queue → Celery Worker → MinIO Storage
                ↓                      ↓
            PostgreSQL ← ─ ─ ─ ─ ─ ─ ─ ┘
```

## Prerequisites

- **Docker**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher

No other dependencies are required - all services run in containers.

## Quick Start

1. **Clone the repository** (if applicable):

   ```bash
   git clone <repository-url>
   cd literature-download-service
   ```

2. **Start all services**:

   ```bash
   docker-compose up
   ```

   This will start:

   - FastAPI application (port 8000)
   - Celery worker
   - PostgreSQL database (port 5432)
   - Redis (port 6379)
   - MinIO (ports 9000, 9001)

3. **Verify the service is running**:

   ```bash
   curl http://localhost:8000/health
   ```

   Expected response: `{"status": "healthy"}`

4. **Submit a download request**:

   ```bash
   curl -X POST http://localhost:8000/download \
     -H "Content-Type: application/json" \
     -d '{"url": "https://arxiv.org/pdf/1706.03762.pdf"}'
   ```

   Expected response:

   ```json
   {
     "task_id": "123e4567-e89b-12d3-a456-426614174000",
     "status": "pending"
   }
   ```

5. **Check task status**:

   ```bash
   curl http://localhost:8000/download/123e4567-e89b-12d3-a456-426614174000
   ```

   Expected response (when complete):

   ```json
   {
     "task_id": "123e4567-e89b-12d3-a456-426614174000",
     "status": "success",
     "file_url": "http://localhost:9000/papers/...",
     "error_message": null,
     "created_at": "2024-01-15T10:30:00",
     "updated_at": "2024-01-15T10:30:15"
   }
   ```

6. **Upload PDF files directly**:

   ```bash
   curl -X POST http://localhost:8000/upload \
     -F "files=@document1.pdf" \
     -F "files=@document2.pdf"
   ```

   Expected response:

   ```json
   {
     "total": 2,
     "success": 2,
     "failed": 0,
     "results": [
       {
         "file_name": "document1.pdf",
         "status": "success",
         "file_id": "uuid",
         "presigned_url": "http://localhost:9000/papers/...",
         "expires_in": 3600
       },
       ...
     ]
   }
   ```

## API Endpoints

### POST /download

Submit a new download task.

**Request:**

```json
{
  "url": "https://arxiv.org/pdf/1706.03762.pdf"
}
```

**Response (200 OK):**

```json
{
  "task_id": "uuid",
  "status": "pending"
}
```

**Error Response (422 Unprocessable Entity):**

```json
{
  "detail": [
    {
      "loc": ["body", "url"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### GET /download/{task_id}

Query the status of a download task.

**Response (200 OK) - Pending/Downloading:**

```json
{
  "task_id": "uuid",
  "status": "downloading",
  "file_url": null,
  "error_message": null,
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T10:30:05"
}
```

**Response (200 OK) - Success:**

```json
{
  "task_id": "uuid",
  "status": "success",
  "file_url": "http://localhost:9000/papers/uuid/filename.pdf?X-Amz-...",
  "error_message": null,
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T10:30:15"
}
```

**Response (200 OK) - Failed:**

```json
{
  "task_id": "uuid",
  "status": "failed",
  "file_url": null,
  "error_message": "Connection timeout after 10 seconds",
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T10:31:00"
}
```

**Response (404 Not Found):**

```json
{
  "detail": "Task not found"
}
```

### POST /upload

Upload multiple PDF files to MinIO storage.

**Request:**

- Content-Type: `multipart/form-data`
- Fields:
  - `files`: Multiple PDF files (required)
  - `expires`: Presigned URL expiration time in seconds (optional, default: 3600, range: 60-604800)

**Example:**

```bash
curl -X POST http://localhost:8000/upload \
  -F "files=@paper1.pdf" \
  -F "files=@paper2.pdf" \
  -F "expires=7200"
```

**Response (200 OK) - All files succeeded:**

```json
{
  "total": 2,
  "success": 2,
  "failed": 0,
  "results": [
    {
      "file_name": "paper1.pdf",
      "status": "success",
      "file_id": "550e8400-e29b-41d4-a716-446655440000",
      "file_size": 2048576,
      "mime_type": "application/pdf",
      "presigned_url": "http://localhost:9000/papers/550e8400.../paper1.pdf?X-Amz-...",
      "expires_in": 7200,
      "created_at": "2024-01-15T10:30:00",
      "error_message": null
    },
    {
      "file_name": "paper2.pdf",
      "status": "success",
      "file_id": "550e8400-e29b-41d4-a716-446655440001",
      "file_size": 1024768,
      "mime_type": "application/pdf",
      "presigned_url": "http://localhost:9000/papers/550e8400.../paper2.pdf?X-Amz-...",
      "expires_in": 7200,
      "created_at": "2024-01-15T10:30:01",
      "error_message": null
    }
  ]
}
```

**Response (200 OK) - Partial success:**

```json
{
  "total": 3,
  "success": 2,
  "failed": 1,
  "results": [
    {
      "file_name": "valid.pdf",
      "status": "success",
      "file_id": "550e8400-e29b-41d4-a716-446655440000",
      "file_size": 2048576,
      "mime_type": "application/pdf",
      "presigned_url": "http://localhost:9000/papers/...",
      "expires_in": 3600,
      "created_at": "2024-01-15T10:30:00",
      "error_message": null
    },
    {
      "file_name": "toolarge.pdf",
      "status": "failed",
      "file_id": null,
      "file_size": null,
      "mime_type": null,
      "presigned_url": null,
      "expires_in": null,
      "created_at": null,
      "error_message": "File size exceeds limit (100MB)"
    },
    {
      "file_name": "valid2.pdf",
      "status": "success",
      "file_id": "550e8400-e29b-41d4-a716-446655440001",
      "file_size": 1024768,
      "mime_type": "application/pdf",
      "presigned_url": "http://localhost:9000/papers/...",
      "expires_in": 3600,
      "created_at": "2024-01-15T10:30:02",
      "error_message": null
    }
  ]
}
```

**Error Response (422 Unprocessable Entity):**

- No files provided
- Invalid expiration time (must be 60-604800 seconds)

```json
{
  "detail": "No files provided"
}
```

**Validation Rules:**

- Only PDF files are accepted (`.pdf` extension and `application/pdf` MIME type)
- Maximum file size: 100MB (configurable via `MAX_FILE_SIZE`)
- Partial success: Individual file failures don't affect other files in the batch

### GET /health

Health check endpoint.

**Response (200 OK):**

```json
{
  "status": "healthy"
}
```

## Task Status Flow

```
pending → downloading → success
                    ↓
                  failed (after 3 retries)
```

- **pending**: Task created, waiting for worker
- **downloading**: Worker processing the download
- **success**: File downloaded and stored successfully
- **failed**: All retry attempts exhausted

## Retry Logic

The service automatically retries failed downloads with exponential backoff:

- **Attempt 1**: Immediate
- **Attempt 2**: 5 seconds delay
- **Attempt 3**: 25 seconds delay (5 × 2²)
- **Attempt 4**: 125 seconds delay (5 × 2³)

After 3 retries (4 total attempts), the task is marked as `failed`.

## Environment Variables

All configuration is managed through environment variables. Default values are provided in `.env` file.

### Required Variables

| Variable           | Description                  | Example                                           |
| ------------------ | ---------------------------- | ------------------------------------------------- |
| `DATABASE_URL`     | PostgreSQL connection string | `postgresql://user:pass@localhost:5432/downloads` |
| `MINIO_ENDPOINT`   | MinIO server endpoint        | `localhost:9000`                                  |
| `MINIO_ACCESS_KEY` | MinIO access key             | `minioadmin`                                      |
| `MINIO_SECRET_KEY` | MinIO secret key             | `minioadmin`                                      |

### Optional Variables

| Variable                | Description               | Default                    |
| ----------------------- | ------------------------- | -------------------------- |
| `REDIS_URL`             | Redis connection string   | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL`     | Celery broker URL         | Same as `REDIS_URL`        |
| `CELERY_RESULT_BACKEND` | Celery result backend URL | `redis://localhost:6379/1` |
| `MINIO_BUCKET`          | MinIO bucket name         | `papers`                   |
| `MINIO_SECURE`          | Use HTTPS for MinIO       | `false`                    |

### Configuration for Different Environments

**Development (default `.env`):**

```env
DATABASE_URL=postgresql://user:pass@localhost:5432/downloads
REDIS_URL=redis://localhost:6379/0
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=papers
MINIO_SECURE=false
```

**Production (example):**

```env
DATABASE_URL=postgresql://prod_user:secure_pass@db.example.com:5432/downloads
REDIS_URL=redis://redis.example.com:6379/0
MINIO_ENDPOINT=s3.example.com:443
MINIO_ACCESS_KEY=<production-access-key>
MINIO_SECRET_KEY=<production-secret-key>
MINIO_BUCKET=production-papers
MINIO_SECURE=true
```

## Testing

### Run All Tests

```bash
pytest
```

### Run Specific Test Files

```bash
# Unit tests
pytest tests/test_validator.py

# Integration tests
pytest tests/test_download_integration.py
```

### Run Tests with Coverage

```bash
pytest --cov=app --cov-report=html
```

Coverage report will be generated in `htmlcov/index.html`.

### Run Tests in Docker

```bash
docker-compose run --rm app pytest
```

### Test Requirements

The integration tests require:

- All services running (PostgreSQL, Redis, MinIO)
- Internet connection (for downloading test PDFs)
- Celery worker running

The test suite will:

1. Submit a real download request
2. Start a Celery worker subprocess
3. Poll for task completion (max 60 seconds)
4. Verify file accessibility via presigned URL
5. Clean up test data

## Development

### Project Structure

```
.
├── app/
│   ├── models/          # SQLAlchemy models
│   │   ├── task.py      # DownloadTask model
│   │   └── file.py      # DocumentFile model
│   ├── routes/          # FastAPI routes
│   │   └── download.py  # Download endpoints
│   ├── services/        # Business logic
│   │   ├── validator.py # URL validation
│   │   ├── downloader.py # PDF downloading
│   │   └── storage.py   # MinIO storage
│   ├── tasks/           # Celery tasks
│   │   └── download_task.py
│   ├── config.py        # Configuration
│   ├── database.py      # Database setup
│   ├── celery_app.py    # Celery configuration
│   └── main.py          # FastAPI application
├── tests/               # Test suite
├── docker-compose.yml   # Service orchestration
├── Dockerfile           # Application container
├── requirements.txt     # Python dependencies
└── .env                 # Environment variables
```

### Running Services Individually

**FastAPI only:**

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Celery worker only:**

```bash
celery -A app.celery_app worker --loglevel=info
```

**Database migrations** (if using Alembic):

```bash
alembic upgrade head
```

### Accessing Service UIs

- **FastAPI Docs**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001 (login: minioadmin/minioadmin)
- **Celery Flower** (if installed): http://localhost:5555

## Monitoring

### View Celery Worker Logs

```bash
docker-compose logs -f celery
```

### View Application Logs

```bash
docker-compose logs -f app
```

### Check Database

```bash
docker-compose exec db psql -U user -d downloads
```

Example queries:

```sql
-- View all tasks
SELECT id, url, status, retry_count, created_at FROM download_task;

-- Count tasks by status
SELECT status, COUNT(*) FROM download_task GROUP BY status;

-- View recent failures
SELECT url, error_message, updated_at
FROM download_task
WHERE status = 'failed'
ORDER BY updated_at DESC
LIMIT 10;
```

### Check MinIO Storage

```bash
docker-compose exec minio mc ls local/papers
```

## Troubleshooting

### Service won't start

**Check if ports are already in use:**

```bash
# Windows
netstat -ano | findstr "8000"
netstat -ano | findstr "5432"
netstat -ano | findstr "6379"
netstat -ano | findstr "9000"
```

**Solution**: Stop conflicting services or modify ports in `docker-compose.yml`.

### Task stuck in "pending" status

**Possible causes:**

- Celery worker not running
- Redis connection issues

**Check worker status:**

```bash
docker-compose ps celery
docker-compose logs celery
```

**Restart worker:**

```bash
docker-compose restart celery
```

### Download fails with timeout

**Possible causes:**

- Source URL is slow or unreachable
- Network connectivity issues

**Check URL manually:**

```bash
curl -I <pdf-url>
```

**Increase timeout** (modify `app/services/validator.py` and `app/services/downloader.py`).

### MinIO connection errors

**Check MinIO health:**

```bash
curl http://localhost:9000/minio/health/live
```

**Access MinIO console:**

- URL: http://localhost:9001
- Login: minioadmin / minioadmin
- Verify bucket "papers" exists

### Database connection errors

**Check PostgreSQL:**

```bash
docker-compose exec db pg_isready -U user -d downloads
```

**Reset database:**

```bash
docker-compose down -v
docker-compose up
```

## Production Deployment

📖 **部署文档**:

- [QUICKSTART.md](./QUICKSTART.md) - 5 分钟快速启动指南
- [DEPLOYMENT.md](./DEPLOYMENT.md) - 完整的生产环境部署指南
- [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md) - 部署检查清单
- [DEPLOYMENT_SUMMARY.md](./DEPLOYMENT_SUMMARY.md) - 部署配置总结

**部署指南包括**:

- 环境变量配置说明（带默认值）
- Docker 生产部署步骤
- 与 Dify 和其他服务集成方案
- Nginx 反向代理配置
- 监控和日志管理
- 故障排查指南
- 备份和恢复流程

### 快速部署

1. **准备环境配置**:

   ```bash
   cp .env.production.example .env.production
   # 编辑 .env.production，修改所有 CHANGE_ME 值
   ```

2. **运行部署脚本**:

   ```bash
   chmod +x scripts/deploy.sh
   ./scripts/deploy.sh
   ```

3. **健康检查**:
   ```bash
   chmod +x scripts/health-check.sh
   ./scripts/health-check.sh
   ```

### 与 Dify 集成

本服务可以作为 Dify Workflow 的 HTTP 节点使用，实现文献自动下载和分析。

**示例配置**:

```yaml
# Dify HTTP Request 节点
Method: POST
URL: http://literature-download-service:8000/api/v1/download
Headers:
  X-API-Key: ${LITERATURE_API_KEY}
Body: { "url": "{{input.paper_url}}", "source_type": "arxiv" }
```

完整的 Dify 集成示例请参考 [dify-integration-example.json](./dify-integration-example.json)

### Security Considerations

1. **Change default credentials**:

   - PostgreSQL user/password
   - MinIO access/secret keys
   - Redis password (add to connection string)

2. **Enable HTTPS**:

   - Set `MINIO_SECURE=true`
   - Use reverse proxy (nginx) for FastAPI

3. **Network isolation**:

   - Use Docker networks
   - Don't expose database ports publicly

4. **API Key authentication**:
   - Configure `ALLOWED_API_KEYS` in production
   - Use `X-API-Key` header for all requests

### Scaling

**Horizontal scaling:**

```bash
docker-compose -f docker-compose.prod.yml up -d --scale celery=3
```

This runs 3 Celery workers for parallel processing.

**Load balancing** (nginx included in production compose):

```bash
docker-compose -f docker-compose.prod.yml --profile with-nginx up -d
```
