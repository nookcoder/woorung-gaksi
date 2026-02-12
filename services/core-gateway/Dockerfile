FROM golang:1.24-alpine AS builder

WORKDIR /app

# Install build dependencies
RUN apk add --no-cache git

# Copy go mod and sum files
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build the application
# Assuming main entry is cmd/server/main.go
RUN CGO_ENABLED=0 GOOS=linux go build -o /woorung-gateway ./cmd/server

# Final stage
FROM alpine:3.19

WORKDIR /root/

# Copy the binary from builder
COPY --from=builder /woorung-gateway .

# Expose port
EXPOSE 8080

RUN apk add --no-cache ca-certificates

# Copy config directory
COPY --from=builder /app/config ./config

CMD ["./woorung-gateway"]
