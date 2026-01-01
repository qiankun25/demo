.PHONY: build test run migrate proto

# Build binaries
build:
	go build -o bin/api ./cmd/api
	go build -o bin/worker ./cmd/worker
	go build -o bin/migrate ./cmd/migrate

# Run tests
test:
	go test ./...

# Run API server
run:
	go run ./cmd/api

# Run worker
worker:
	go run ./cmd/worker

# Run migrations
migrate:
	go run ./cmd/migrate

# Generate gRPC code
proto:
	protoc --go_out=. --go_opt=paths=source_relative \
		--go-grpc_out=. --go-grpc_opt=paths=source_relative \
		internal/grpc/translator.proto

# Install dependencies
deps:
	go mod download
	go mod tidy

# Lint
lint:
	golangci-lint run

# Clean
clean:
	rm -rf bin/

