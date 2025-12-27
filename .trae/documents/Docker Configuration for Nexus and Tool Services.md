I have successfully checked and configured Dockerfiles for all services in `tool_services` and `nexus`.

### Summary of Actions
1.  **Analyzed Existing Services**: Checked `nexus` and `download_service`, which already had valid Dockerfiles.
2.  **Created New Dockerfiles**:
    *   **Discovery Service** (`tool_services/discovery_service`): Created `Dockerfile` and `requirements.txt`. Configured as a **Worker** (runs `nexus_tool.tool_service`).
    *   **Overview Service** (`tool_services/overview_service`): Created `Dockerfile` and `requirements.txt`. Configured as a **Worker** (runs `nexus_tool.tool_service`).
    *   **Indexing Service** (`tool_services/indexing_service`): Created `Dockerfile`. Configured as an **API** (runs `main.py` on port 8020), but includes `nexus_sdk` for hybrid use.
    *   **Retrieval Service** (`tool_services/retrieval_service`): Created `Dockerfile`. Configured as an **API** (runs `main.py` on port 8003).
    *   **Translator Service** (`tool_services/translator_service`): Created `Dockerfile`. Configured as an **API** (runs `main.py` on port 8002).
    *   **Paper Analyse** (`tool_services/paper_analyse`): Created `Dockerfile` (Go). Configured as an **API** (runs binary on port 3000).

### Key Configurations
*   **Base Images**: Python services use `python:3.11-slim`. Paper Analyse uses `golang:1.22` (build) and `debian:bookworm-slim` (runtime).
*   **Nexus SDK**: All Python services are configured to install `nexus_sdk` from the repository root, ensuring shared dependencies are available.
*   **Context**: All Dockerfiles are designed to be built from the **repository root** (e.g., `docker build -f tool_services/discovery_service/Dockerfile .`).

### Verification
*   **Files Created**: Verified the existence of all created `Dockerfile` and `requirements.txt` files.
*   **Dependencies**: Added missing `requirements.txt` for `discovery_service` and `overview_service` based on code analysis (`aiohttp`, `httpx`).

### Next Steps
You can now build the images using commands like:
```bash
docker build -f tool_services/discovery_service/Dockerfile -t discovery-service .
docker build -f tool_services/indexing_service/Dockerfile -t indexing-service .
# ... and so on
```