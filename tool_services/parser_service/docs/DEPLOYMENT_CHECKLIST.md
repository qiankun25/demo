## Deployment checklist

- [ ] Secrets injected via env/secret manager (MinIO creds, etc.)
- [ ] Postgres reachable; migrations applied
- [ ] RabbitMQ reachable; queues/exchanges ok
- [ ] MinIO reachable; bucket ok
- [ ] API returns 200 on `/health/ready`
- [ ] Worker can successfully consume and ack a test `cmd.parser.start`
- [ ] Logs collected from stdout and include `trace_id/work_key`


