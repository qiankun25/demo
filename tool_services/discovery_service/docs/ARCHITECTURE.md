## discovery_service architecture

### Responsibilities
- External discovery via OpenAlex (tool logic in `nexus_tool/`)
- Persist discovery indices in Postgres (result_id -> output_key)
- MQ worker consumes `cmd.discovery.start`, emits `evt.discovery.*`
- HTTP API provides read-only access to stored results (ref-only)

### Dependencies
- Postgres (results index + inbox/outbox)
- RabbitMQ (command/event)
- Redis (optional cache)
- MinIO (claim-check storage via `nexus_sdk.common.MockStorage`)

### Ports
- HTTP API: `8032`


