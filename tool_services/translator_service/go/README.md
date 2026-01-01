# Translator Service - Go Implementation

Production-ready translation microservice built with Go.

## Features

- **Text Translation**: Multi-language translation with LaTeX/citation preservation
- **Image Translation**: OCR + translation with structured output
- **PDF Translation**: Parse and translate PDFs to Markdown
- **Glossary Management**: Project/tenant-level terminology
- **Quality Assessment**: Automatic quality scoring
- **Async Jobs**: Background job processing with Redis
- **Caching**: Redis-based result caching

## Quick Start

### Prerequisites

- Go 1.21+
- PostgreSQL 15+
- Redis 7+
- MinIO (or S3-compatible storage)

### Configuration

Set environment variables:

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=translator
export DB_USER=translator_user
export DB_PASSWORD=your_password

export REDIS_HOST=localhost
export REDIS_PORT=6379

export MINIO_ENDPOINT=localhost:9000
export MINIO_ACCESS_KEY=minioadmin
export MINIO_SECRET_KEY=minioadmin

export SILICONFLOW_API_KEY=your_key
export DASHSCOPE_API_KEY=your_key  # Optional
export BAIDU_APP_ID=your_app_id    # Optional
export BAIDU_SECRET_KEY=your_key   # Optional
```

### Run Migrations

```bash
make migrate
# or
go run ./cmd/migrate
```

### Build

```bash
make build
```

### Run API Server

```bash
make run
# or
./bin/api
```

### Run Worker

```bash
make worker
# or
./bin/worker
```

### Run Tests

```bash
make test
```

## API Endpoints

### Text Translation

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

```bash
curl -X POST http://localhost:8002/api/v1/translate/image \
  -F "file=@image.png" \
  -F "source_lang=en" \
  -F "target_lang=zh"
```

### Create Job

```bash
curl -X POST http://localhost:8002/api/v1/jobs/translate \
  -H "Content-Type: application/json" \
  -d '{
    "type": "text",
    "input_ref": "{\"source_lang\":\"en\",\"target_lang\":\"zh\",\"content\":\"Hello\"}"
  }'
```

## Project Structure

```
go/
├── cmd/
│   ├── api/          # REST API server
│   ├── worker/       # Background worker
│   └── migrate/      # Database migrations
├── internal/
│   ├── api/          # HTTP handlers
│   ├── grpc/         # gRPC service
│   ├── service/      # Business logic
│   ├── model/        # Data models
│   └── config/       # Configuration
├── pkg/
│   └── ocr/          # OCR clients
└── migrations/       # SQL migration files
```

## Development

### Generate gRPC Code

```bash
make proto
```

### Run Linter

```bash
make lint
```

## License

MIT

