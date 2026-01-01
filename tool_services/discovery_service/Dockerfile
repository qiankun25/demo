# Run from repository root: docker build -f tool_services/discovery_service/Dockerfile .

FROM python:3.11-slim

WORKDIR /app

# Runtime defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SERVICE_MODE=worker

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Nexus SDK
COPY nexus_sdk /app/nexus_sdk
RUN pip install --no-cache-dir /app/nexus_sdk

# Copy and install service requirements
COPY tool_services/discovery_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY tool_services/discovery_service/nexus_tool /app/nexus_tool
COPY tool_services/discovery_service/app /app/app
COPY tool_services/discovery_service/alembic.ini /app/alembic.ini
COPY tool_services/discovery_service/migrations /app/migrations

# Set python path to include current directory so imports work
ENV PYTHONPATH=/app

# Port is only used in API mode (worker mode does not listen on HTTP).
EXPOSE 8032

# Healthcheck:
# - In API mode: probe readiness endpoint
# - In worker mode: always healthy (worker has no HTTP server)
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD sh -c 'if [ "$SERVICE_MODE" = "worker" ]; then exit 0; else curl -fsS http://localhost:8032/health/ready >/dev/null; fi'

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Default: run worker. API overrides CMD in compose.
CMD ["python", "-m", "app.worker_main"]
