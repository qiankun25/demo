## parser_service architecture

### Responsibilities
- Consume `cmd.parser.start` (ref-only: expects a file ref)
- Fetch PDF bytes (via `download_service` signed URL)
- Parse PDF to chunks + metadata
- Store parsed artifact to MinIO (claim-check) and persist index row in Postgres
- Emit `evt.parser.*`

### Dependencies
- Postgres (parsed_docs + inbox/outbox)
- RabbitMQ (command/event)
- MinIO (claim-check)
- download_service (HTTP signed URL) when running worker pipeline

### Ports
- HTTP API: `8031`


