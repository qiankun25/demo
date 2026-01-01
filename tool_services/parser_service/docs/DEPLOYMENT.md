## Deployment

### Image build

```bash
docker build -f tool_services/parser_service/Dockerfile -t parser_service:local .
```

### Runtime
- API: `uvicorn app.main:app --port 8031`
- Worker: `python app/mq_worker.py`

### Required configuration
- `PARSER_DATABASE_URL`
- `RABBITMQ_URL`
- MinIO claim-check: `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` / `MINIO_BUCKET`
- Downstream: `PARSER_DOWNLOAD_BASE_URL` (worker mode)

### Health probes
- `GET /health/live`
- `GET /health/ready`


