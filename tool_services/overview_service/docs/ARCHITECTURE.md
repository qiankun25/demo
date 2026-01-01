## overview_service architecture

### Responsibilities
- Read-only API to fetch overview reports from claim-check storage
- Optional worker generates reports and writes them back to storage

### Dependencies
- MinIO (claim-check)
- LLM provider (worker mode, for SUMMARY_REPORT)

### Ports
- HTTP API: `8040`


