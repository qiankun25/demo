# Run from repository root: docker build -f tool_services/retrieval_service/Dockerfile .

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SERVICE_MODE=api

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Nexus SDK
COPY nexus_sdk /app/nexus_sdk
RUN pip install --no-cache-dir /app/nexus_sdk

# Copy and install service requirements
COPY tool_services/retrieval_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY tool_services/retrieval_service/ /app/

# Set python path
ENV PYTHONPATH=/app

# Expose API port
EXPOSE 8003

# Healthcheck: readiness endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8003/health/ready >/dev/null || exit 1

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Run the API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
