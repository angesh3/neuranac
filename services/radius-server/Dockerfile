FROM golang:1.22-alpine AS builder
RUN apk add --no-cache git ca-certificates
WORKDIR /app
COPY go.mod ./
COPY go.sum* ./
RUN go mod download 2>/dev/null || true
COPY . .
RUN go mod tidy && CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /radius-server ./cmd/server/

FROM gcr.io/distroless/static:nonroot
COPY --from=builder /radius-server /radius-server
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
USER nonroot:nonroot
EXPOSE 1812/udp 1813/udp 2083 3799/udp 49 9100
ENTRYPOINT ["/radius-server"]
