## nexus-contracts

This directory contains the **shared message contracts** (`nexus_contracts`) used by Nexus services for command/event payloads and claim-check references.

### Install (local/dev)

```bash
pip install -e tool_services/libs/contracts
```

### Notes

- This package should stay **dependency-light** (ideally only `pydantic`).
- Version it and publish internally if you want services to be truly independent of the monorepo layout.

