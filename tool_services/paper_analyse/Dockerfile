# Run from repository root: docker build -f tool_services/paper_analyse/Dockerfile .

# Build stage
FROM golang:1.22 as builder

WORKDIR /app

# Copy go.mod and go.sum from the service directory
COPY tool_services/paper_analyse/go.mod tool_services/paper_analyse/go.sum ./
RUN go mod download

# Copy source code
COPY tool_services/paper_analyse/ .

# Build the binary
RUN CGO_ENABLED=0 GOOS=linux go build -o main .

# Runtime stage
FROM debian:bookworm-slim

WORKDIR /app

# Install runtime dependencies (pdftotext)
RUN apt-get update && apt-get install -y \
    poppler-utils \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy binary from builder
COPY --from=builder /app/main .
# Copy web resources
COPY --from=builder /app/web ./web

# Expose port
EXPOSE 3000

# Run the binary
CMD ["./main"]
