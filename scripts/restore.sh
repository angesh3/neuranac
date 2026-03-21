#!/usr/bin/env bash
set -euo pipefail

# NeuraNAC Database Restore Script
# Usage: ./scripts/restore.sh <postgres_backup_file> [redis_backup_file]
# Restores PostgreSQL (required) and optionally Redis from backup files.

if [ $# -lt 1 ]; then
  echo "Usage: $0 <postgres_backup_file> [redis_backup_file]"
  echo ""
  echo "Examples:"
  echo "  $0 backups/postgres/neuranac_pg_20260303.dump"
  echo "  $0 backups/postgres/neuranac_pg_20260303.sql.gz backups/redis/neuranac_redis_20260303.rdb"
  exit 1
fi

PG_BACKUP="$1"
REDIS_BACKUP="${2:-}"
COMPOSE_FILE="deploy/docker-compose.yml"
PG_CONTAINER="neuranac-postgres"
REDIS_CONTAINER="neuranac-redis"
PG_USER="${POSTGRES_USER:-neuranac}"
PG_DB="${POSTGRES_DB:-neuranac}"
REDIS_PASSWORD="${REDIS_PASSWORD:-neuranac_dev_password}"

echo "=========================================="
echo "  NeuraNAC Restore"
echo "=========================================="
echo ""
echo "  ⚠️  WARNING: This will OVERWRITE the current database!"
echo "  PostgreSQL: $PG_BACKUP"
[ -n "$REDIS_BACKUP" ] && echo "  Redis: $REDIS_BACKUP"
echo ""
read -p "  Continue? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "  Aborted."
  exit 0
fi

# ─── Stop application services (keep infra running) ──────────────────
echo "[+] Stopping application services..."
docker compose -f "$COMPOSE_FILE" stop api-gateway radius-server policy-engine ai-engine sync-engine web 2>/dev/null || true

# ─── Restore PostgreSQL ──────────────────────────────────────────────
echo "[+] Restoring PostgreSQL..."

if [[ "$PG_BACKUP" == *.dump ]]; then
  # Custom format: drop and recreate
  docker compose -f "$COMPOSE_FILE" exec -T "$PG_CONTAINER" \
    psql -U "$PG_USER" -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$PG_DB' AND pid <> pg_backend_pid();" 2>/dev/null || true

  docker compose -f "$COMPOSE_FILE" exec -T "$PG_CONTAINER" \
    dropdb -U "$PG_USER" --if-exists "$PG_DB" 2>/dev/null || true

  docker compose -f "$COMPOSE_FILE" exec -T "$PG_CONTAINER" \
    createdb -U "$PG_USER" "$PG_DB" 2>/dev/null

  docker compose -f "$COMPOSE_FILE" exec -T "$PG_CONTAINER" \
    pg_restore -U "$PG_USER" -d "$PG_DB" --no-owner --no-acl < "$PG_BACKUP"

  echo "    ✅ PostgreSQL restored from custom dump"

elif [[ "$PG_BACKUP" == *.sql.gz ]]; then
  # Plain SQL compressed
  docker compose -f "$COMPOSE_FILE" exec -T "$PG_CONTAINER" \
    psql -U "$PG_USER" -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$PG_DB' AND pid <> pg_backend_pid();" 2>/dev/null || true

  docker compose -f "$COMPOSE_FILE" exec -T "$PG_CONTAINER" \
    dropdb -U "$PG_USER" --if-exists "$PG_DB" 2>/dev/null || true

  docker compose -f "$COMPOSE_FILE" exec -T "$PG_CONTAINER" \
    createdb -U "$PG_USER" "$PG_DB" 2>/dev/null

  gunzip -c "$PG_BACKUP" | docker compose -f "$COMPOSE_FILE" exec -T "$PG_CONTAINER" \
    psql -U "$PG_USER" -d "$PG_DB" 2>/dev/null

  echo "    ✅ PostgreSQL restored from SQL dump"

elif [[ "$PG_BACKUP" == *.sql ]]; then
  # Plain SQL
  docker compose -f "$COMPOSE_FILE" exec -T "$PG_CONTAINER" \
    dropdb -U "$PG_USER" --if-exists "$PG_DB" 2>/dev/null || true

  docker compose -f "$COMPOSE_FILE" exec -T "$PG_CONTAINER" \
    createdb -U "$PG_USER" "$PG_DB" 2>/dev/null

  docker compose -f "$COMPOSE_FILE" exec -T "$PG_CONTAINER" \
    psql -U "$PG_USER" -d "$PG_DB" < "$PG_BACKUP" 2>/dev/null

  echo "    ✅ PostgreSQL restored from SQL file"
else
  echo "    ❌ Unsupported backup format: $PG_BACKUP"
  exit 1
fi

# ─── Restore Redis (optional) ────────────────────────────────────────
if [ -n "$REDIS_BACKUP" ] && [ -f "$REDIS_BACKUP" ]; then
  echo "[+] Restoring Redis..."
  docker compose -f "$COMPOSE_FILE" stop "$REDIS_CONTAINER" 2>/dev/null || true
  docker cp "$REDIS_BACKUP" "${REDIS_CONTAINER}:/data/dump.rdb" 2>/dev/null
  docker compose -f "$COMPOSE_FILE" start "$REDIS_CONTAINER" 2>/dev/null
  echo "    ✅ Redis restored"
fi

# ─── Restart application services ────────────────────────────────────
echo "[+] Starting application services..."
docker compose -f "$COMPOSE_FILE" up -d

echo "[+] Waiting for services to be healthy..."
for i in $(seq 1 30); do
  if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "    ✅ API Gateway is ready"
    break
  fi
  sleep 2
done

echo ""
echo "=========================================="
echo "  Restore Complete"
echo "=========================================="
echo "  Verify: curl http://localhost:8080/api/v1/diagnostics/db-schema-check"
echo ""
