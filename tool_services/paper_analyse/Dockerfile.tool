# Run from repository root: docker build -f tool_services/paper_analyse/Dockerfile.tool .

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
COPY tool_services/paper_analyse/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY tool_services/paper_analyse/nexus_tool /app/nexus_tool

# Set python path
ENV PYTHONPATH=/app

# Run the worker
CMD ["python", "-m", "nexus_tool.tool_service"]
