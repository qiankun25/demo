# Run from repository root: docker build -f tool_services/indexing_service/Dockerfile .

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Nexus SDK
COPY nexus_sdk /app/nexus_sdk
RUN pip install --no-cache-dir /app/nexus_sdk

# Copy and install service requirements
COPY tool_services/indexing_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY tool_services/indexing_service/ /app/

# Set python path
ENV PYTHONPATH=/app

# Expose API port
EXPOSE 8020

# Run the API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8020"]
