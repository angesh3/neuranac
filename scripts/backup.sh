#!/usr/bin/env bash
set -euo pipefail

# NeuraNAC Database Backup Script
# Usage: ./scripts/backup.sh [backup_dir]
# Backs up PostgreSQL and Redis data with timestamped filenames.
# Designed for cron scheduling or manual use.

BACKUP_DIR="${1:-backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
COMPOSE_FILE="deploy/docker-compose.yml"

# PostgreSQL settings
PG_CONTAINER="neuranac-postgres"
PG_USER="${POSTGRES_USER:-neuranac}"
PG_DB="${POSTGRES_DB:-neuranac}"

# Redis settings
REDIS_CONTAINER="neuranac-redis"
REDIS_PASSWORD="${REDIS_PASSWORD:-neuranac_dev_password}"

echo "=========================================="
echo "  NeuraNAC Backup — $TIMESTAMP"
echo "=========================================="

mkdir -p "$BACKUP_DIR/postgres" "$BACKUP_DIR/redis"

# ─── PostgreSQL Backup ────────────────────────────────────────────────
echo "[+] Backing up PostgreSQL..."
PG_BACKUP_FILE="$BACKUP_DIR/postgres/neuranac_pg_${TIMESTAMP}.sql.gz"

docker compose -f "$COMPOSE_FILE" exec -T "$PG_CONTAINER" \
  pg_dump -U "$PG_USER" -d "$PG_DB" --format=custom --compress=9 \
  > "$BACKUP_DIR/postgres/neuranac_pg_${TIMESTAMP}.dump" 2>/dev/null

# Also create a plain SQL backup for disaster recovery
docker compose -f "$COMPOSE_FILE" exec -T "$PG_CONTAINER" \
  pg_dump -U "$PG_USER" -d "$PG_DB" --format=plain \
  | gzip > "$PG_BACKUP_FILE" 2>/dev/null

PG_SIZE=$(du -sh "$PG_BACKUP_FILE" 2>/dev/null | cut -f1)
echo "    PostgreSQL backup: $PG_BACKUP_FILE ($PG_SIZE)"

# ─── Redis Backup ─────────────────────────────────────────────────────
echo "[+] Backing up Redis..."
REDIS_BACKUP_FILE="$BACKUP_DIR/redis/neuranac_redis_${TIMESTAMP}.rdb"

# Trigger Redis BGSAVE and wait for completion
docker compose -f "$COMPOSE_FILE" exec -T "$REDIS_CONTAINER" \
  redis-cli -a "$REDIS_PASSWORD" BGSAVE 2>/dev/null || true

sleep 2

docker compose -f "$COMPOSE_FILE" exec -T "$REDIS_CONTAINER" \
  redis-cli -a "$REDIS_PASSWORD" --rdb /data/dump_backup.rdb 2>/dev/null || true

docker cp "${REDIS_CONTAINER}:/data/dump_backup.rdb" "$REDIS_BACKUP_FILE" 2>/dev/null || {
  # Fallback: copy the appendonly file
  docker cp "${REDIS_CONTAINER}:/data/appendonly.aof" \
    "$BACKUP_DIR/redis/neuranac_redis_${TIMESTAMP}.aof" 2>/dev/null || true
  echo "    Redis backup: AOF fallback"
}

REDIS_SIZE=$(du -sh "$REDIS_BACKUP_FILE" 2>/dev/null | cut -f1 || echo "N/A")
echo "    Redis backup: $REDIS_BACKUP_FILE ($REDIS_SIZE)"

# ─── Cleanup old backups (retain last 7 days) ─────────────────────────
echo "[+] Cleaning up backups older than 7 days..."
find "$BACKUP_DIR" -name "neuranac_*" -mtime +7 -delete 2>/dev/null || true

# ─── Verify backup integrity ──────────────────────────────────────────
echo "[+] Verifying PostgreSQL backup integrity..."
if docker compose -f "$COMPOSE_FILE" exec -T "$PG_CONTAINER" \
  pg_restore --list "/dev/stdin" < "$BACKUP_DIR/postgres/neuranac_pg_${TIMESTAMP}.dump" >/dev/null 2>&1; then
  echo "    ✅ PostgreSQL backup verified"
else
  echo "    ⚠️  Could not verify .dump file (non-critical if .sql.gz exists)"
fi

echo ""
echo "=========================================="
echo "  Backup Complete"
echo "=========================================="
echo "  Location: $BACKUP_DIR/"
echo "  Files:"
ls -la "$BACKUP_DIR/postgres/neuranac_pg_${TIMESTAMP}"* 2>/dev/null || true
ls -la "$BACKUP_DIR/redis/neuranac_redis_${TIMESTAMP}"* 2>/dev/null || true
echo ""
echo "  To schedule daily backups, add to crontab:"
echo "  0 2 * * * cd /path/to/neuranac && ./scripts/backup.sh"
echo ""
