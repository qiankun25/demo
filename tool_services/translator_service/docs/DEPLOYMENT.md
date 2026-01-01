## Deployment

### Image build

```bash
docker build -f tool_services/translator_service/Dockerfile -t translator_service:local .
```

### Required configuration
- At least one of:
  - `SILICONFLOW_API_KEY` (enables text translation + image fallback)
  - `BAIDU_APP_ID` + `BAIDU_SECRET_KEY` (enables preferred image OCR translation)

### Health probes
- `GET /health/live`
- `GET /health/ready`


