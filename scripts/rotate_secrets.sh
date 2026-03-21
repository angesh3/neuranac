#!/usr/bin/env bash
set -euo pipefail

# NeuraNAC Secret Rotation Script
# Usage: ./scripts/rotate_secrets.sh [component]
# Components: jwt, db, redis, nats, all
# Rotates secrets and restarts affected services with zero downtime.

COMPONENT="${1:-all}"
COMPOSE_FILE="deploy/docker-compose.yml"
ENV_FILE=".env"

echo "=========================================="
echo "  NeuraNAC Secret Rotation"
echo "=========================================="

generate_secret() {
  openssl rand -base64 "$1" | tr -d '=/+' | head -c "$1"
}

rotate_jwt_keys() {
  echo "[+] Rotating JWT keys..."
  CERT_DIR="deploy/certs"
  mkdir -p "$CERT_DIR"

  # Backup current keys
  [ -f "$CERT_DIR/jwt_private.pem" ] && cp "$CERT_DIR/jwt_private.pem" "$CERT_DIR/jwt_private.pem.bak.$(date +%s)"
  [ -f "$CERT_DIR/jwt_public.pem" ] && cp "$CERT_DIR/jwt_public.pem" "$CERT_DIR/jwt_public.pem.bak.$(date +%s)"

  # Generate new RSA key pair
  openssl genpkey -algorithm RSA -out "$CERT_DIR/jwt_private.pem" -pkeyopt rsa_keygen_bits:2048 2>/dev/null
  openssl rsa -in "$CERT_DIR/jwt_private.pem" -pubout -out "$CERT_DIR/jwt_public.pem" 2>/dev/null
  chmod 600 "$CERT_DIR/jwt_private.pem"
  chmod 644 "$CERT_DIR/jwt_public.pem"

  # Update env file
  if [ -f "$ENV_FILE" ]; then
    sed -i.bak "s|^JWT_PRIVATE_KEY_PATH=.*|JWT_PRIVATE_KEY_PATH=$CERT_DIR/jwt_private.pem|" "$ENV_FILE"
    sed -i.bak "s|^JWT_PUBLIC_KEY_PATH=.*|JWT_PUBLIC_KEY_PATH=$CERT_DIR/jwt_public.pem|" "$ENV_FILE"
  fi

  echo "    ✅ JWT keys rotated"
  echo "    ⚠️  Existing access tokens will be invalidated (refresh tokens still valid for grace period)"

  # Flush Redis token blocklist to force re-auth
  docker compose -f "$COMPOSE_FILE" exec -T neuranac-redis \
    redis-cli -a "${REDIS_PASSWORD:-neuranac_dev_password}" FLUSHDB 2>/dev/null || true
}

rotate_db_password() {
  echo "[+] Rotating PostgreSQL password..."
  NEW_PG_PASS=$(generate_secret 32)

  # Update PostgreSQL user password
  docker compose -f "$COMPOSE_FILE" exec -T neuranac-postgres \
    psql -U neuranac -c "ALTER USER neuranac WITH PASSWORD '$NEW_PG_PASS';" 2>/dev/null

  # Update .env file
  if [ -f "$ENV_FILE" ]; then
    sed -i.bak "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$NEW_PG_PASS|" "$ENV_FILE"
  fi

  echo "    ✅ PostgreSQL password rotated"
  echo "    New password written to $ENV_FILE"
}

rotate_redis_password() {
  echo "[+] Rotating Redis password..."
  NEW_REDIS_PASS=$(generate_secret 32)

  # Update Redis password via CONFIG SET
  CURRENT_PASS="${REDIS_PASSWORD:-neuranac_dev_password}"
  docker compose -f "$COMPOSE_FILE" exec -T neuranac-redis \
    redis-cli -a "$CURRENT_PASS" CONFIG SET requirepass "$NEW_REDIS_PASS" 2>/dev/null

  # Update .env file
  if [ -f "$ENV_FILE" ]; then
    sed -i.bak "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=$NEW_REDIS_PASS|" "$ENV_FILE"
  fi

  export REDIS_PASSWORD="$NEW_REDIS_PASS"
  echo "    ✅ Redis password rotated"
}

rotate_nats_password() {
  echo "[+] Rotating NATS password..."
  NEW_NATS_PASS=$(generate_secret 32)

  if [ -f "$ENV_FILE" ]; then
    sed -i.bak "s|^NATS_PASSWORD=.*|NATS_PASSWORD=$NEW_NATS_PASS|" "$ENV_FILE"
  fi

  echo "    ✅ NATS password updated in env (requires NATS restart)"
}

rotate_api_secret() {
  echo "[+] Rotating API secret key..."
  NEW_API_SECRET=$(generate_secret 48)
  NEW_JWT_SECRET=$(generate_secret 72)

  if [ -f "$ENV_FILE" ]; then
    sed -i.bak "s|^API_SECRET_KEY=.*|API_SECRET_KEY=$NEW_API_SECRET|" "$ENV_FILE"
    sed -i.bak "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$NEW_JWT_SECRET|" "$ENV_FILE"
  fi

  echo "    ✅ API and JWT secret keys rotated"
}

restart_services() {
  echo "[+] Performing rolling restart of application services..."
  for svc in api-gateway radius-server policy-engine ai-engine sync-engine; do
    echo "    Restarting $svc..."
    docker compose -f "$COMPOSE_FILE" restart "$svc" 2>/dev/null || true
    sleep 5
  done
  echo "    ✅ All services restarted"
}

case "$COMPONENT" in
  jwt)
    rotate_jwt_keys
    restart_services
    ;;
  db)
    rotate_db_password
    restart_services
    ;;
  redis)
    rotate_redis_password
    restart_services
    ;;
  nats)
    rotate_nats_password
    echo "[!] NATS requires full restart:"
    echo "    docker compose -f $COMPOSE_FILE restart nats"
    restart_services
    ;;
  api)
    rotate_api_secret
    restart_services
    ;;
  all)
    rotate_jwt_keys
    rotate_db_password
    rotate_redis_password
    rotate_nats_password
    rotate_api_secret
    echo ""
    echo "[+] Restarting all services with new secrets..."
    docker compose -f "$COMPOSE_FILE" down 2>/dev/null || true
    docker compose -f "$COMPOSE_FILE" up -d
    ;;
  *)
    echo "Unknown component: $COMPONENT"
    echo "Usage: $0 [jwt|db|redis|nats|api|all]"
    exit 1
    ;;
esac

echo ""
echo "=========================================="
echo "  Secret Rotation Complete"
echo "=========================================="
echo ""
echo "  ⚠️  Remember to update any external systems"
echo "     that use these credentials."
echo ""
echo "  Recommended: Schedule rotation every 90 days"
echo "  0 0 1 */3 * cd /path/to/neuranac && ./scripts/rotate_secrets.sh all"
echo ""
