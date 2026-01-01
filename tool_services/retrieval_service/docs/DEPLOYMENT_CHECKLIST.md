## Deployment checklist

- [ ] Downstream indexing_service reachable and healthy
- [ ] State DB is persistent (not ephemeral) and backed up
- [ ] `/health/ready` returns 200
- [ ] Smoke test: POST `/semantic_search` succeeds


