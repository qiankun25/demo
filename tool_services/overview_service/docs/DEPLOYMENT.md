## Deployment

### Image build

```bash
docker build -f tool_services/overview_service/Dockerfile -t overview_service:local .
```

### Runtime
- API: `uvicorn app.main:app --port 8040`
- Worker: `python -m nexus_tool.tool_service`

### Required configuration
- MinIO claim-check env vars
- Worker mode: `SILICONFLOW2_API_KEY` (+ base/model)

### Health probes
- `GET /health/live`
- `GET /health/ready`


