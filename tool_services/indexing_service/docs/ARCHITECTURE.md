## indexing_service architecture

### Responsibilities
- Accept `doc + chunks[]` and build:
  - Metadata/index tables in Postgres
  - Vector index in Chroma (persistent)
- Provide search APIs (`/search`, `/kb/overview`, ...)
- MQ worker consumes `cmd.indexer.start` and emits `evt.indexer.*`

### Dependencies
- Postgres
- RabbitMQ (worker mode)
- Local persistent volume for Chroma

### Ports
- HTTP API: `8020`


