## Deployment checklist

- [ ] Postgres reachable; migrations applied
- [ ] Chroma persistence volume mounted (or stable local disk)
- [ ] `/health/ready` returns 200
- [ ] Search endpoint returns results for a known indexed doc
- [ ] (worker mode) RabbitMQ reachable and worker can consume `cmd.indexer.start`


