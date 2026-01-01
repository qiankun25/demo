## Deployment

### Image build

```bash
docker build -f tool_services/indexing_service/Dockerfile -t indexing_service:local .
```

### Required configuration
- `INDEX_DATABASE_URL`
- `INDEX_CHROMA_PERSIST_DIR` / `INDEX_CHROMA_COLLECTION`
- `INDEX_RABBITMQ_URL` (worker mode)

### Health probes
- `GET /health/live`
- `GET /health/ready`


