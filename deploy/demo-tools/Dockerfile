# ─────────────────────────────────────────────────────────────────────────────
# NeuraNAC Demo Tools Container
# Bundles all client-side tools needed to run demos against the NeuraNAC platform:
#   • radtest (FreeRADIUS client)   — RADIUS PAP/MAB authentication
#   • Go 1.22                       — RADIUS protocol test suite
#   • k6                            — API load testing
#   • Python 3 + requests           — Sanity runner (344 tests)
#   • curl, jq, openssl             — Ad-hoc API calls and TLS checks
#
# Usage:
#   docker compose -f deploy/docker-compose.yml --profile demo up -d demo-tools
#   docker exec -it neuranac-demo-tools bash
#   # or use the interactive demo runner:
#   docker exec -it neuranac-demo-tools /opt/demo/demo-runner.sh
# ─────────────────────────────────────────────────────────────────────────────

FROM golang:1.22-bookworm AS go-base

# ── Stage 1: Build Go RADIUS test binary ─────────────────────────────────────
WORKDIR /build/tests
COPY tests/integration/go.mod tests/integration/go.sum* ./
RUN go mod download 2>/dev/null || true
COPY tests/integration/ ./
RUN CGO_ENABLED=0 go test -c -o /radius-test-bin . 2>/dev/null || true

# ── Stage 2: Final demo-tools image ──────────────────────────────────────────
FROM debian:bookworm-slim

LABEL maintainer="NeuraNAC Team"
LABEL description="NeuraNAC Demo Tools — radtest, Go, k6, Python, curl, jq"

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# ── Install system packages ───────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # FreeRADIUS client (provides radtest, radclient)
    freeradius-utils \
    # Network tools
    curl wget netcat-openbsd dnsutils iputils-ping \
    # JSON processing
    jq \
    # TLS / certificate inspection
    openssl ca-certificates \
    # Python 3 for sanity runner
    python3 python3-pip python3-venv \
    # Shell utilities
    bash less vim-tiny procps \
    && rm -rf /var/lib/apt/lists/*

# ── Install Python packages (for sanity runner) ──────────────────────────────
RUN pip3 install --break-system-packages --no-cache-dir \
    requests>=2.31.0 \
    urllib3>=2.0.0

# ── Install Go (for running tests from source) ───────────────────────────────
COPY --from=go-base /usr/local/go /usr/local/go
ENV PATH="/usr/local/go/bin:${PATH}"
ENV GOPATH="/go"
ENV PATH="${GOPATH}/bin:${PATH}"

# ── Install k6 ───────────────────────────────────────────────────────────────
RUN ARCH=$(dpkg --print-architecture) && \
    K6_VERSION="v0.49.0" && \
    if [ "$ARCH" = "arm64" ]; then K6_ARCH="arm64"; else K6_ARCH="amd64"; fi && \
    wget -q "https://github.com/grafana/k6/releases/download/${K6_VERSION}/k6-${K6_VERSION}-linux-${K6_ARCH}.tar.gz" -O /tmp/k6.tar.gz && \
    tar -xzf /tmp/k6.tar.gz -C /tmp && \
    mv /tmp/k6-${K6_VERSION}-linux-${K6_ARCH}/k6 /usr/local/bin/k6 && \
    chmod +x /usr/local/bin/k6 && \
    rm -rf /tmp/k6*

# ── Copy pre-built Go test binary (if build succeeded) ───────────────────────
COPY --from=go-base /radius-test-bin /usr/local/bin/radius-test-bin

# ── Create workspace directories ─────────────────────────────────────────────
RUN mkdir -p /opt/demo /workspace/tests /workspace/scripts

# ── Copy the interactive demo runner script ───────────────────────────────────
COPY deploy/demo-tools/demo-runner.sh /opt/demo/demo-runner.sh
RUN chmod +x /opt/demo/demo-runner.sh

# ── Environment defaults (override via docker-compose) ────────────────────────
ENV NeuraNAC_API_HOST="api-gateway"
ENV NeuraNAC_API_PORT="8080"
ENV NeuraNAC_API_URL="http://api-gateway:8080"
ENV NeuraNAC_RADIUS_HOST="radius-server"
ENV NeuraNAC_RADIUS_IP="radius-server"
ENV NeuraNAC_WEB_URL="http://web:80"
ENV RADIUS_SECRET="testing123"
ENV RADIUS_USER="testuser"
ENV RADIUS_PASS="testing123"
ENV ADMIN_USER="admin"
ENV ADMIN_PASS="admin123"

WORKDIR /workspace

# Keep the container running so you can exec into it
CMD ["sleep", "infinity"]
