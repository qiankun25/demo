## Deployment checklist

- [ ] **Secrets** injected via environment / secret manager (no hardcoded keys)
- [ ] Postgres reachable; migrations applied (`alembic upgrade head`)
- [ ] RabbitMQ reachable; exchanges/queues provisioned (or auto-declared by worker)
- [ ] MinIO reachable; bucket exists (or auto-created by claim-check client)
- [ ] `/health/live` and `/health/ready` return 200
- [ ] Logs are collected (stdout) and include trace identifiers for MQ flows
- [ ] Resource limits configured (CPU/memory), and autoscaling policy defined (if K8s)


