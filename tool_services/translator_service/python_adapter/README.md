# Python Adapter for Translator Service

Python compatibility layer that integrates the Go translator service with the Nexus SDK.

## Overview

This adapter provides a `BaseToolService` implementation that:
1. Receives translation requests from RabbitMQ (via Nexus SDK)
2. Calls the Go translator service via HTTP/gRPC
3. Stores results in MinIO (Claim Check pattern)
4. Publishes completion events back to RabbitMQ

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Set environment variables:

```bash
export GO_SERVICE_URL=http://localhost:8002
export RABBITMQ_URL=amqp://guest:guest@localhost:5672/
export MINIO_ENDPOINT=localhost:9000
export MINIO_ACCESS_KEY=minioadmin
export MINIO_SECRET_KEY=minioadmin
export MINIO_BUCKET=papers
```

## Usage

### Standalone

```bash
python -m python_adapter.adapter
```

### With Docker

```bash
docker-compose up translator-python
```

## Integration

The adapter implements the `BaseToolService` interface from Nexus SDK:

```python
from python_adapter import TranslatorAdapter

service = TranslatorAdapter()
await service.start()  # Starts listening to RabbitMQ
```

## Input Format

Expected input in MockStorage:

```json
{
  "text": "Hello world",
  "images": ["/path/to/image.png"],
  "source_lang": "en",
  "target_lang": "zh"
}
```

## Output Format

Output written to MockStorage:

```json
{
  "text_translated": "你好世界",
  "images_translated": [...],
  "meta": {
    "target_lang": "zh",
    "image_count": 1,
    "model": "go-service"
  }
}
```

## License

MIT

