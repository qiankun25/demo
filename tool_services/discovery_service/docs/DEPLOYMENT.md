## Deployment

### Container image
Build from repo root context:

```bash
docker build -f tool_services/discovery_service/Dockerfile -t discovery_service:local .
```

### Runtime modes
- **API**: `SERVICE_MODE=api` + run `uvicorn app.main:app --port 8032`
- **Worker**: `SERVICE_MODE=worker` + run `python -m app.worker_main`

### Required environment variables (production)
- `DISCOVERY_DATABASE_URL`
- `RABBITMQ_URL`
- `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` / `MINIO_BUCKET`
- (optional) `REDIS_URL`

### Health probes
- Liveness: `GET /health/live`
- Readiness: `GET /health/ready`


