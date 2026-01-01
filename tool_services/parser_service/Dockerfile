# Run from repository root: docker build -f tool_services/parser_service/Dockerfile .
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SERVICE_MODE=api

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY tool_services/parser_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Shared libs for claim-check contracts (optional)
COPY tool_services/libs/contracts /app/tool_services/libs/contracts
RUN pip install --no-cache-dir /app/tool_services/libs/contracts

COPY tool_services/parser_service/app /app/app
COPY tool_services/parser_service/alembic.ini /app/alembic.ini
COPY tool_services/parser_service/migrations /app/migrations

ENV PYTHONPATH=/app

EXPOSE 8031

# Healthcheck:
# - In API mode: probe readiness endpoint
# - In worker mode: always healthy (worker has no HTTP server)
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD sh -c 'if [ "$SERVICE_MODE" = "worker" ]; then exit 0; else curl -fsS http://localhost:8031/health/ready >/dev/null; fi'

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8031"]


