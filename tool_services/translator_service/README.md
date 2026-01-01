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

### API Endpoints

- `POST /api/v1/translate/text` - Text translation
- `POST /api/v1/translate/image` - Image translation
- `POST /api/v1/jobs/translate` - Create async job
- `GET /api/v1/jobs/{job_id}` - Get job status
- `POST /api/v1/glossaries/{project_id}/terms` - Add glossary term
- `GET /health/ready` - Health check

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

