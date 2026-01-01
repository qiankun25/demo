## retrieval_service architecture

### Responsibilities
- Unified retrieval orchestration layer
- Provides `/search` and `/semantic_search` by delegating to `indexing_service`
- Maintains ingestion state machine in a local DB (SQLite by default)

### Dependencies
- indexing_service (HTTP)
- Local DB (SQLite) for state (for multi-instance production, prefer Postgres)

### Ports
- HTTP API: `8003`


