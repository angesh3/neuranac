FROM golang:1.22-alpine AS builder
RUN apk add --no-cache git ca-certificates
WORKDIR /app
COPY go.mod ./
COPY go.sum* ./
RUN go mod download 2>/dev/null || true
COPY . .
RUN go mod tidy && CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /ingestion-collector ./cmd/collector/

FROM gcr.io/distroless/static:nonroot
COPY --from=builder /ingestion-collector /ingestion-collector
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
USER nonroot:nonroot
EXPOSE 1162/udp 1514/udp 2055/udp 6767/udp 9102
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD ["/ingestion-collector", "--health-check"] || exit 1
ENTRYPOINT ["/ingestion-collector"]
