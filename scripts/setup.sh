#!/usr/bin/env bash
set -euo pipefail

echo "=========================================="
echo "  NeuraNAC - NeuraNAC Setup"
echo "=========================================="

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "ERROR: docker is required"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || command -v "docker compose" >/dev/null 2>&1 || { echo "ERROR: docker-compose is required"; exit 1; }

# Copy env file if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[+] Created .env from .env.example"
    echo "    IMPORTANT: Update passwords in .env before production use!"
fi

# Generate dev TLS certs if needed
CERT_DIR="deploy/certs"
if [ ! -f "$CERT_DIR/ca.crt" ]; then
    echo "[+] Generating development TLS certificates..."
    mkdir -p "$CERT_DIR"
    # CA
    openssl req -x509 -newkey rsa:4096 -keyout "$CERT_DIR/ca.key" -out "$CERT_DIR/ca.crt" \
        -days 3650 -nodes -subj "/CN=NeuraNAC Dev CA" 2>/dev/null
    # Server cert
    openssl req -newkey rsa:2048 -keyout "$CERT_DIR/server.key" -out "$CERT_DIR/server.csr" \
        -nodes -subj "/CN=localhost" 2>/dev/null
    openssl x509 -req -in "$CERT_DIR/server.csr" -CA "$CERT_DIR/ca.crt" -CAkey "$CERT_DIR/ca.key" \
        -CAcreateserial -out "$CERT_DIR/server.crt" -days 365 2>/dev/null
    # RadSec cert
    cp "$CERT_DIR/server.crt" "$CERT_DIR/radsec.crt"
    cp "$CERT_DIR/server.key" "$CERT_DIR/radsec.key"
    echo "    Certificates generated in $CERT_DIR/"
fi

# Start infrastructure
echo "[+] Starting infrastructure services..."
docker compose -f deploy/docker-compose.yml up -d postgres redis nats

echo "[+] Waiting for infrastructure to be healthy..."
for i in $(seq 1 30); do
    if docker compose -f deploy/docker-compose.yml exec -T postgres pg_isready -U neuranac -q 2>/dev/null; then
        echo "    PostgreSQL is ready"
        break
    fi
    echo "    Waiting for PostgreSQL... ($i/30)"
    sleep 2
done

# Run database migrations (all versions in order)
echo "[+] Running database migrations..."
for migration in database/migrations/V*.sql; do
    if [ -f "$migration" ]; then
        echo "    Applying $(basename "$migration")..."
        docker compose -f deploy/docker-compose.yml exec -T postgres psql -U neuranac -d neuranac < "$migration" 2>/dev/null || true
    fi
done

# Load seed data
echo "[+] Loading seed data..."
docker compose -f deploy/docker-compose.yml exec -T postgres psql -U neuranac -d neuranac < database/seeds/seed_data.sql 2>/dev/null || true

# Post-seed: align site + deployment config with env vars
if [ -f .env ]; then
    _ST=$(grep -E "^NEURANAC_SITE_TYPE=" .env 2>/dev/null | cut -d= -f2 | tr -d '"' | tr -d "'" || true)
    _DM=$(grep -E "^DEPLOYMENT_MODE=" .env 2>/dev/null | cut -d= -f2 | tr -d '"' | tr -d "'" || true)
    _IE=$(grep -E "^LEGACY_NAC_ENABLED=" .env 2>/dev/null | cut -d= -f2 | tr -d '"' | tr -d "'" || true)
    _SI=$(grep -E "^NEURANAC_SITE_ID=" .env 2>/dev/null | cut -d= -f2 | tr -d '"' | tr -d "'" || true)

    _ST=${_ST:-onprem}
    _DM=${_DM:-standalone}
    _IE=${_IE:-false}
    _SI=${_SI:-00000000-0000-0000-0000-000000000001}

    echo "[+] Aligning DB site config: site_type=$_ST, deployment_mode=$_DM, legacy_nac_enabled=$_IE"
    docker compose -f deploy/docker-compose.yml exec -T postgres psql -U neuranac -d neuranac <<-EOSQL 2>/dev/null || true
        UPDATE neuranac_sites
           SET site_type = '$_ST', deployment_mode = '$_DM'
         WHERE id = '$_SI'::uuid;
        UPDATE neuranac_deployment_config
           SET deployment_mode = '$_DM',
               legacy_nac_enabled = $_IE;
EOSQL
fi

# Build and start application services
echo "[+] Building application services..."
docker compose -f deploy/docker-compose.yml build

echo "[+] Starting all services (NeuraNAC Bridge always runs with pluggable adapters)..."
docker compose -f deploy/docker-compose.yml up -d

# Wait for API to be ready
echo "[+] Waiting for API Gateway to start..."
for i in $(seq 1 30); do
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo "    API Gateway is ready"
        break
    fi
    sleep 2
done

echo ""
echo "=========================================="
echo "  NeuraNAC Setup Complete!"
echo "=========================================="
echo ""
echo "  Dashboard:  http://localhost:3001"
echo "  API Docs:   http://localhost:8080/api/docs"
echo "  API:        http://localhost:8080/api/v1/"
echo "  Prometheus: http://localhost:9092 (with --profile monitoring)"
echo "  Grafana:    http://localhost:3000 (with --profile monitoring)"
echo ""
echo "  Default credentials will be printed in api-gateway logs:"
echo "  docker compose -f deploy/docker-compose.yml logs api-gateway | grep password"
echo ""
