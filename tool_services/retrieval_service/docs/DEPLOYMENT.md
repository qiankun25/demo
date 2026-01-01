## Deployment

### Image build

```bash
docker build -f tool_services/retrieval_service/Dockerfile -t retrieval_service:local .
```

### Required configuration
- `RETRIEVAL_INDEXING_BASE_URL`
- `RETRIEVAL_DB_PATH` (persist storage; for production multi-replica, use a shared DB instead of SQLite)

### Health probes
- `GET /health/live`
- `GET /health/ready` (checks downstream indexing_service)


